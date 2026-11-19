from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no timezone support; schemas add the tz back)."""
    return datetime.now(UTC).replace(tzinfo=None)


# Columns added after the first release: (table, column, SQL that adds it)
_LATE_COLUMNS = [
    (
        "users",
        "google_sub",
        [
            "ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)",
        ],
    ),
    ("complaints", "reopen_count", ["ALTER TABLE complaints ADD COLUMN reopen_count INTEGER NOT NULL DEFAULT 0"]),
]


def add_missing_columns() -> None:
    """Stopgap until Alembic (Phase 3): upgrade databases created before a column existed.
    create_all() only creates missing tables, never missing columns."""
    inspector = inspect(engine)
    for table, column, statements in _LATE_COLUMNS:
        if column in {c["name"] for c in inspector.get_columns(table)}:
            continue
        with engine.begin() as conn:
            for sql in statements:
                conn.exec_driver_sql(sql)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
