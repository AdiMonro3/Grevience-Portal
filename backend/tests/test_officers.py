"""Admin: add, list, move and deactivate officers."""

import itertools

import pytest

ADMIN = "admin@gp.demo"
_n = itertools.count(1)


@pytest.fixture(scope="module")
def ids(client):
    depts = {d["code"]: d["id"] for d in client.get("/departments").json()}
    wards = {w["code"]: w["id"] for w in client.get("/wards").json()}
    return depts, wards


@pytest.fixture
def new_officer(client, auth, ids):
    """Create a sewer officer for ward 4; returns (officer JSON, their auth header)."""
    depts, wards = ids
    email = f"new.officer{next(_n)}@gp.demo"
    r = client.post(
        "/admin/officers",
        headers=auth(ADMIN),
        json={"name": "New Officer", "email": email, "password": "secret1", "department_id": depts["SEWER"], "ward_id": wards["W4"]},
    )
    assert r.status_code == 201, r.text
    token = client.post("/auth/login", data={"username": email, "password": "secret1"}).json()["access_token"]
    return r.json(), {"Authorization": f"Bearer {token}"}


def test_new_officer_can_log_in_and_sees_the_ward_queue(client, auth, submit, new_officer):
    officer, headers = new_officer
    assert officer["department"]["code"] == "SEWER" and officer["ward"]["code"] == "W4"
    assert officer["is_active"] and officer["open_tickets"] == 0
    ticket = submit()["ticket_no"]
    assert ticket in [q["ticket_no"] for q in client.get("/officer/queue", headers=headers).json()]


def test_create_officer_validation(client, auth, ids):
    depts, wards = ids
    body = {"name": "Dup", "email": "sewer.w4@gp.demo", "password": "secret1", "department_id": depts["SEWER"], "ward_id": wards["W4"]}
    assert client.post("/admin/officers", headers=auth(ADMIN), json=body).status_code == 409
    assert client.post("/admin/officers", headers=auth(ADMIN), json={**body, "email": "x1@gp.demo", "ward_id": 9999}).status_code == 400
    assert client.post("/admin/officers", headers=auth(ADMIN), json={**body, "email": "x2@gp.demo", "password": "123"}).status_code == 422
    assert client.post("/admin/officers", headers=auth("citizen1@gp.demo"), json={**body, "email": "x3@gp.demo"}).status_code == 403
    assert client.post("/admin/officers", headers=auth("sewer.w4@gp.demo"), json={**body, "email": "x4@gp.demo"}).status_code == 403


def test_list_officers_with_filters_and_ticket_counts(client, auth, ids, submit, new_officer):
    depts, wards = ids
    officer, headers = new_officer
    ticket = submit()["ticket_no"]
    client.post(f"/officer/complaints/{ticket}/pick", headers=headers)

    everyone = client.get("/admin/officers", headers=auth(ADMIN)).json()
    assert len(everyone) >= 32
    w4_sewer = client.get("/admin/officers", headers=auth(ADMIN), params={"ward_id": wards["W4"], "department_id": depts["SEWER"]}).json()
    assert {o["ward"]["code"] for o in w4_sewer} == {"W4"} and {o["department"]["code"] for o in w4_sewer} == {"SEWER"}
    assert next(o for o in w4_sewer if o["id"] == officer["id"])["open_tickets"] == 1


def test_deactivating_returns_tickets_and_locks_the_officer_out(client, auth, submit, new_officer):
    officer, headers = new_officer
    ticket = submit()["ticket_no"]
    assert client.post(f"/officer/complaints/{ticket}/pick", headers=headers).json()["status"] == "ASSIGNED"

    r = client.patch(f"/admin/officers/{officer['id']}", headers=auth(ADMIN), json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False and r.json()["open_tickets"] == 0

    c = client.get(f"/complaints/{ticket}", headers=auth(ADMIN)).json()
    assert c["status"] == "OPEN" and c["assigned_officer"] is None
    assert c["history"][-1]["note"] == "Returned to queue: officer deactivated"

    assert client.get("/officer/queue", headers=headers).status_code == 401  # existing session ends
    login = client.post("/auth/login", data={"username": officer["email"], "password": "secret1"})
    assert login.status_code == 403

    client.patch(f"/admin/officers/{officer['id']}", headers=auth(ADMIN), json={"is_active": True})
    assert client.post("/auth/login", data={"username": officer["email"], "password": "secret1"}).status_code == 200


def test_moving_an_officer_changes_their_queue(client, auth, ids, submit, new_officer):
    depts, wards = ids
    officer, headers = new_officer
    w4_ticket = submit()["ticket_no"]
    client.post(f"/officer/complaints/{w4_ticket}/pick", headers=headers)

    r = client.patch(f"/admin/officers/{officer['id']}", headers=auth(ADMIN), json={"ward_id": wards["W1"]})
    assert r.json()["ward"]["code"] == "W1"
    assert client.get(f"/complaints/{w4_ticket}", headers=auth(ADMIN)).json()["status"] == "OPEN"
    queue = client.get("/officer/queue", headers=headers).json()
    assert all(q["ward"]["code"] == "W1" for q in queue)
    assert client.get(f"/officer/complaints/{w4_ticket}", headers=headers).status_code == 404


def test_update_validation(client, auth, new_officer):
    officer, _ = new_officer
    assert client.patch(f"/admin/officers/{officer['id']}", headers=auth(ADMIN), json={"ward_id": 9999}).status_code == 400
    citizen_id = client.get("/auth/me", headers=auth("citizen1@gp.demo")).json()["id"]
    assert client.patch(f"/admin/officers/{citizen_id}", headers=auth(ADMIN), json={"is_active": False}).status_code == 404
