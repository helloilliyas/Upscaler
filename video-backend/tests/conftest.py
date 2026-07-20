"""Shared test fixtures: an app wired with in-memory stores, a fake verifier,
and ffmpeg-generated synthetic clips.

The whole suite requires the ffmpeg/ffprobe binaries (installed in CI); tests
skip cleanly when they are absent.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from app.auth import TokenVerifier
from app.config import Settings
from app.errors import ApiError, ErrorCode
from app.main import create_app
from app.storage import InMemoryMetadataStore, LocalFileStore
from fastapi.testclient import TestClient

APPROVED_EMAIL = "approved@example.com"
APPROVED_SUB = "sub-approved-123"

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")

# Token -> claims table the fake verifier returns. The Authorization header in a
# test is `Bearer <token>` where <token> is one of these keys.
_TOKENS = {
    "approved": {"sub": APPROVED_SUB, "email": APPROVED_EMAIL, "email_verified": True},
    "other": {"sub": "sub-other-999", "email": "intruder@example.com", "email_verified": True},
    "unverified": {"sub": "sub-x", "email": APPROVED_EMAIL, "email_verified": False},
}


class FakeVerifier(TokenVerifier):
    def verify(self, raw_token: str) -> dict:
        claims = _TOKENS.get(raw_token)
        if claims is None:
            raise ApiError(ErrorCode.AUTH_REQUIRED, "Invalid token")
        return dict(claims)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        google_web_client_id="test-client",
        allowed_google_email=APPROVED_EMAIL,
        allowed_google_sub="",
        data_dir=str(tmp_path / "data"),
        max_upload_bytes=20 * 1024 * 1024,
        max_duration_seconds=10.0,
        max_input_pixels=2_100_000,
        max_fps=61.0,
    )


@pytest.fixture
def app(settings):
    return create_app(
        settings=settings,
        verifier=FakeVerifier(),
        files=LocalFileStore(settings.data_dir),
        meta=InMemoryMetadataStore(),
    )


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def auth(token: str = "approved") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_video_bytes(
    duration: float = 1.0,
    size: tuple[int, int] = (64, 48),
    fps: float = 10.0,
    audio: bool = False,
    container: str = "mp4",
    rotate: int = 0,
) -> bytes:
    """Generate a tiny synthetic clip with ffmpeg and return its bytes.

    container: "mp4" (h264), "mkv" (h264 in Matroska), or "avi" (mpeg4, used to
    test container rejection). rotate: degrees stored as a display-matrix
    rotation flag (how phones record portrait video).
    """
    w, h = size
    suffix = f".{container}"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc2=duration={duration}:size={w}x{h}:rate={fps}",
    ]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    if container == "avi":
        cmd += ["-c:v", "mpeg4"]
    else:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-shortest"]

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / f"clip{suffix}"
        subprocess.run(cmd + [str(out)], check=True, capture_output=True)
        if rotate:
            flagged = Path(tmpdir) / f"rotated{suffix}"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-display_rotation", str(rotate),
                    "-i", str(out), "-c", "copy", str(flagged),
                ],
                check=True,
                capture_output=True,
            )
            return flagged.read_bytes()
        return out.read_bytes()


def probe_bytes(data: bytes):
    """Probe video bytes via a temp file; returns app.video_io.VideoInfo."""
    from app.video_io import probe_video

    with tempfile.NamedTemporaryFile(suffix=".bin") as tmp:
        Path(tmp.name).write_bytes(data)
        return probe_video(tmp.name)
