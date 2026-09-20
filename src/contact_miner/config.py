from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, comments ignored, existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key and value and key not in os.environ:
            os.environ[key] = value


def _resolve(base: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


@dataclass(frozen=True)
class Settings:
    root: Path
    db_path: Path
    raw_dir: Path
    output_dir: Path
    relevance_threshold: float = 2.0
    llm_model: str = "gpt-4o-mini"
    owner_emails: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_root(cls, root: Path | None = None) -> "Settings":
        base = (root or Path.cwd()).resolve()
        load_dotenv(base / ".env")
        owners = {value.strip().lower() for value in os.getenv("OWNER_EMAILS", "").split(",") if value.strip()}
        return cls(
            root=base,
            db_path=_resolve(base, os.getenv("CONTACT_MINER_DB", "data/processed/contacts.sqlite3")),
            raw_dir=base / "data/raw",
            output_dir=base / "data/output",
            relevance_threshold=float(os.getenv("RELEVANCE_THRESHOLD", "2.0")),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            owner_emails=frozenset(owners),
        )

    def ensure_directories(self) -> None:
        for path in (self.db_path.parent, self.raw_dir, self.output_dir, self.root / "data/processed"):
            path.mkdir(parents=True, exist_ok=True)
