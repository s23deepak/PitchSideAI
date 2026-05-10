"""File-backed live session persistence for multi-replica deployments.

The backend still keeps hot objects such as WebSockets and QARunner in memory,
but serializable session state is mirrored to disk so another replica can pick
up notes, settings, language, and latest vision context.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from models.notes_store import NotesStore


DEFAULT_SESSION_DIR = ".pitchai_sessions"


class SessionPersistence:
    """Small JSON persistence adapter for session-scoped backend state."""

    def __init__(self, root_dir: Optional[str] = None) -> None:
        self.root_dir = Path(root_dir or os.getenv("PITCHAI_SESSION_STORE_DIR", DEFAULT_SESSION_DIR))

    def save_notes(self, match_session: str, notes_store: NotesStore) -> None:
        notes_store.save_json(self._path(match_session, "notes.json"))

    def load_notes(self, match_session: str) -> Optional[NotesStore]:
        path = self._path(match_session, "notes.json")
        if not path.exists():
            return None
        try:
            return NotesStore.load_json(path)
        except Exception:
            return None

    def save_value(self, match_session: str, name: str, value: Any) -> None:
        path = self._path(match_session, f"{name}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")

    def load_value(self, match_session: str, name: str, default: Any = None) -> Any:
        path = self._path(match_session, f"{name}.json")
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _path(self, match_session: str, filename: str) -> Path:
        safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "_", match_session).strip("_")
        return self.root_dir / (safe_session or "active_match") / filename
