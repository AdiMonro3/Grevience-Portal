"""Sign-up, password login and Sign in with Google."""

import pytest
from google.auth import exceptions as google_exceptions

from app.services import google_auth


def test_register_creates_account_without_logging_in(client):
    r = client.post("/auth/register", json={"name": "New Citizen", "email": "New@Example.com", "password": "secret1"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert "access_token" not in body
    assert body["email"] == "new@example.com" and body["role"] == "citizen"

    assert client.post("/auth/register", json={"name": "Dup", "email": "new@example.com", "password": "secret1"}).status_code == 409
    r = client.post("/auth/login", data={"username": "new@example.com", "password": "secret1"})
    assert r.status_code == 200 and r.json()["user"]["email"] == "new@example.com"


def test_wrong_password(client):
    assert client.post("/auth/login", data={"username": "citizen1@gp.demo", "password": "nope"}).status_code == 401


def test_providers_exposes_google_client_id(client):
    assert client.get("/auth/providers").json() == {"google_client_id": "test-client.apps.googleusercontent.com"}


# ---------------------------------------------------------------- Google

@pytest.fixture
def google(monkeypatch):
    """Pretend Google verified a token with these claims."""
    claims = {}
    monkeypatch.setattr(
        google_auth.id_token, "verify_oauth2_token", lambda credential, request, audience, clock_skew_in_seconds=0: dict(claims)
    )
    return claims


def google_login(client):
    return client.post("/auth/google", json={"credential": "x" * 40})


def test_google_creates_a_citizen_then_recognises_them(client, google):
    google.update(sub="g-1", email="Someone@Gmail.com", email_verified=True, name="Some One")
    r = google_login(client)
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["role"] == "citizen" and user["email"] == "someone@gmail.com" and user["name"] == "Some One"

    google["email"] = "renamed@gmail.com"  # same Google account, new address
    assert google_login(client).json()["user"]["id"] == user["id"]

    # Google-only accounts have no usable password
    assert client.post("/auth/login", data={"username": "someone@gmail.com", "password": "anything"}).status_code == 401


def test_google_links_an_existing_account_by_email(client, google):
    google.update(sub="g-2", email="citizen2@gp.demo", email_verified=True, name="Ignored")
    r = google_login(client)
    assert r.status_code == 200
    assert r.json()["user"]["name"] == "Priya Verma"
    assert client.post("/auth/login", data={"username": "citizen2@gp.demo", "password": "Demo@123"}).status_code == 200

    google["sub"] = "g-other"  # a different Google account claiming the same email
    assert google_login(client).status_code == 409


def test_google_requires_a_verified_email(client, google):
    google.update(sub="g-3", email="unverified@gmail.com", email_verified=False)
    assert google_login(client).status_code == 401


def test_invalid_google_token_is_rejected(client, monkeypatch):
    # Real verification code, but Google's public keys are faked (no network needed)
    monkeypatch.setattr(google_auth.id_token, "_fetch_certs", lambda request, url: {})
    r = google_login(client)
    assert r.status_code == 401
    assert r.json()["detail"] == "Google sign-in failed. Please try again."


def test_google_unreachable(client, monkeypatch):
    def offline(request, url):
        raise google_exceptions.TransportError("no network")

    monkeypatch.setattr(google_auth.id_token, "_fetch_certs", offline)
    assert google_login(client).status_code == 503


def test_google_not_configured(client, monkeypatch):
    monkeypatch.setattr(google_auth.settings, "google_client_id", "")
    assert client.get("/auth/providers").json() == {"google_client_id": None}
    assert google_login(client).status_code == 503
