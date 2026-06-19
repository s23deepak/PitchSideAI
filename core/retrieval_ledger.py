"""
Every web fetch, API call, LLM invocation, and scrape gets a permanent log entry.
Nothing escapes the ledger.

Provides: log_fetch(), get_run_summary(), get_source_health(), export_run_audit()
"""
import sqlite3
import json
import uuid
import threading
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import contextmanager

DB_DIR = Path(__file__).parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FetchLogEntry:
    id: str
    run_id: str
    phase: str
    agent_name: str
    source_name: str
    source_tier: int
    query_text: str
    query_params: dict[str, Any]
    started_at: str
    duration_ms: int
    response_bytes: int
    status: str
    error_message: str
    data_completeness: float
    data_quality: float
    placeholder_count: int
    extracted_fields: dict[str, Any]
    source_urls: list[str]
    cache_hit: bool
    retry_count: int
    created_at: str

    @classmethod
    def from_row(cls, row: tuple) -> "FetchLogEntry":
        cols = [
            "id", "run_id", "phase", "agent_name", "source_name",
            "source_tier", "query_text", "query_params", "started_at",
            "duration_ms", "response_bytes", "status", "error_message",
            "data_completeness", "data_quality", "placeholder_count",
            "extracted_fields", "source_urls", "cache_hit", "retry_count", "created_at",
        ]
        d = dict(zip(cols, row))
        d["query_params"] = json.loads(d["query_params"]) if isinstance(d["query_params"], str) else d["query_params"] or {}
        d["extracted_fields"] = json.loads(d["extracted_fields"]) if isinstance(d["extracted_fields"], str) else d["extracted_fields"] or {}
        d["source_urls"] = json.loads(d["source_urls"]) if isinstance(d["source_urls"], str) else d["source_urls"] or []
        d["cache_hit"] = bool(d["cache_hit"])
        return cls(**d)


class RetrievalLedger:
    """Singleton ledger for all retrieval audit logging."""

    _instance: Optional["RetrievalLedger"] = None
    _initialized: bool = False
    _lock = threading.Lock()

    def __new__(cls, db_path: str | None = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str | None = None):
        if self._initialized:
            return
        self._db_path = db_path or str(DB_DIR / "retrieval_ledger.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        self._initialized = True

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retrieval_log (
                    id            TEXT PRIMARY KEY,
                    run_id        TEXT NOT NULL,
                    phase         TEXT NOT NULL,
                    agent_name    TEXT NOT NULL,
                    source_name   TEXT NOT NULL,
                    source_tier   INTEGER NOT NULL DEFAULT 3,
                    query_text    TEXT NOT NULL,
                    query_params  TEXT DEFAULT '{}',
                    started_at    TEXT NOT NULL,
                    duration_ms   INTEGER NOT NULL,
                    response_bytes INTEGER DEFAULT 0,
                    status        TEXT NOT NULL,
                    error_message TEXT DEFAULT '',
                    data_completeness REAL DEFAULT 0.0,
                    data_quality   REAL DEFAULT 0.0,
                    placeholder_count INTEGER DEFAULT 0,
                    extracted_fields TEXT DEFAULT '{}',
                    source_urls    TEXT DEFAULT '[]',
                    cache_hit      INTEGER DEFAULT 0,
                    retry_count    INTEGER DEFAULT 0,
                    created_at     TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_retrieval_run ON retrieval_log(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_retrieval_source ON retrieval_log(source_name, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_retrieval_phase ON retrieval_log(phase, agent_name)")

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def log_fetch(
        self,
        *,
        run_id: str,
        phase: str,
        agent_name: str,
        source_name: str,
        source_tier: int = 3,
        query_text: str,
        query_params: dict[str, Any] | None = None,
        duration_ms: int,
        response_bytes: int = 0,
        status: str = "success",
        error_message: str = "",
        data_completeness: float = 0.0,
        data_quality: float = 0.0,
        placeholder_count: int = 0,
        extracted_fields: dict[str, Any] | None = None,
        source_urls: list[str] | None = None,
        cache_hit: bool = False,
        retry_count: int = 0,
    ) -> str:
        entry_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        created_at = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO retrieval_log
                   (id, run_id, phase, agent_name, source_name, source_tier,
                    query_text, query_params, started_at, duration_ms, response_bytes,
                    status, error_message, data_completeness, data_quality,
                    placeholder_count, extracted_fields, source_urls,
                    cache_hit, retry_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    run_id,
                    phase,
                    agent_name,
                    source_name,
                    source_tier,
                    query_text,
                    json.dumps(query_params or {}),
                    started_at,
                    duration_ms,
                    response_bytes,
                    status,
                    error_message,
                    round(data_completeness, 2),
                    round(data_quality, 2),
                    placeholder_count,
                    json.dumps(extracted_fields or {}),
                    json.dumps(source_urls or []),
                    1 if cache_hit else 0,
                    retry_count,
                    created_at,
                ),
            )
            conn.commit()
        return entry_id

    def get_run_logs(self, run_id: str) -> list[FetchLogEntry]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM retrieval_log WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [FetchLogEntry.from_row(tuple(row)) for row in rows]

    def get_run_summary(self, run_id: str) -> dict[str, Any]:
        logs = self.get_run_logs(run_id)
        if not logs:
            return {"total_fetches": 0, "good": 0, "bad": 0, "marginal": 0, "duration_ms": 0}

        good = sum(1 for entry in logs if entry.status == "success" and entry.data_quality >= 0.6)
        bad = sum(1 for entry in logs if entry.status in {"empty", "error", "timeout", "blocked"} or entry.data_completeness < 0.3)
        marginal = len(logs) - good - bad
        total_duration = sum(entry.duration_ms for entry in logs)

        return {
            "total_fetches": len(logs),
            "good": good,
            "bad": bad,
            "marginal": marginal,
            "duration_ms": total_duration,
            "run_id": run_id,
        }

    def get_source_health(self, run_id: str | None = None) -> dict[str, dict[str, Any]]:
        with self._get_conn() as conn:
            if run_id:
                rows = conn.execute(
                    """SELECT source_name, source_tier,
                              COUNT(*) as total_calls,
                              SUM(CASE WHEN status='success' AND data_quality>=0.6 THEN 1 ELSE 0 END) as good,
                              SUM(CASE WHEN status IN ('empty','error','timeout','blocked') OR data_completeness<0.3 THEN 1 ELSE 0 END) as bad,
                              AVG(data_quality) as avg_quality,
                              AVG(duration_ms) as avg_duration
                       FROM retrieval_log WHERE run_id = ?
                       GROUP BY source_name, source_tier""",
                    (run_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT source_name, source_tier,
                              COUNT(*) as total_calls,
                              SUM(CASE WHEN status='success' AND data_quality>=0.6 THEN 1 ELSE 0 END) as good,
                              SUM(CASE WHEN status IN ('empty','error','timeout','blocked') OR data_completeness<0.3 THEN 1 ELSE 0 END) as bad,
                              AVG(data_quality) as avg_quality,
                              AVG(duration_ms) as avg_duration
                       FROM retrieval_log
                       GROUP BY source_name, source_tier""",
                ).fetchall()

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            src = str(row["source_name"])
            result[src] = {
                "source_tier": int(row["source_tier"]),
                "total_calls": int(row["total_calls"]),
                "good": int(row["good"]),
                "bad": int(row["bad"]),
                "marginal": int(row["total_calls"]) - int(row["good"]) - int(row["bad"]),
                "avg_quality": round(float(row["avg_quality"] or 0.0), 2),
                "avg_duration_ms": round(float(row["avg_duration"] or 0.0)),
            }
        return result

    def export_run_audit(self, run_id: str) -> list[dict[str, Any]]:
        logs = self.get_run_logs(run_id)
        return [{
            "id": entry.id,
            "source": entry.source_name,
            "tier": entry.source_tier,
            "query": entry.query_text[:200],
            "status": entry.status,
            "completeness": entry.data_completeness,
            "quality": entry.data_quality,
            "duration_ms": entry.duration_ms,
            "error": entry.error_message or "",
            "cache_hit": entry.cache_hit,
            "urls": entry.source_urls[:5],
        } for entry in logs]


def get_ledger() -> RetrievalLedger:
    return RetrievalLedger()