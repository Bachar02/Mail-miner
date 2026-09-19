from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    db_path: Path
    raw_dir: Path
    output_dir: Path
    relevance_threshold: float = 2.0
    llm_model: str = "gpt-4o-mini"

    @classmethod
    def from_root(cls, root: Path | None = None) -> "Settings":
        base = (root or Path.cwd()).resolve()
        return cls(
            root=base,
            db_path=Path(os.getenv("CONTACT_MINER_DB", base / "data/processed/contacts.sqlite3")),
            raw_dir=base / "data/raw",
            output_dir=base / "data/output",
            relevance_threshold=float(os.getenv("RELEVANCE_THRESHOLD", "2.0")),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        )

    def ensure_directories(self) -> None:
        for path in (self.db_path.parent, self.raw_dir, self.output_dir, self.root / "data/processed"):
            path.mkdir(parents=True, exist_ok=True)
