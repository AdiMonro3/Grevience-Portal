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


def add_missing_columns() -> None:
    """Stopgap until Alembic (Phase 3): upgrade databases created before a column existed.
    create_all() only creates missing tables, never missing columns."""
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    if "google_sub" not in columns:
        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)")
            conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)")


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
