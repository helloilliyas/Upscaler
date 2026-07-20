"""Real-ESRGAN frame-streaming video enhancer (GPU worker only).

Two ffmpeg subprocesses bracket the model so frames never touch disk:

    source ─► ffmpeg decode (CFR, rgb24 rawvideo) ─► pipe
                    │ one W*H*3 buffer per frame
                    ▼
        SRVGGNetCompact x4 (fp16, CUDA)  ── realesr-general-x4v3
                    ▼
    pipe ─► ffmpeg encode (scale to target, hevc_nvenc → libx264 fallback,
            audio mapped straight from the source file)  ─► result.mp4

torch/numpy are imported lazily inside ``load`` so this module is importable
(and lintable) in CPU-only environments; CI never loads the model.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .video_io import FfmpegError, VideoInfo, _tool
from .worker import audio_args

_SCALE = 4
_MODEL_FILE = "realesr-general-x4v3.pth"
# The weak-denoise twin; blended with the main model to control smoothing.
_WDN_MODEL_FILE = "realesr-general-wdn-x4v3.pth"
# Mild output sharpening (ffmpeg unsharp luma amount) to counter resampling.
_SHARPEN = 0.3


class RealEsrganVideoEnhancer:
    """Streams frames through the compact Real-ESRGAN x4 model."""

    def __init__(
        self, weights_dir: str, *, half: bool = True, denoise: float = 0.35
    ) -> None:
        """``denoise`` in [0, 1]: 1.0 = pure strong-denoise model (very smooth),
        0.0 = pure weak-denoise model (keeps grain and fine texture). The
        weights of the two models are linearly blended, exactly like the
        official Real-ESRGAN ``--denoise_strength`` option.
        """
        self._weights = Path(weights_dir) / _MODEL_FILE
        self._wdn_weights = Path(weights_dir) / _WDN_MODEL_FILE
        self._half = half
        self._denoise = min(1.0, max(0.0, denoise))
        self._model: Any = None
        self._torch: Any = None

    def load(self) -> RealEsrganVideoEnhancer:
        import torch
        from basicsr.archs.srvgg_arch import SRVGGNetCompact

        model = SRVGGNetCompact(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_conv=32,
            upscale=_SCALE,
            act_type="prelu",
        )

        def params(path: Path) -> Any:
            state = torch.load(str(path), map_location="cpu")
            return state.get("params", state)

        state = params(self._weights)
        if self._denoise < 1.0 and self._wdn_weights.exists():
            wdn = params(self._wdn_weights)
            state = {
                key: self._denoise * value + (1.0 - self._denoise) * wdn[key]
                for key, value in state.items()
            }
        model.load_state_dict(state, strict=True)
        model.eval()
        model = model.cuda().half() if self._half else model.cuda()
        self._model = model
        self._torch = torch
        return self

    def warmup(self) -> None:
        import numpy as np

        if self._model is None:
            self.load()
        self._upscale_frame(np.zeros((64, 64, 3), dtype=np.uint8), (128, 128))

    # --- the streaming pipeline -----------------------------------------

    def enhance(
        self,
        src: Path,
        dst: Path,
        info: VideoInfo,
        target: tuple[int, int],
        on_frame: Callable[[int], None],
    ) -> None:
        if self._model is None:
            self.load()
        try:
            self._stream(src, dst, info, target, on_frame, vcodec="hevc_nvenc")
        except FfmpegError:
            # No usable NVENC on this host/driver: re-run with CPU x264.
            self._stream(src, dst, info, target, on_frame, vcodec="libx264")

    def _stream(
        self,
        src: Path,
        dst: Path,
        info: VideoInfo,
        target: tuple[int, int],
        on_frame: Callable[[int], None],
        *,
        vcodec: str,
    ) -> None:
        w, h = info.width, info.height
        tw, th = target
        fps = f"{info.fps:.6f}"
        frame_bytes = w * h * 3

        decode_cmd = [
            _tool("ffmpeg"), "-hide_banner", "-v", "error", "-nostats",
            "-i", str(src),
            "-map", "0:v:0",
            # Force CFR at the probed rate so frame counts and audio sync are
            # deterministic even for VFR phone recordings.
            "-fps_mode", "cfr", "-r", fps,
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "pipe:1",
        ]
        if vcodec == "hevc_nvenc":
            codec_args = ["-c:v", "hevc_nvenc", "-preset", "p5", "-cq", "20", "-tag:v", "hvc1"]
        else:
            codec_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "17"]
        # Frames are resized to the final target on the GPU before piping, so
        # the encoder receives target-sized frames (4x less pipe traffic than
        # piping the raw 4x model output) and never scales on the CPU.
        encode_cmd = [
            _tool("ffmpeg"), "-hide_banner", "-y", "-v", "error", "-nostats",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{tw}x{th}", "-r", fps,
            "-i", "pipe:0",
            "-i", str(src),
            "-map", "0:v:0",
            *(["-map", "1:a:0"] if info.has_audio else []),
            "-vf", f"unsharp=5:5:{_SHARPEN}:5:5:0",
            "-pix_fmt", "yuv420p",
            *codec_args,
            *audio_args(info),
            "-movflags", "+faststart",
            str(dst),
        ]

        with tempfile.TemporaryFile() as dec_err, tempfile.TemporaryFile() as enc_err:
            decoder = subprocess.Popen(
                decode_cmd, stdout=subprocess.PIPE, stderr=dec_err, stdin=subprocess.DEVNULL
            )
            encoder = subprocess.Popen(
                encode_cmd, stdin=subprocess.PIPE, stderr=enc_err, stdout=subprocess.DEVNULL
            )
            assert decoder.stdout is not None and encoder.stdin is not None
            frames = 0
            try:
                import numpy as np

                while True:
                    raw = _read_exact(decoder.stdout, frame_bytes)
                    if len(raw) < frame_bytes:
                        break
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)
                    encoder.stdin.write(self._upscale_frame(frame, target).tobytes())
                    frames += 1
                    on_frame(frames)
                encoder.stdin.close()
            except BrokenPipeError:
                pass  # encoder died; surfaced via its exit code below
            finally:
                decoder.stdout.close()

            dec_code, enc_code = decoder.wait(), encoder.wait()
            if enc_code != 0:
                raise FfmpegError(f"encoder exited with {enc_code}: {_tail(enc_err)}")
            if dec_code != 0:
                raise FfmpegError(f"decoder exited with {dec_code}: {_tail(dec_err)}")
            if frames == 0:
                raise FfmpegError("no frames decoded from source")

    def _upscale_frame(self, frame: Any, target: tuple[int, int]) -> Any:
        """rgb24 HxWx3 uint8 -> target-sized (W,H) HxWx3 uint8 through the model.

        The 4x model output is resized to the final target on the GPU (bicubic,
        antialiased) so only target-sized frames ever cross the CPU boundary.
        """
        torch = self._torch
        tw, th = target
        with torch.inference_mode():
            tensor = torch.from_numpy(frame.copy()).cuda().permute(2, 0, 1).unsqueeze(0)
            tensor = tensor.half() if self._half else tensor.float()
            out = self._model(tensor.div_(255.0))
            if (out.shape[3], out.shape[2]) != (tw, th):
                out = torch.nn.functional.interpolate(
                    out.float(), size=(th, tw), mode="bicubic", antialias=True
                )
            out = out.squeeze(0).permute(1, 2, 0).clamp_(0, 1).mul_(255.0).round_()
            return out.to(torch.uint8).cpu().numpy()


def _read_exact(stream: Any, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def _tail(errf: Any, limit: int = 500) -> str:
    errf.seek(0)
    return errf.read().decode(errors="replace").strip()[-limit:]
