from enum import StrEnum


class Role(StrEnum):
    CITIZEN = "citizen"
    OFFICER = "officer"
    ADMIN = "admin"


class Status(StrEnum):
    TRIAGE = "TRIAGE"  # ML unsure or location outside every ward -> admin routes it
    OPEN = "OPEN"  # routed to a department + ward, waiting for an officer
    ASSIGNED = "ASSIGNED"  # an officer picked it up
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


ACTIVE_STATUSES = (Status.TRIAGE, Status.OPEN, Status.ASSIGNED, Status.IN_PROGRESS)
CLOSED_STATUSES = (Status.RESOLVED, Status.REJECTED)


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MediaKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"


class MediaPurpose(StrEnum):
    REPORT = "report"  # attached by the citizen
    PROOF = "proof"  # attached by the officer when resolving
