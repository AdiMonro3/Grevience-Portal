"""Shared test setup.

Every test run gets a throwaway SQLite database and media folder, a fake Google
client ID, and no real emails (they are captured in `outbox` instead). The env
vars must be set before `app` is imported, because settings are read at import.
"""

import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="gp-tests-"))
os.environ.update(
    DATABASE_URL=f"sqlite:///{_TMP / 'test.db'}",
    MEDIA_DIR=str(_TMP / "media"),
    GOOGLE_CLIENT_ID="test-client.apps.googleusercontent.com",
    # Override anything in backend/.env so tests never send real mail
    SMTP_USER="",
    SMTP_PASSWORD="",
    EMAIL_OVERRIDE_TO="",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import PASSWORD, reset_db, seed_base  # noqa: E402
from app.services import email as email_service  # noqa: E402

PARI_CHOWK = (28.466, 77.509)  # inside ward W4
CONNAUGHT_PLACE = (28.6315, 77.2167)  # outside every ward
SEWER_TEXT = (
    "Hamari gali mein naali band ho gayi hai, ganda paani ghar ke andar aa raha hai, bacche bimar ho rahe hain"
)


@pytest.fixture(scope="session")
def client():
    """The API with the base seed: 8 departments, 17 categories, 4 wards, 32 officers,
    admin@gp.demo, citizen1/2@gp.demo. No demo complaints; tests create their own."""
    reset_db()
    with SessionLocal() as db:
        seed_base(db)
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def auth(client):
    """auth("sewer.w4@gp.demo") -> Authorization header for that seeded user."""
    tokens: dict[str, dict] = {}

    def _auth(email: str) -> dict:
        if email not in tokens:
            r = client.post("/auth/login", data={"username": email, "password": PASSWORD})
            assert r.status_code == 200, r.text
            tokens[email] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return tokens[email]

    return _auth


@pytest.fixture
def outbox(monkeypatch):
    """Emails the API would have sent during the test."""
    sent = []
    monkeypatch.setattr(email_service, "send_email", sent.append)
    return sent


@pytest.fixture
def submit(client, auth):
    """submit(text, ...) -> the created complaint (JSON), filed by citizen1 by default."""

    def _submit(text=SEWER_TEXT, severity="high", where=PARI_CHOWK, user="citizen1@gp.demo"):
        r = client.post(
            "/complaints",
            headers=auth(user),
            data={"description": text, "severity": severity, "lat": where[0], "lng": where[1], "address": "Test lane"},
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _submit


@pytest.fixture
def resolved_ticket(client, auth, submit):
    """A sewer complaint in ward 4, picked up and resolved by sewer.w4."""
    ticket = submit()["ticket_no"]
    officer = auth("sewer.w4@gp.demo")
    assert client.post(f"/officer/complaints/{ticket}/pick", headers=officer).status_code == 200
    r = client.post(f"/officer/complaints/{ticket}/resolve", headers=officer, data={"note": "Drain cleaned"})
    assert r.status_code == 200, r.text
    return ticket
