"""SLA due dates: created_at + the category's sla_hours, overdue while still open."""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Complaint
from tests.conftest import CONNAUGHT_PLACE


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def backdate(ticket: str, days: int) -> None:
    with SessionLocal() as db:
        c = db.scalar(select(Complaint).where(Complaint.ticket_no == ticket))
        c.created_at -= timedelta(days=days)
        db.commit()


def queue_item(client, auth, ticket):
    queue = client.get("/officer/queue", headers=auth("sewer.w4@gp.demo")).json()
    return next(q for q in queue if q["ticket_no"] == ticket)


def test_due_date_comes_from_the_category_sla(client, submit):
    c = submit()  # sewer overflow: 24 h
    assert parse(c["due_at"]) - parse(c["created_at"]) == timedelta(hours=24)
    assert c["overdue"] is False


def test_overdue_while_open_but_not_after_resolving(client, auth, submit):
    ticket = submit()["ticket_no"]
    backdate(ticket, days=2)
    assert queue_item(client, auth, ticket)["overdue"] is True

    officer = auth("sewer.w4@gp.demo")
    client.post(f"/officer/complaints/{ticket}/pick", headers=officer)
    client.post(f"/officer/complaints/{ticket}/resolve", headers=officer, data={"note": "Done"})
    assert queue_item(client, auth, ticket)["overdue"] is False


def test_triage_tickets_have_no_due_date_until_routed(client, auth, submit):
    c = submit(where=CONNAUGHT_PLACE)
    assert c["due_at"] is None and c["overdue"] is False
