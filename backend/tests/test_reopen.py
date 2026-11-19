"""Citizen reopen: "the fix didn't work"."""

from datetime import timedelta

from app.db import SessionLocal, utcnow
from app.models import Complaint, User
from sqlalchemy import select

REASON = "Still overflowing, nothing changed"


def detail(client, auth, ticket, user="citizen1@gp.demo"):
    return client.get(f"/complaints/{ticket}", headers=auth(user)).json()


def reopen(client, auth, ticket, reason=REASON, user="citizen1@gp.demo"):
    return client.post(f"/complaints/{ticket}/reopen", headers=auth(user), json={"reason": reason})


def resolve_again(client, auth, ticket):
    r = client.post(f"/officer/complaints/{ticket}/resolve", headers=auth("sewer.w4@gp.demo"), data={"note": "Fixed"})
    assert r.status_code == 200, r.text


def test_reopen_goes_back_to_the_same_officer_with_higher_priority(client, auth, resolved_ticket, outbox):
    before = detail(client, auth, resolved_ticket)
    assert before["status"] == "RESOLVED" and before["can_reopen"]
    outbox.clear()

    r = reopen(client, auth, resolved_ticket)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["status"] == "ASSIGNED"
    assert c["assigned_officer"]["email"] == "sewer.w4@gp.demo"
    assert c["reopen_count"] == 1
    assert c["priority"] == before["priority"] + 10
    assert c["resolved_at"] is None and c["resolution_note"] is None and not c["closed_with_proof"]
    assert not c["can_reopen"]  # not resolved any more
    officer_name = c["assigned_officer"]["name"]
    assert [(h["to_status"], h["note"]) for h in c["history"][-2:]] == [
        ("REOPENED", REASON),
        ("ASSIGNED", f"Sent back to {officer_name}"),
    ]
    assert sorted(m.to for m in outbox) == ["citizen1@gp.demo", "sewer.w4@gp.demo"]

    # Back on the officer's queue, flagged, and they can resolve it again
    queue = client.get("/officer/queue", headers=auth("sewer.w4@gp.demo")).json()
    assert any(q["ticket_no"] == resolved_ticket and q["reopen_count"] == 1 for q in queue)
    resolve_again(client, auth, resolved_ticket)
    assert detail(client, auth, resolved_ticket)["can_reopen"]


def test_only_the_citizen_who_filed_it_can_reopen(client, auth, resolved_ticket):
    assert reopen(client, auth, resolved_ticket, user="citizen2@gp.demo").status_code == 404
    assert reopen(client, auth, resolved_ticket, user="sewer.w4@gp.demo").status_code == 403
    assert reopen(client, auth, resolved_ticket, user="admin@gp.demo").status_code == 403


def test_only_resolved_tickets_can_be_reopened(client, auth, submit):
    ticket = submit()["ticket_no"]
    r = reopen(client, auth, ticket)
    assert r.status_code == 409
    assert "Only resolved" in r.json()["detail"]
    assert not detail(client, auth, ticket)["can_reopen"]


def test_reason_is_required(client, auth, resolved_ticket):
    assert reopen(client, auth, resolved_ticket, reason="  no  ").status_code == 422


def test_reopen_window(client, auth, resolved_ticket):
    with SessionLocal() as db:
        c = db.scalar(select(Complaint).where(Complaint.ticket_no == resolved_ticket))
        c.resolved_at = utcnow() - timedelta(days=15)
        db.commit()
    assert not detail(client, auth, resolved_ticket)["can_reopen"]
    r = reopen(client, auth, resolved_ticket)
    assert r.status_code == 409
    assert "14 days" in r.json()["detail"]


def test_at_most_two_reopens(client, auth, resolved_ticket):
    for _ in range(2):
        assert reopen(client, auth, resolved_ticket).status_code == 200
        resolve_again(client, auth, resolved_ticket)
    assert not detail(client, auth, resolved_ticket)["can_reopen"]
    r = reopen(client, auth, resolved_ticket)
    assert r.status_code == 409
    assert "already reopened 2 times" in r.json()["detail"]


def test_goes_to_the_department_queue_if_the_officer_left(client, auth, resolved_ticket, outbox):
    with SessionLocal() as db:
        officer = db.scalar(select(User).where(User.email == "sewer.w4@gp.demo"))
        officer.is_active = False
        db.commit()
    try:
        outbox.clear()
        c = reopen(client, auth, resolved_ticket).json()
        assert c["status"] == "OPEN"
        assert c["assigned_officer"] is None
        assert c["history"][-1]["note"] == "Back in the department queue"
        assert [m.to for m in outbox] == ["citizen1@gp.demo"]  # no officer to notify
    finally:
        with SessionLocal() as db:
            db.scalar(select(User).where(User.email == "sewer.w4@gp.demo")).is_active = True
            db.commit()


def test_admin_cannot_reroute_a_resolved_ticket(client, auth, resolved_ticket):
    r = client.patch(
        f"/admin/complaints/{resolved_ticket}/assign",
        headers=auth("admin@gp.demo"),
        json={"department_id": 1, "ward_id": 1},
    )
    assert r.status_code == 409
