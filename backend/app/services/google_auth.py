"""Verify the ID token that Google's "Sign in with Google" button hands the browser.

The frontend gets a signed JWT (the "credential") from Google and posts it to
POST /auth/google. Here we check Google's signature with Google's public keys,
the audience (our client ID), the issuer and expiry. No client secret is needed.
"""

import logging

from fastapi import HTTPException, status
from google.auth import exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings

log = logging.getLogger(__name__)

_transport = google_requests.Request()  # reuses one HTTP session for Google's key downloads


def verify_google_credential(credential: str) -> dict:
    """Return the verified token claims (sub, email, name, ...) or raise an HTTP error."""
    if not settings.google_client_id:
        # Never verify without an audience: any Google token for any app would pass
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured on this server")
    try:
        claims = id_token.verify_oauth2_token(
            credential, _transport, settings.google_client_id, clock_skew_in_seconds=10
        )
    except exceptions.TransportError:
        log.exception("Could not download Google's signing keys")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not reach Google. Please try again.")
    except (ValueError, exceptions.GoogleAuthError) as e:
        log.info("Rejected Google credential: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google sign-in failed. Please try again.")

    if not claims.get("email") or not claims.get("email_verified"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your Google account has no verified email address")
    return claims
