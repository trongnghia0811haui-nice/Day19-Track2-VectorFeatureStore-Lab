"""Small, dependency-free project settings loader.

The lab ships a ``.env.example`` and creates ``.env`` during setup, but a
dotenv file is not loaded by Python automatically. Keeping the loader here
means the API, searcher, and scripts all observe the same runtime settings
without adding another dependency to the lite path.
"""
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """Load simple ``KEY=VALUE`` entries without overriding the environment."""
    env_path = path or ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if not key or key in os.environ:
            continue
        try:
            parsed = shlex.split(value, comments=True, posix=True)
            os.environ[key] = parsed[0] if parsed else ""
        except ValueError:
            continue


@dataclass(frozen=True)
class Settings:
    qdrant_mode: str
    qdrant_url: str
    embedding_backend: str
    feast_online_store: str
    feast_offline_store: str

    def summary(self) -> str:
        """Return only non-sensitive settings suitable for startup logs."""
        return (
            f"qdrant_mode={self.qdrant_mode} "
            f"embedding_backend={self.embedding_backend} "
            f"feast_online_store={self.feast_online_store} "
            f"feast_offline_store={self.feast_offline_store}"
        )


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        qdrant_mode=os.getenv("QDRANT_MODE", "memory").strip().lower(),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333").strip(),
        embedding_backend=os.getenv("EMBEDDING_BACKEND", "fastembed").strip().lower(),
        feast_online_store=os.getenv("FEAST_ONLINE_STORE", "sqlite").strip().lower(),
        feast_offline_store=os.getenv("FEAST_OFFLINE_STORE", "file").strip().lower(),
    )
