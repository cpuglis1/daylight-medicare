"""Explicit service settings. Never discover or copy the applications' .env files."""
from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    archive_root: Path
    service_token: str = field(default="", repr=False)
    cursor_secret: str = field(default="", repr=False)
    statement_timeout_ms: int = 1500

    @classmethod
    def from_env(cls):
        return cls(database_url=os.environ["DAYLIGHT_DATA_DATABASE_URL"],
                   archive_root=Path(os.environ["DAYLIGHT_DATA_ARCHIVE_ROOT"]),
                   service_token=os.environ.get("DAYLIGHT_DATA_SERVICE_TOKEN", ""),
                   cursor_secret=os.environ.get("DAYLIGHT_DATA_CURSOR_SECRET", ""))
