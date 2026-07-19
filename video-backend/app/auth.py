"""Google ID-token verification.

The verifier is an injectable protocol so unit tests can supply claims without
contacting Google. The real implementation uses ``google.oauth2.id_token`` and
validates signature, issuer, audience, and expiry; the account checks
(email_verified, approved email, stable sub) are applied on top.
"""

from __future__ import annotations

from typing import Protocol

from .config import Settings
from .errors import ApiError, ErrorCode

_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class TokenVerifier(Protocol):
    """Verifies a raw Google ID token and returns its claims, or raises ApiError."""

    def verify(self, raw_token: str) -> dict: ...


class GoogleTokenVerifier:
    """Production verifier backed by google-auth.

    Imports google-auth lazily so the package can be imported (and most tests
    run) without the dependency installed.
    """

    def __init__(self, web_client_id: str) -> None:
        self._audience = web_client_id

    def verify(self, raw_token: str) -> dict:
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ApiError(ErrorCode.INTERNAL_ERROR, "Auth backend unavailable") from exc

        try:
            claims = id_token.verify_oauth2_token(
                raw_token,
                google_requests.Request(),
                self._audience,
            )
        except Exception as exc:
            raise ApiError(ErrorCode.AUTH_REQUIRED, "Invalid or expired Google token") from exc

        if claims.get("iss") not in _GOOGLE_ISSUERS:
            raise ApiError(ErrorCode.AUTH_REQUIRED, "Untrusted token issuer")
        return claims


def extract_bearer(authorization: str | None) -> str:
    """Pull the raw token out of an ``Authorization: Bearer ...`` header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(ErrorCode.AUTH_REQUIRED, "Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise ApiError(ErrorCode.AUTH_REQUIRED, "Missing bearer token")
    return token


def authorize_claims(claims: dict, settings: Settings) -> dict:
    """Apply the account-approval policy to verified token claims.

    Returns the claims on success; raises ``ApiError`` otherwise. Kept separate
    from token verification so it is trivial to unit-test in isolation.
    """
    if claims.get("email_verified") is not True:
        raise ApiError(ErrorCode.ACCOUNT_NOT_ALLOWED, "Google email is not verified")

    email = str(claims.get("email", "")).lower()
    if not settings.allowed_google_email:
        raise ApiError(ErrorCode.INTERNAL_ERROR, "Approved account is not configured")
    if email != settings.allowed_google_email.lower():
        raise ApiError(ErrorCode.ACCOUNT_NOT_ALLOWED, "Google account is not permitted")

    # Once the stable subject is captured, pin to it as well.
    if settings.allowed_google_sub and claims.get("sub") != settings.allowed_google_sub:
        raise ApiError(
            ErrorCode.ACCOUNT_NOT_ALLOWED, "Google account identifier is not permitted"
        )

    if not claims.get("sub"):
        raise ApiError(ErrorCode.AUTH_REQUIRED, "Token missing subject")

    return claims


def verify_and_authorize(
    authorization: str | None, verifier: TokenVerifier, settings: Settings
) -> dict:
    """Full request-auth path: extract -> verify signature -> approve account."""
    raw = extract_bearer(authorization)
    claims = verifier.verify(raw)
    return authorize_claims(claims, settings)
