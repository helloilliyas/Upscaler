"""ffprobe/ffmpeg subprocess helpers.

All container parsing, decoding, and encoding happens inside ffmpeg processes;
Python never interprets uploaded bytes itself. Uploaded content is only ever
data to ffmpeg — nothing here executes it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


class ToolMissingError(RuntimeError):
    """ffmpeg/ffprobe is not installed on this host."""


class ProbeError(ValueError):
    """The file could not be probed as a sane video."""


class FfmpegError(RuntimeError):
    """An ffmpeg run exited non-zero; message carries a stderr tail."""


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ToolMissingError(f"{name} is not available on PATH")
    return path


@dataclass(frozen=True)
class VideoInfo:
    """Probed facts about a video file (first real video stream).

    ``width``/``height`` are DISPLAY dimensions: when the stream carries a
    90/270-degree rotation flag (portrait phone video), they are swapped to
    match the auto-rotated frames every ffmpeg decoder emits. Treating the
    coded dimensions as the frame geometry silently shreds portrait video
    into horizontal stripes.
    """

    width: int
    height: int
    duration_seconds: float
    fps: float
    frames_estimate: int
    container: str  # raw ffprobe format_name, e.g. "mov,mp4,m4a,3gp,3g2,mj2"
    codec: str  # e.g. "h264"
    has_audio: bool
    audio_codec: str | None


def _parse_rate(value: object) -> float | None:
    try:
        rate = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None


def _parse_float(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _rotation_degrees(stream: dict) -> int:
    """Rotation from the Display Matrix side data (or the legacy rotate tag)."""
    rotation = 0
    for side_data in stream.get("side_data_list") or []:
        if "rotation" in side_data:
            try:
                rotation = int(side_data["rotation"])
            except (TypeError, ValueError):
                pass
    legacy = (stream.get("tags") or {}).get("rotate")
    if legacy is not None:
        try:
            rotation = int(legacy)
        except (TypeError, ValueError):
            pass
    return rotation % 360


def probe_video(path: str | Path) -> VideoInfo:
    """Probe a file with ffprobe; raise ``ProbeError`` if it isn't a sane video."""
    cmd = [
        _tool("ffprobe"),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProbeError(proc.stderr.strip()[-300:] or "ffprobe failed")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe produced unreadable output") from exc

    streams = data.get("streams") or []
    # Skip attached_pic streams (embedded cover art masquerading as video).
    video_streams = [
        s
        for s in streams
        if s.get("codec_type") == "video"
        and not int(s.get("disposition", {}).get("attached_pic", 0) or 0)
    ]
    if not video_streams:
        raise ProbeError("no video stream found")
    v = video_streams[0]
    fmt = data.get("format") or {}

    width = int(v.get("width") or 0)
    height = int(v.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ProbeError("video stream has no dimensions")
    # Portrait phone video: decoders auto-rotate, so display dims are swapped.
    if _rotation_degrees(v) % 180 == 90:
        width, height = height, width

    fps = _parse_rate(v.get("avg_frame_rate")) or _parse_rate(v.get("r_frame_rate"))
    if fps is None:
        raise ProbeError("video stream has no frame rate")

    duration = _parse_float(v.get("duration")) or _parse_float(fmt.get("duration"))
    if duration is None:
        raise ProbeError("video has no duration")

    nb_frames = str(v.get("nb_frames") or "")
    frames = int(nb_frames) if nb_frames.isdigit() and int(nb_frames) > 0 else max(
        1, round(duration * fps)
    )

    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    audio_codec = str(audio_streams[0].get("codec_name")) if audio_streams else None

    return VideoInfo(
        width=width,
        height=height,
        duration_seconds=duration,
        fps=fps,
        frames_estimate=frames,
        container=str(fmt.get("format_name", "")),
        codec=str(v.get("codec_name", "")),
        has_audio=bool(audio_streams),
        audio_codec=audio_codec,
    )


def run_ffmpeg(args: list[str], *, on_frame: Callable[[int], None] | None = None) -> None:
    """Run ffmpeg with the given args, optionally reporting encoded-frame counts.

    ``on_frame`` receives the running frame count parsed from ``-progress``
    output. stderr is spooled to a temp file (never a pipe) so a chatty run can
    never deadlock; a tail of it is raised in ``FfmpegError`` on failure.
    """
    cmd = [_tool("ffmpeg"), "-hide_banner", "-y", "-v", "error", "-nostats"]
    if on_frame is not None:
        cmd += ["-progress", "pipe:1"]
    cmd += args

    with tempfile.TemporaryFile() as errf:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=errf,
            text=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            if on_frame is not None and line.startswith("frame="):
                try:
                    on_frame(int(line.split("=", 1)[1].strip()))
                except ValueError:
                    pass
        code = proc.wait()
        if code != 0:
            errf.seek(0)
            tail = errf.read().decode(errors="replace").strip()[-500:]
            raise FfmpegError(f"ffmpeg exited with {code}: {tail}")
