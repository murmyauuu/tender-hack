from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("var/app.sqlite")
    allowed_origin: str = "http://127.0.0.1:5173"
    cookie_secure: bool = False
    is_demo: bool = False
    auto_worker: bool = True
    ollama_url: str = "http://127.0.0.1:11434"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            db_path=Path(os.getenv("TENDERHACK_DB_PATH", "var/app.sqlite")),
            allowed_origin=os.getenv(
                "TENDERHACK_ALLOWED_ORIGIN", "http://127.0.0.1:5173"
            ),
            cookie_secure=os.getenv("TENDERHACK_COOKIE_SECURE", "false").lower()
            == "true",
            is_demo=os.getenv("TENDERHACK_IS_DEMO", "false").lower() == "true",
            auto_worker=os.getenv("TENDERHACK_AUTO_WORKER", "true").lower() == "true",
            ollama_url=os.getenv("TENDERHACK_OLLAMA_URL", "http://127.0.0.1:11434"),
        )
