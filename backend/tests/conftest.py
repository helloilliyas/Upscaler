"""Shared test fixtures: an app wired with in-memory stores and a fake verifier."""

from __future__ import annotations

import io

import pytest
from app.auth import TokenVerifier
from app.config import Settings
from app.errors import ApiError, ErrorCode
from app.main import create_app
from app.storage import InMemoryMetadataStore, LocalFileStore
from fastapi.testclient import TestClient
from PIL import Image

APPROVED_EMAIL = "approved@example.com"
APPROVED_SUB = "sub-approved-123"

# Token -> claims table the fake verifier returns. The Authorization header in a
# test is `Bearer <token>` where <token> is one of these keys.
_TOKENS = {
    "approved": {"sub": APPROVED_SUB, "email": APPROVED_EMAIL, "email_verified": True},
    "approved2": {"sub": APPROVED_SUB, "email": APPROVED_EMAIL, "email_verified": True},
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
        allowed_google_sub="",  # sub pinning off by default; enabled in a dedicated test
        data_dir=str(tmp_path / "data"),
        max_upload_bytes=40 * 1024 * 1024,
        max_input_pixels=50_000_000,
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


def make_image_bytes(
    size: tuple[int, int] = (64, 48), fmt: str = "JPEG", color=(120, 90, 200)
) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_mask_bytes(size: tuple[int, int]) -> bytes:
    mask = Image.new("L", size, 0)
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()
