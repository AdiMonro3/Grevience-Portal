"""Phase 1-2 rules: routing, triage, jurisdiction, status changes, priority, Me too."""

from app.services.priority import compute_priority
from tests.conftest import CONNAUGHT_PLACE

SEWER = "sewer.w4@gp.demo"


def test_clear_complaint_is_routed_to_the_right_officer(client, auth, submit, outbox):
    c = submit()
    assert c["status"] == "OPEN"
    assert c["category"]["code"] == "sewer_overflow"
    assert c["department"]["code"] == "SEWER" and c["ward"]["code"] == "W4"
    assert c["ticket_no"].startswith("GRV-")
    assert [h["to_status"] for h in c["history"]] == ["SUBMITTED", "OPEN"]
    assert [m.subject.split("] ")[1] for m in outbox] == ["Complaint received"]

    queue = client.get("/officer/queue", headers=auth(SEWER)).json()
    assert c["ticket_no"] in [q["ticket_no"] for q in queue]


def test_vague_or_out_of_area_complaints_go_to_triage(client, auth, submit):
    vague = submit("Bhai sahab kuch karo yahan, bahut pareshani hai")
    assert vague["status"] == "TRIAGE" and vague["department"] is None
    far = submit(where=CONNAUGHT_PLACE)
    assert far["status"] == "TRIAGE" and far["ward"] is None

    triage = [t["ticket_no"] for t in client.get("/admin/triage", headers=auth("admin@gp.demo")).json()]
    assert {vague["ticket_no"], far["ticket_no"]} <= set(triage)


def test_admin_routes_a_triage_ticket(client, auth, submit, outbox):
    ticket = submit(where=CONNAUGHT_PLACE)["ticket_no"]
    depts = {d["code"]: d["id"] for d in client.get("/departments").json()}
    wards = {w["code"]: w["id"] for w in client.get("/wards").json()}
    r = client.patch(
        f"/admin/complaints/{ticket}/assign",
        headers=auth("admin@gp.demo"),
        json={"department_id": depts["SEWER"], "ward_id": wards["W4"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "OPEN"
    assert outbox[-1].subject == f"[{ticket}] Complaint routed"
    assert ticket in [q["ticket_no"] for q in client.get("/officer/queue", headers=auth(SEWER)).json()]


def test_officers_only_see_their_own_department_and_ward(client, auth, submit):
    ticket = submit()["ticket_no"]
    assert client.get(f"/officer/complaints/{ticket}", headers=auth(SEWER)).status_code == 200
    assert client.get(f"/officer/complaints/{ticket}", headers=auth("roads.w4@gp.demo")).status_code == 404
    assert client.get(f"/officer/complaints/{ticket}", headers=auth("sewer.w1@gp.demo")).status_code == 404
    assert client.post(f"/officer/complaints/{ticket}/pick", headers=auth("sewer.w1@gp.demo")).status_code == 404


def test_citizens_only_see_their_own_tickets(client, auth, submit):
    ticket = submit()["ticket_no"]
    assert client.get(f"/complaints/{ticket}", headers=auth("citizen1@gp.demo")).status_code == 200
    assert client.get(f"/complaints/{ticket}", headers=auth("citizen2@gp.demo")).status_code == 404
    assert client.get("/officer/queue", headers=auth("citizen1@gp.demo")).status_code == 403


def test_full_officer_workflow(client, auth, submit, outbox):
    ticket = submit()["ticket_no"]
    officer = auth(SEWER)

    # Must pick up before changing status
    r = client.patch(f"/officer/complaints/{ticket}/status", headers=officer, json={"status": "IN_PROGRESS"})
    assert r.status_code == 409
    assert client.post(f"/officer/complaints/{ticket}/pick", headers=officer).json()["status"] == "ASSIGNED"
    assert client.patch(f"/officer/complaints/{ticket}/status", headers=officer, json={"status": "IN_PROGRESS"}).json()["status"] == "IN_PROGRESS"

    # Rejecting needs a reason
    assert client.patch(f"/officer/complaints/{ticket}/status", headers=officer, json={"status": "REJECTED"}).status_code == 422

    r = client.post(f"/officer/complaints/{ticket}/resolve", headers=officer, data={"note": "Drain cleaned"})
    c = r.json()
    assert c["status"] == "RESOLVED" and c["resolution_note"] == "Drain cleaned"
    assert [h["to_status"] for h in c["history"]] == ["SUBMITTED", "OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED"]
    subjects = [m.subject.split("] ")[1] for m in outbox]
    assert subjects == ["Complaint received", "Officer assigned", "Work in progress", "Complaint resolved"]

    # Closed tickets can't move again (picking up your own ticket again changes nothing)
    assert client.patch(f"/officer/complaints/{ticket}/status", headers=officer, json={"status": "IN_PROGRESS"}).status_code == 409
    assert client.post(f"/officer/complaints/{ticket}/pick", headers=officer).json()["status"] == "RESOLVED"


def test_priority_formula_and_me_too(client, auth, submit):
    c = submit(severity="high")
    weight = 2  # sewer_overflow
    assert c["priority"] == compute_priority("high", c["urgency"], weight, 0)

    me_too = client.post(f"/complaints/{c['ticket_no']}/upvote", headers=auth("citizen2@gp.demo"))
    assert me_too.json()["priority"] == c["priority"] + 3
    again = client.post(f"/complaints/{c['ticket_no']}/upvote", headers=auth("citizen2@gp.demo"))
    assert again.json()["upvote_count"] == 1  # idempotent
    assert client.post(f"/complaints/{c['ticket_no']}/upvote", headers=auth("citizen1@gp.demo")).status_code == 400


def test_priority_bonus_for_reopens():
    base = compute_priority("medium", 2, 1, 0)
    assert compute_priority("medium", 2, 1, 0, reopens=2) == base + 20
