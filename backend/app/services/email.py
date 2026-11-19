"""Citizen notification emails, sent over SMTP from a FastAPI BackgroundTask.

Messages are built inside the request (where the DB session is open) and only
plain strings are handed to the background task. Without SMTP credentials the
email is printed to the console, so the app works without a Gmail account.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape

import certifi
from fastapi import BackgroundTasks

from app.config import settings
from app.models import Complaint, User

log = logging.getLogger("app.email")


@dataclass
class Email:
    to: str
    subject: str
    text: str
    html: str


def send_email(email: Email) -> None:
    to = settings.email_override_to or email.to
    if not settings.email_enabled:
        log.info("[email not configured, printing instead]\nTo: %s\nSubject: %s\n\n%s", to, email.subject, email.text)
        return
    msg = EmailMessage()
    msg["From"] = settings.email_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = email.subject
    msg.set_content(email.text)
    msg.add_alternative(email.html, subtype="html")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls(context=ssl.create_default_context(cafile=certifi.where()))
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        log.info("Sent '%s' to %s", email.subject, to)
    except Exception:  # Phase 3: retry + email log table
        log.exception("Failed to send '%s' to %s", email.subject, to)


def queue(background: BackgroundTasks, email: Email) -> None:
    background.add_task(send_email, email)


# ---------------------------------------------------------------- templates

def _ticket_link(c: Complaint) -> str:
    return f"{settings.frontend_url.rstrip('/')}/complaints/{c.ticket_no}"


def _routing_lines(c: Complaint) -> list[tuple[str, str]]:
    return [
        ("Ticket", c.ticket_no),
        ("Category", c.category.name if c.category else "Being reviewed"),
        ("Department", c.department.name if c.department else "Being reviewed"),
        ("Ward", c.ward.name if c.ward else "Being reviewed"),
    ]


def _build(
    c: Complaint,
    subject: str,
    intro: str,
    rows: list[tuple[str, str]],
    outro: str = "",
    to: User | None = None,  # default: the citizen who filed it
    link: str | None = None,
    button: str = "Track your complaint",
) -> Email:
    to = to or c.citizen
    link = link or _ticket_link(c)
    text_rows = "\n".join(f"{k}: {v}" for k, v in rows)
    text = f"Hello {to.name},\n\n{intro}\n\n{text_rows}\n\n{outro}\n{button}: {link}\n\nGrievance Portal"
    html_rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#64748b">{escape(k)}</td>'
        f'<td style="padding:4px 0;font-weight:600">{escape(v)}</td></tr>'
        for k, v in rows
    )
    html = f"""\
<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">
  <div style="background:#1d4ed8;color:#fff;padding:16px 20px;font-size:18px;font-weight:bold">Grievance Portal</div>
  <div style="padding:20px;color:#0f172a;font-size:14px;line-height:1.5">
    <p>Hello {escape(to.name)},</p>
    <p>{escape(intro)}</p>
    <table style="border-collapse:collapse;margin:12px 0">{html_rows}</table>
    {f"<p>{escape(outro)}</p>" if outro else ""}
    <p><a href="{escape(link)}" style="background:#1d4ed8;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;display:inline-block">{escape(button)}</a></p>
  </div>
</div>"""
    return Email(to=to.email, subject=f"[{c.ticket_no}] {subject}", text=text, html=html)


def complaint_received(c: Complaint) -> Email:
    if c.status == "TRIAGE":
        intro = "We received your complaint. Our team is reviewing it and will route it to the right department shortly."
    else:
        intro = "We received your complaint and routed it to the department below."
    return _build(c, "Complaint received", intro, _routing_lines(c))


def complaint_routed(c: Complaint) -> Email:
    return _build(c, "Complaint routed", "Your complaint has been reviewed and routed to the department below.", _routing_lines(c))


def officer_assigned(c: Complaint, officer: User) -> Email:
    rows = [
        ("Ticket", c.ticket_no),
        ("Officer", officer.name),
        ("Officer email", officer.email),
        ("Department", c.department.name if c.department else "-"),
    ]
    if officer.phone:
        rows.append(("Officer phone", officer.phone))
    return _build(c, "Officer assigned", "An officer has picked up your complaint.", rows)


def status_changed(c: Complaint) -> Email:
    if c.status == "IN_PROGRESS":
        return _build(c, "Work in progress", "Work on your complaint has started.", [("Ticket", c.ticket_no), ("Status", "In progress")])
    return _build(
        c,
        "Complaint rejected",
        "Your complaint was closed without action for the reason below.",
        [("Ticket", c.ticket_no), ("Status", "Rejected"), ("Reason", c.rejection_reason or "-")],
        "If you think this is a mistake, please file a new complaint with more details.",
    )


def resolved(c: Complaint) -> Email:
    rows = [("Ticket", c.ticket_no), ("Status", "Resolved")]
    if c.resolution_note:
        rows.append(("Officer's note", c.resolution_note))
    rows.append(("Proof attached", "Yes, see the ticket page" if c.closed_with_proof else "No"))
    return _build(c, "Complaint resolved", "Good news: your complaint has been marked as resolved.", rows)


def reopened_citizen(c: Complaint, reason: str, officer: User | None) -> Email:
    where = f"Back with {officer.name}" if officer else "Back in the department queue"
    return _build(
        c,
        "Complaint reopened",
        "You reopened your complaint. It has been sent back for another fix.",
        [("Ticket", c.ticket_no), ("Status", where), ("Your reason", reason)],
    )


def reopened_officer(c: Complaint, reason: str, officer: User) -> Email:
    link = f"{settings.frontend_url.rstrip('/')}/officer/tickets/{c.ticket_no}"
    return _build(
        c,
        "Reopened by the citizen",
        "A complaint you resolved was reopened: the citizen says the problem is not fixed.",
        [
            ("Ticket", c.ticket_no),
            ("Category", c.category.name if c.category else "-"),
            ("Citizen's reason", reason),
            ("Times reopened", str(c.reopen_count)),
        ],
        "It is back in your queue with a higher priority.",
        to=officer,
        link=link,
        button="Open the ticket",
    )
