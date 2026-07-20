"""Modal deployment entrypoint for the AI Video Upscaler.

Wires the framework-agnostic FastAPI app to Modal-backed storage and the GPU
worker. Run locally with ``modal serve video-backend/modal_app.py`` or deploy
with ``modal deploy video-backend/modal_app.py``.

This module imports ``modal`` and is intentionally excluded from the unit-test,
lint, and type-check passes (it cannot run without the Modal runtime). The
testable logic lives in ``video-backend/app``.

Reuses the ``photo-restorer-auth`` secret (same approved Google account); the
Volume and Dict are the video service's own.
"""

from __future__ import annotations

from collections.abc import Iterator

import modal
from app.config import get_settings
from app.jobs import JobService
from app.storage import FileStore, MetadataStore

# NOTE: app.main is imported lazily inside fastapi_app() (not here) because it
# pulls in FastAPI, which is only installed in the web image. The GPU worker
# container also imports this module, so a top-level FastAPI import would crash
# it on startup.

DATA_MOUNT = "/data"
MODELS_DIR = "/models"

# Compact Real-ESRGAN checkpoints, baked into the GPU image at build. ~5 MB
# each; the SRVGGNetCompact architecture is what makes per-frame video work
# affordable. The main model and its weak-denoise (wdn) twin are blended at
# load time to control smoothing (see realesrgan_video.py).
_RELEASE = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0"
WEIGHTS = [
    {
        "file": "realesr-general-x4v3.pth",
        "url": f"{_RELEASE}/realesr-general-x4v3.pth",
        "sha256": "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292",
    },
    {
        # Pin after the first successful build: the build log prints
        # "PIN_SHA256 realesr-general-wdn-x4v3.pth <hash>" (same pin-from-
        # first-build approach the photo backend used for its Ultra snapshot).
        "file": "realesr-general-wdn-x4v3.pth",
        "url": f"{_RELEASE}/realesr-general-wdn-x4v3.pth",
        "sha256": None,
    },
]

app = modal.App("ai-video-upscaler")

files_volume = modal.Volume.from_name("video-upscaler-files", create_if_missing=True)
jobs_dict = modal.Dict.from_name("video-upscaler-jobs", create_if_missing=True)


def _weight_download_commands() -> list[str]:
    """Fetch each weight at build; verify the pinned hash or print it to pin."""
    cmds = [f"mkdir -p {MODELS_DIR}"]
    for w in WEIGHTS:
        path = f"{MODELS_DIR}/{w['file']}"
        script = (
            "import urllib.request, hashlib, os; "
            f"p = {path!r}; "
            f"urllib.request.urlretrieve({w['url']!r}, p); "
            "h = hashlib.sha256(open(p, 'rb').read()).hexdigest(); "
            # Sanity floor so an HTML error page can never pass as weights.
            "assert os.path.getsize(p) > 1_000_000, os.path.getsize(p); "
        )
        if w["sha256"]:
            script += f"assert h == {w['sha256']!r}, h"
        else:
            script += f"print('PIN_SHA256', {w['file']!r}, h)"
        cmds.append(f'python -c "{script}"')
    return cmds

# Lightweight image for the web layer: no torch, but ffmpeg for ffprobe
# validation of uploads.
web_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "fastapi>=0.111",
        "python-multipart>=0.0.9",
        "pydantic>=2.7",
        "pydantic-settings>=2.3",
        "google-auth>=2.30",
        # google.auth.transport.requests needs `requests`; google-auth does not
        # pull it in automatically. Without it, token verification 500s.
        "requests>=2.31",
    )
    .add_local_python_source("app")
)

# GPU image: ffmpeg (with NVENC-capable build from debian) + the Real-ESRGAN
# stack. torch 2.1.2 / torchvision 0.16.2 are pinned because basicsr imports
# torchvision.transforms.functional_tensor, removed in torchvision 0.17.
# basicsr is installed with --no-build-isolation so its legacy setup.py sees
# the already-installed torch/numpy; setuptools<70 for the same reason.
gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "torch==2.1.2",
        "torchvision==0.16.2",
        "numpy<2",
        "cython",
        "setuptools<70",
        "wheel",
        "opencv-python-headless==4.9.0.80",
        "Pillow>=10.3",
        "pydantic>=2.7",
        "pydantic-settings>=2.3",
    )
    .pip_install(
        # Re-pin numpy<2: basicsr's transitive deps otherwise pull NumPy 2.x,
        # which torch 2.1.2 cannot initialize.
        "numpy<2",
        "basicsr==1.4.2",
        extra_options="--no-build-isolation",
    )
    .run_commands(*_weight_download_commands())
    .add_local_python_source("app")
)


# --- Modal-backed storage implementations --------------------------------


class ModalVolumeFileStore(FileStore):
    """FileStore over a mounted Modal Volume; commit/reload bridge containers."""

    def __init__(self, mount: str, volume: modal.Volume) -> None:
        from app.storage import LocalFileStore

        self._local = LocalFileStore(mount)
        self._volume = volume

    def write(self, path: str, data: bytes) -> None:
        self._local.write(path, data)

    def read(self, path: str) -> bytes:
        return self._local.read(path)

    def exists(self, path: str) -> bool:
        return self._local.exists(path)

    def delete(self, path: str) -> None:
        self._local.delete(path)

    def delete_prefix(self, prefix: str) -> None:
        self._local.delete_prefix(prefix)

    def commit(self) -> None:
        self._volume.commit()

    def reload(self) -> None:
        self._volume.reload()


class ModalDictMetadataStore(MetadataStore):
    """MetadataStore over a Modal Dict."""

    def __init__(self, d: modal.Dict) -> None:
        self._d = d

    def get(self, key: str) -> dict | None:
        return self._d.get(key, None)

    def put(self, key: str, value: dict) -> None:
        self._d[key] = value

    def delete(self, key: str) -> None:
        self._d.pop(key, None)

    def contains(self, key: str) -> bool:
        return key in self._d

    def items(self) -> Iterator[tuple[str, dict]]:
        yield from self._d.items()


# --- GPU worker ----------------------------------------------------------


@app.cls(
    gpu="L4",
    timeout=30 * 60,
    image=gpu_image,
    volumes={DATA_MOUNT: files_volume},
)
class VideoUpscaler:
    @modal.enter()
    def load_models(self) -> None:
        from app.realesrgan_video import RealEsrganVideoEnhancer

        self._files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
        self._jobs = JobService(ModalDictMetadataStore(jobs_dict), self._files)
        # fp16 is safe on the L4; the compact model needs no tiling at 1080p.
        # denoise=0.35 keeps fine texture (1.0 = maximum smoothing).
        self._enhancer = RealEsrganVideoEnhancer(MODELS_DIR, half=True, denoise=0.35)
        self._enhancer.load()
        self._enhancer.warmup()

    @modal.method()
    def process(self, job_id: str) -> None:
        from app.worker import run_video_job

        run_video_job(self._jobs, self._files, job_id, self._enhancer)


class SpawnProcessor:
    """Processor that dispatches a job to the GPU worker via spawn().

    The web container never blocks on GPU work; the worker reads inputs from
    the shared Volume and writes results back.
    """

    def process(self, job_id: str) -> None:
        jobs = JobService(
            ModalDictMetadataStore(jobs_dict),
            ModalVolumeFileStore(DATA_MOUNT, files_volume),
        )
        call = VideoUpscaler().process.spawn(job_id)
        jobs.set_call_id(job_id, call.object_id)


# --- Debugging helpers (run via `modal run modal_app.py::<name>`) ---------


@app.function(image=web_image, volumes={DATA_MOUNT: files_volume})
def diagnose() -> None:
    """Print sanitized recent job records.

    No video bytes, owner ids, or emails are printed — CI logs are public.
    """
    records = [v for k, v in jobs_dict.items() if str(k).startswith("job:")]
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    print(f"{len(records)} job records present")
    for r in records[:15]:
        jid = str(r.get("job_id", "?"))
        print(
            f"{r.get('created_at')} {jid[:16]} out={r.get('output')} "
            f"status={r.get('status')} stage={r.get('stage')} prog={r.get('progress')} "
            f"frames={r.get('frames_done')}/{r.get('frames_total')} "
            f"err={r.get('error_code')} msg={str(r.get('error_message'))[:200]}"
        )


@app.function(gpu="L4", image=gpu_image, timeout=15 * 60)
def selftest_video() -> None:
    """Run the full deployed pipeline on a synthetic clip, on the real GPU.

    Generates a 4-second 1080p test pattern with audio, streams it through the
    Real-ESRGAN pipeline, and reports throughput, output facts, and whether
    NVENC was used — proving the pipeline end to end before the app touches it.
    """
    import subprocess
    import tempfile
    import time
    from pathlib import Path

    from app.realesrgan_video import RealEsrganVideoEnhancer
    from app.schemas import OutputSize
    from app.sizing import compute_target_size
    from app.video_io import probe_video

    with tempfile.TemporaryDirectory() as workdir:
        work = Path(workdir)
        src = work / "src.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", "testsrc2=duration=4:size=1920x1080:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                str(src),
            ],
            check=True,
        )
        info = probe_video(src)
        target = compute_target_size(info.width, info.height, OutputSize.X2)
        print(f"source: {info.width}x{info.height}@{info.fps:.2f} "
              f"{info.frames_estimate} frames; target: {target}")

        enhancer = RealEsrganVideoEnhancer(MODELS_DIR, half=True, denoise=0.35).load()
        dst = work / "out.mp4"
        seen = {"n": 0}

        def on_frame(n: int) -> None:
            seen["n"] = n

        start = time.time()
        enhancer.enhance(src, dst, info, target, on_frame)
        elapsed = time.time() - start

        out = probe_video(dst)
        fps = seen["n"] / elapsed if elapsed > 0 else 0.0
        print(
            f"OK {seen['n']} frames in {elapsed:.1f}s ({fps:.1f} fps) -> "
            f"{out.width}x{out.height} codec={out.codec} audio={out.audio_codec} "
            f"duration={out.duration_seconds:.2f}s"
        )

        # Portrait pass: the same clip with a 90-degree rotation flag (how
        # phones store portrait video) must probe swapped and come out upright.
        portrait_src = work / "src_portrait.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-display_rotation", "90",
                "-i", str(src), "-c", "copy", str(portrait_src),
            ],
            check=True,
        )
        p_info = probe_video(portrait_src)
        assert (p_info.width, p_info.height) == (1080, 1920), (p_info.width, p_info.height)
        p_target = compute_target_size(p_info.width, p_info.height, OutputSize.X2)
        p_dst = work / "out_portrait.mp4"
        enhancer.enhance(portrait_src, p_dst, p_info, p_target, on_frame)
        p_out = probe_video(p_dst)
        assert (p_out.width, p_out.height) == p_target, (p_out.width, p_out.height)
        print(f"portrait OK -> {p_out.width}x{p_out.height} (target {p_target})")


# --- Web app -------------------------------------------------------------


@app.function(
    image=web_image,
    volumes={DATA_MOUNT: files_volume},
    secrets=[modal.Secret.from_name("photo-restorer-auth")],
    # Uploads are read into memory for validation; leave headroom over the
    # 300 MB limit.
    memory=2048,
    min_containers=0,
)
@modal.asgi_app()
def fastapi_app():
    from app.main import create_app  # lazy: FastAPI only exists in the web image

    settings = get_settings()
    files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
    meta = ModalDictMetadataStore(jobs_dict)
    return create_app(
        settings=settings,
        files=files,
        meta=meta,
        processor=SpawnProcessor(),
    )
