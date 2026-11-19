"""Priority score: higher = handle first. Officer queues sort by this, then oldest first.

score = 20 x severity (citizen, 1-4)
      + 10 x urgency  (from the text, 1-3)
      +  5 x category weight (0-2, e.g. live wires > noise)
      +  3 x "Me too" votes, capped at 30
      + 10 x times the citizen reopened it (the fix didn't work)
"""

from app.models import Severity

SEVERITY_POINTS = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}
MAX_UPVOTE_POINTS = 30
REOPEN_POINTS = 10


def compute_priority(severity: str, urgency: int, category_weight: int, upvotes: int, reopens: int = 0) -> int:
    return (
        20 * SEVERITY_POINTS.get(Severity(severity), 2)
        + 10 * urgency
        + 5 * category_weight
        + min(3 * upvotes, MAX_UPVOTE_POINTS)
        + REOPEN_POINTS * reopens
    )


def priority_label(score: int) -> str:
    if score >= 100:
        return "P1"
    if score >= 75:
        return "P2"
    if score >= 55:
        return "P3"
    return "P4"
