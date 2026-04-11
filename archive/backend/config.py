import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# On Vercel, use /tmp for ephemeral SQLite; locally use data/rpm.db
_default_db = "/tmp/rpm.db" if os.getenv("VERCEL") else str(
    Path(__file__).parent.parent / "data" / "rpm.db"
)


class Settings:
    """Application settings loaded from environment variables."""

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DATABASE_PATH: str = os.getenv("RPM_DATABASE_PATH", _default_db)
    DEBUG: bool = os.getenv("RPM_DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("RPM_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("RPM_PORT", "8000"))


settings = Settings()
