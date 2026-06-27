"""Unit tests for token extraction and account authorization policy."""

from __future__ import annotations

import pytest
from app.auth import authorize_claims, extract_bearer, verify_and_authorize
from app.config import Settings
from app.errors import ApiError, ErrorCode

from tests.conftest import APPROVED_EMAIL, APPROVED_SUB, FakeVerifier


def _settings(**kw) -> Settings:
    base = dict(
        google_web_client_id="c",
        allowed_google_email=APPROVED_EMAIL,
        allowed_google_sub="",
    )
    base.update(kw)
    return Settings(**base)


def test_extract_bearer_ok():
    assert extract_bearer("Bearer abc.def") == "abc.def"


@pytest.mark.parametrize("header", [None, "", "Token x", "Bearer ", "Bearer    "])
def test_extract_bearer_rejects_bad_headers(header):
    with pytest.raises(ApiError) as exc:
        extract_bearer(header)
    assert exc.value.code == ErrorCode.AUTH_REQUIRED


def test_authorize_approved_account():
    claims = {"sub": APPROVED_SUB, "email": APPROVED_EMAIL, "email_verified": True}
    assert authorize_claims(claims, _settings()) is claims


def test_authorize_rejects_unverified_email():
    claims = {"sub": "x", "email": APPROVED_EMAIL, "email_verified": False}
    with pytest.raises(ApiError) as exc:
        authorize_claims(claims, _settings())
    assert exc.value.code == ErrorCode.ACCOUNT_NOT_ALLOWED


def test_authorize_rejects_wrong_email():
    claims = {"sub": "x", "email": "someone@else.com", "email_verified": True}
    with pytest.raises(ApiError) as exc:
        authorize_claims(claims, _settings())
    assert exc.value.code == ErrorCode.ACCOUNT_NOT_ALLOWED


def test_authorize_email_is_case_insensitive():
    claims = {"sub": "x", "email": APPROVED_EMAIL.upper(), "email_verified": True}
    assert authorize_claims(claims, _settings())["sub"] == "x"


def test_authorize_pins_to_stable_sub_when_configured():
    settings = _settings(allowed_google_sub=APPROVED_SUB)
    good = {"sub": APPROVED_SUB, "email": APPROVED_EMAIL, "email_verified": True}
    assert authorize_claims(good, settings)["sub"] == APPROVED_SUB

    bad = {"sub": "different", "email": APPROVED_EMAIL, "email_verified": True}
    with pytest.raises(ApiError) as exc:
        authorize_claims(bad, settings)
    assert exc.value.code == ErrorCode.ACCOUNT_NOT_ALLOWED


def test_verify_and_authorize_end_to_end():
    claims = verify_and_authorize("Bearer approved", FakeVerifier(), _settings())
    assert claims["email"] == APPROVED_EMAIL


def test_verify_and_authorize_rejects_unknown_token():
    with pytest.raises(ApiError) as exc:
        verify_and_authorize("Bearer nope", FakeVerifier(), _settings())
    assert exc.value.code == ErrorCode.AUTH_REQUIRED
