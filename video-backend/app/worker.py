"""Video job orchestration and the GPU-free placeholder enhancer.

``run_video_job`` owns stage transitions, temp-file handling, poster
generation, storage, and error mapping. An enhancer supplies only the actual
video-to-video transform — a pure-ffmpeg Lanczos scale for the placeholder,
the Real-ESRGAN frame-streaming pipeline on the GPU worker — so the
orchestration is written and tested once, without a GPU.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .errors import ApiError, ErrorCode
from .jobs import JobService
from .schemas import JobStage, OutputSize
from .sizing import compute_target_size
from .storage import FileStore, preview_path, result_path, source_path
from .video_io import ToolMissingError, VideoInfo, probe_video, run_ffmpeg

# Longest edge of the poster JPEG shown in the app's history list.
_POSTER_MAX_EDGE = 1280

# Frame progress is mapped into this progress-percent window.
_ENHANCE_START = 8
_ENHANCE_SPAN = 80

# Audio codecs that can be stream-copied into an MP4 container as-is; anything
# else (e.g. Opus/Vorbis from WebM) is transcoded to AAC.
_MP4_COPY_SAFE_AUDIO = {"aac", "mp3"}


class VideoEnhancer(Protocol):
    """Transforms ``src`` into an upscaled MP4 at ``dst``.

    Implementations must produce H.264/HEVC + yuv420p in MP4, preserve the
    source frame rate and audio, and call ``on_frame`` with the running frame
    count as work progresses.
    """

    def enhance(
        self,
        src: Path,
        dst: Path,
        info: VideoInfo,
        target: tuple[int, int],
        on_frame: Callable[[int], None],
    ) -> None: ...


class Processor(Protocol):
    """Runs a single job to completion (or failure), updating its record."""

    def process(self, job_id: str) -> None: ...


def run_video_job(
    jobs: JobService,
    files: FileStore,
    job_id: str,
    enhancer: VideoEnhancer,
) -> None:
    """Drive one video job through its stages using the supplied enhancer.

    Reads the stored source, probes it, runs the enhancer in a temp workspace,
    writes the result + poster, commits storage, and marks the job completed —
    mapping any failure to a job error rather than raising.
    """
    record = jobs.get(job_id)
    try:
        jobs.update_progress(job_id, stage=JobStage.VALIDATING, progress=3)
        files.reload()
        src_bytes = files.read(source_path(record.owner_sub, record.job_id))

        with tempfile.TemporaryDirectory(prefix="videojob_") as workdir:
            work = Path(workdir)
            src = work / "source"
            src.write_bytes(src_bytes)
            del src_bytes

            jobs.update_progress(job_id, stage=JobStage.DECODING, progress=6)
            info = probe_video(src)
            target = compute_target_size(info.width, info.height, OutputSize(record.output))
            frames_total = max(1, record.frames_total or info.frames_estimate)

            dst = work / "result.mp4"
            enhancer.enhance(
                src, dst, info, target, _progress_reporter(jobs, job_id, frames_total)
            )

            jobs.update_progress(job_id, stage=JobStage.ENCODING, progress=90)
            out_info = probe_video(dst)
            poster = work / "poster.jpg"
            _extract_poster(dst, poster, out_info.width, out_info.height)

            res_path = result_path(record.owner_sub, record.job_id) + ".mp4"
            prev_path = preview_path(record.owner_sub, record.job_id) + ".jpg"
            files.write(res_path, dst.read_bytes())
            files.write(prev_path, poster.read_bytes())
            files.commit()

        jobs.mark_completed(
            job_id,
            result_path=res_path,
            preview_path=prev_path,
            width=out_info.width,
            height=out_info.height,
        )
    except ApiError as exc:
        jobs.mark_failed(job_id, code=exc.code, message=exc.message)
    except ToolMissingError as exc:
        jobs.mark_failed(job_id, code=ErrorCode.INTERNAL_ERROR, message=str(exc))
    except Exception as exc:  # any model/IO failure becomes a job error, not a crash
        jobs.mark_failed(
            job_id, code=ErrorCode.MODEL_ERROR, message=f"Processing failed: {exc}"
        )


def _progress_reporter(
    jobs: JobService, job_id: str, frames_total: int
) -> Callable[[int], None]:
    """Map frame counts into the 8..88 progress window.

    Only writes to the metadata store when the integer percent advances, so a
    long job costs at most ~80 Dict RPCs regardless of frame count.
    """
    last = {"pct": -1}

    def on_frame(frames_done: int) -> None:
        pct = _ENHANCE_START + min(
            _ENHANCE_SPAN, frames_done * _ENHANCE_SPAN // frames_total
        )
        if pct > last["pct"]:
            last["pct"] = pct
            jobs.update_progress(
                job_id,
                stage=JobStage.ENHANCING,
                progress=pct,
                frames_done=min(frames_done, frames_total),
            )

    return on_frame


def audio_args(info: VideoInfo) -> list[str]:
    """Output-side ffmpeg audio arguments: stream-copy when MP4-safe."""
    if not info.has_audio:
        return ["-an"]
    if info.audio_codec in _MP4_COPY_SAFE_AUDIO:
        return ["-c:a", "copy"]
    return ["-c:a", "aac", "-b:a", "192k"]


def _extract_poster(video: Path, dst: Path, width: int, height: int) -> None:
    """Write the first frame as a JPEG poster with a bounded long edge."""
    scale = min(1.0, _POSTER_MAX_EDGE / max(width, height))
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    run_ffmpeg(
        [
            "-i", str(video),
            "-frames:v", "1",
            "-vf", f"scale={w}:{h}",
            "-q:v", "3",
            str(dst),
        ]
    )


class PlaceholderVideoEnhancer:
    """CPU stand-in: Lanczos scale + x264, audio preserved.

    Exercises the entire job flow (decode, scale, encode, audio, progress)
    without any model so the service is fully testable in CI.
    """

    def enhance(
        self,
        src: Path,
        dst: Path,
        info: VideoInfo,
        target: tuple[int, int],
        on_frame: Callable[[int], None],
    ) -> None:
        w, h = target
        run_ffmpeg(
            [
                "-i", str(src),
                "-map", "0:v:0",
                *(["-map", "0:a:0"] if info.has_audio else []),
                "-vf", f"scale={w}:{h}:flags=lanczos",
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "18",
                *audio_args(info),
                "-movflags", "+faststart",
                str(dst),
            ],
            on_frame=on_frame,
        )


class LocalPlaceholderProcessor:
    """GPU-free processor used for local runs and the test suite."""

    def __init__(self, jobs: JobService, files: FileStore) -> None:
        self._jobs = jobs
        self._files = files
        self._enhancer = PlaceholderVideoEnhancer()

    def process(self, job_id: str) -> None:
        run_video_job(self._jobs, self._files, job_id, self._enhancer)
