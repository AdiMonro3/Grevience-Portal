"""App settings, read from environment variables / backend/.env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_name: str = "Grievance Portal API"

    # Database: SQLite for the demo, swap for postgresql+psycopg://... later
    database_url: str = f"sqlite:///{BASE_DIR / 'grievance.db'}"

    # Auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # Frontend
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_url: str = "http://localhost:5173"

    # Uploads
    media_dir: Path = BASE_DIR / "media"
    max_photos: int = 3
    max_photo_mb: int = 5
    max_video_mb: int = 25

    # ML routing
    model_path: Path = BASE_DIR / "app" / "ml" / "model.joblib"
    ml_confidence_threshold: float = 0.5

    # Email (Gmail: smtp.gmail.com:587 + an App Password)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""  # defaults to smtp_user
    email_override_to: str = ""  # demo helper: deliver every email to this inbox

    # Geocoding (OpenStreetMap Nominatim, free, no key)
    geocoder_user_agent: str = "GrievancePortal/0.1 (student project)"

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)


settings = Settings()
