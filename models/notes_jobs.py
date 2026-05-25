"""Persistent commentary-notes job state and results."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from config import DATABASE_URL
from models.notes_store import NotesStore


class NotesJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MatchScheduleStatus(str, Enum):
    SCHEDULED = "scheduled"
    NOTES_QUEUED = "notes_queued"
    NOTES_RUNNING = "notes_running"
    NOTES_READY = "notes_ready"
    LIVE = "live"
    COMPLETE = "complete"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


class MatchSchedule(Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_kickoff_status", "kickoff_at", "status"),
        UniqueConstraint("match_session", name="uq_matches_match_session"),
    )

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_session: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    sport: Mapped[str] = mapped_column(String(40), nullable=False, default="soccer")
    competition: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    kickoff_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    venue_lat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    venue_lon: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=MatchScheduleStatus.SCHEDULED.value)
    notes_job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    notes_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vlm_context_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_notes_update_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotesJob(Base):
    __tablename__ = "notes_jobs"
    __table_args__ = (Index("ix_notes_jobs_match_session_status", "match_session", "status"),)

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_session: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    sport: Mapped[str] = mapped_column(String(40), nullable=False, default="soccer")
    competition: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    match_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=NotesJobStatus.QUEUED.value)
    phase: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class NotesResult(Base):
    __tablename__ = "notes_results"

    job_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("notes_jobs.job_id", ondelete="CASCADE"),
        primary_key=True,
    )
    match_session: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    markdown_notes: Mapped[str] = mapped_column(Text, nullable=False)
    notes_store_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    beat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preparation_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    notes_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    vlm_context_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    vlm_context_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotesVersion(Base):
    __tablename__ = "notes_versions"
    __table_args__ = (
        Index("ix_notes_versions_match_active", "match_id", "active"),
        Index("ix_notes_versions_session_version", "match_session", "notes_version"),
    )

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    match_session: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    notes_version: Mapped[int] = mapped_column(Integer, nullable=False)
    vlm_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    update_type: Mapped[str] = mapped_column(String(32), nullable=False, default="prematch")
    source_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    markdown_notes: Mapped[str] = mapped_column(Text, nullable=False)
    notes_store_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    vlm_context_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LiveMatchEvent(Base):
    __tablename__ = "live_match_events"
    __table_args__ = (
        UniqueConstraint("match_id", "idempotency_key", name="uq_live_event_idempotency"),
        Index("ix_live_events_match_created", "match_id", "created_at"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    match_session: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_notes_job_db() -> None:
    """Create notes job tables when migrations have not run yet."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await _upgrade_existing_notes_tables(conn)


async def _upgrade_existing_notes_tables(conn) -> None:
    """Best-effort compatibility migration until Alembic owns these tables."""
    statements = [
        "ALTER TABLE notes_jobs ADD COLUMN IF NOT EXISTS match_id VARCHAR(64)",
        "ALTER TABLE notes_jobs ADD COLUMN IF NOT EXISTS competition VARCHAR(160) NOT NULL DEFAULT ''",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS competition VARCHAR(160) NOT NULL DEFAULT ''",
        "ALTER TABLE notes_jobs ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE notes_jobs ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255)",
        "ALTER TABLE notes_results ADD COLUMN IF NOT EXISTS notes_version INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE notes_results ADD COLUMN IF NOT EXISTS vlm_context_version INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE notes_results ADD COLUMN IF NOT EXISTS vlm_context_json JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS notes_version INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS vlm_context_version INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS last_notes_update_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS notes_job_id VARCHAR(64)",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'scheduled'",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS venue_lat DOUBLE PRECISION NOT NULL DEFAULT 0.0",
        "ALTER TABLE matches ADD COLUMN IF NOT EXISTS venue_lon DOUBLE PRECISION NOT NULL DEFAULT 0.0",
        "CREATE INDEX IF NOT EXISTS ix_notes_jobs_match_id ON notes_jobs (match_id)",
        "CREATE INDEX IF NOT EXISTS ix_notes_jobs_idempotency_key ON notes_jobs (idempotency_key)",
    ]
    for statement in statements:
        await conn.execute(text(statement))


class NotesJobRepository:
    """Async repository for notes jobs and results."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] = SessionLocal):
        self.session_factory = session_factory

    async def create_or_get_active_job(
        self,
        *,
        job_id: str,
        match_session: str,
        home_team: str,
        away_team: str,
        sport: str,
        competition: str = "",
        match_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> tuple[NotesJob, bool]:
        async with self.session_factory() as session:
            active = await session.scalar(
                select(NotesJob)
                .where(NotesJob.match_session == match_session)
                .where(NotesJob.status.in_([NotesJobStatus.QUEUED.value, NotesJobStatus.RUNNING.value]))
                .order_by(NotesJob.created_at.desc())
                .limit(1)
            )
            if active is not None:
                if competition and not active.competition:
                    active.competition = competition
                    await session.commit()
                    await session.refresh(active)
                return active, False

            job = NotesJob(
                job_id=job_id,
                match_session=match_session,
                home_team=home_team,
                away_team=away_team,
                sport=sport,
                competition=competition or "",
                match_id=match_id,
                idempotency_key=idempotency_key,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job, True

    async def get_job(self, job_id: str) -> Optional[NotesJob]:
        async with self.session_factory() as session:
            return await session.get(NotesJob, job_id)

    async def get_result(self, job_id: str) -> Optional[NotesResult]:
        async with self.session_factory() as session:
            return await session.get(NotesResult, job_id)

    async def get_latest_result_for_session(self, match_session: str) -> Optional[NotesResult]:
        async with self.session_factory() as session:
            return await session.scalar(
                select(NotesResult)
                .where(NotesResult.match_session == match_session)
                .order_by(NotesResult.created_at.desc())
                .limit(1)
            )

    async def mark_running(self, job_id: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(NotesJob, job_id)
            if job is None:
                return
            job.status = NotesJobStatus.RUNNING.value
            job.phase = "initialize"
            job.progress = max(job.progress or 0.0, 0.01)
            job.started_at = datetime.utcnow()
            job.attempts = (job.attempts or 0) + 1
            await session.commit()

    async def update_progress(self, job_id: str, phase: str, progress: float, error: Optional[str] = None) -> None:
        async with self.session_factory() as session:
            job = await session.get(NotesJob, job_id)
            if job is None:
                return
            job.status = NotesJobStatus.RUNNING.value
            job.phase = phase
            job.progress = max(0.0, min(1.0, float(progress or 0.0)))
            if error:
                job.error = error
            await session.commit()

    async def complete_job(
        self,
        *,
        job_id: str,
        notes_store: NotesStore,
        preparation_time_ms: float,
        warnings: list[Any],
        errors: list[Any],
        quality_report: Optional[dict[str, Any]] = None,
    ) -> None:
        async with self.session_factory() as session:
            job = await session.get(NotesJob, job_id)
            if job is None:
                return

            existing = await session.get(NotesResult, job_id)
            payload = notes_store.to_dict()
            notes_version = 1
            vlm_context_version = 1
            if job.match_id:
                match = await session.get(MatchSchedule, job.match_id)
                if match is not None:
                    notes_version = (match.notes_version or 0) + 1
                    vlm_context_version = (match.vlm_context_version or 0) + 1
            vlm_context = build_vlm_context_payload(notes_store, notes_version, vlm_context_version)
            vlm_context["quality_report"] = quality_report or {}
            vlm_context["competition"] = job.competition or ""
            if existing is None:
                existing = NotesResult(
                    job_id=job_id,
                    match_session=job.match_session,
                    markdown_notes=notes_store.raw_markdown,
                    notes_store_json=payload,
                    beat_count=len(notes_store.beats),
                    preparation_time_ms=preparation_time_ms,
                    warnings=warnings,
                    errors=errors,
                    notes_version=notes_version,
                    vlm_context_version=vlm_context_version,
                    vlm_context_json=vlm_context,
                )
                session.add(existing)
            else:
                existing.markdown_notes = notes_store.raw_markdown
                existing.notes_store_json = payload
                existing.beat_count = len(notes_store.beats)
                existing.preparation_time_ms = preparation_time_ms
                existing.warnings = warnings
                existing.errors = errors
                existing.notes_version = notes_version
                existing.vlm_context_version = vlm_context_version
                existing.vlm_context_json = vlm_context

            job.status = NotesJobStatus.SUCCEEDED.value
            job.phase = "complete"
            job.progress = 1.0
            job.error = None
            job.completed_at = datetime.utcnow()
            await session.commit()

    async def fail_job(self, job_id: str, error: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(NotesJob, job_id)
            if job is None:
                return
            job.status = NotesJobStatus.FAILED.value
            job.phase = "error"
            job.error = error
            job.completed_at = datetime.utcnow()
            await session.commit()

    async def upsert_match(
        self,
        *,
        match_id: str,
        match_session: str,
        home_team: str,
        away_team: str,
        sport: str,
        competition: str = "",
        kickoff_at: Optional[datetime] = None,
        venue: str = "",
        venue_lat: float = 0.0,
        venue_lon: float = 0.0,
    ) -> MatchSchedule:
        async with self.session_factory() as session:
            match = await session.get(MatchSchedule, match_id)
            if match is None:
                match = await session.scalar(
                    select(MatchSchedule).where(MatchSchedule.match_session == match_session).limit(1)
                )
            if match is None:
                match = MatchSchedule(
                    match_id=match_id,
                    match_session=match_session,
                    home_team=home_team,
                    away_team=away_team,
                    sport=sport,
                    competition=competition or "",
                    kickoff_at=kickoff_at,
                    venue=venue or "",
                    venue_lat=venue_lat or 0.0,
                    venue_lon=venue_lon or 0.0,
                )
                session.add(match)
            else:
                match.home_team = home_team
                match.away_team = away_team
                match.sport = sport
                match.competition = competition or match.competition or ""
                if kickoff_at is not None:
                    match.kickoff_at = kickoff_at
                if venue:
                    match.venue = venue
                match.venue_lat = venue_lat or match.venue_lat or 0.0
                match.venue_lon = venue_lon or match.venue_lon or 0.0
            await session.commit()
            await session.refresh(match)
            return match

    async def get_match(self, match_id: str) -> Optional[MatchSchedule]:
        async with self.session_factory() as session:
            return await session.get(MatchSchedule, match_id)

    async def get_match_by_session(self, match_session: str) -> Optional[MatchSchedule]:
        async with self.session_factory() as session:
            return await session.scalar(
                select(MatchSchedule).where(MatchSchedule.match_session == match_session).limit(1)
            )

    async def get_matches_due_for_prematch_notes(
        self,
        now: Optional[datetime] = None,
        lookahead: timedelta = timedelta(hours=12),
    ) -> list[MatchSchedule]:
        now = now or datetime.utcnow()
        due_at = now + lookahead
        async with self.session_factory() as session:
            result = await session.scalars(
                select(MatchSchedule)
                .where(MatchSchedule.kickoff_at.is_not(None))
                .where(MatchSchedule.kickoff_at <= due_at)
                .where(MatchSchedule.status.in_([
                    MatchScheduleStatus.SCHEDULED.value,
                    MatchScheduleStatus.FAILED.value,
                ]))
                .order_by(MatchSchedule.kickoff_at.asc())
            )
            return list(result)

    async def mark_match_notes_job(
        self,
        match_id: str,
        job_id: str,
        status: str = MatchScheduleStatus.NOTES_QUEUED.value,
    ) -> None:
        async with self.session_factory() as session:
            match = await session.get(MatchSchedule, match_id)
            if match is None:
                return
            match.notes_job_id = job_id
            match.status = status
            await session.commit()

    async def create_notes_version(
        self,
        *,
        match_id: str,
        match_session: str,
        notes_store: NotesStore,
        update_type: str,
        source_event_id: Optional[str] = None,
        warnings: Optional[list[Any]] = None,
        errors: Optional[list[Any]] = None,
        provenance: Optional[dict[str, Any]] = None,
        vlm_context: Optional[dict[str, Any]] = None,
    ) -> NotesVersion:
        import uuid

        async with self.session_factory() as session:
            match = await session.get(MatchSchedule, match_id)
            next_notes_version = ((match.notes_version or 0) + 1) if match else 1
            next_vlm_version = ((match.vlm_context_version or 0) + 1) if match else 1
            context = vlm_context or build_vlm_context_payload(notes_store, next_notes_version, next_vlm_version)
            context["notes_version"] = next_notes_version
            context["vlm_context_version"] = next_vlm_version

            active_versions = await session.scalars(
                select(NotesVersion)
                .where(NotesVersion.match_id == match_id)
                .where(NotesVersion.active.is_(True))
            )
            for version in active_versions:
                version.active = False

            version = NotesVersion(
                version_id=str(uuid.uuid4()),
                match_id=match_id,
                match_session=match_session,
                notes_version=next_notes_version,
                vlm_context_version=next_vlm_version,
                update_type=update_type,
                source_event_id=source_event_id,
                markdown_notes=notes_store.raw_markdown,
                notes_store_json=notes_store.to_dict(),
                vlm_context_json=context,
                provenance_json=provenance or {},
                warnings=warnings or [],
                errors=errors or [],
                active=True,
            )
            session.add(version)
            if match is not None:
                match.notes_version = next_notes_version
                match.vlm_context_version = next_vlm_version
                match.last_notes_update_at = datetime.utcnow()
                match.status = MatchScheduleStatus.NOTES_READY.value
            await session.commit()
            await session.refresh(version)
            return version

    async def get_latest_notes_version(
        self,
        *,
        match_id: Optional[str] = None,
        match_session: Optional[str] = None,
    ) -> Optional[NotesVersion]:
        async with self.session_factory() as session:
            query = select(NotesVersion).where(NotesVersion.active.is_(True))
            if match_id:
                query = query.where(NotesVersion.match_id == match_id)
            elif match_session:
                query = query.where(NotesVersion.match_session == match_session)
            else:
                return None
            return await session.scalar(query.order_by(NotesVersion.created_at.desc()).limit(1))

    async def create_live_event(
        self,
        *,
        event_id: str,
        match_id: str,
        match_session: str,
        event_type: str,
        source: str,
        description: str,
        confidence: float,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[LiveMatchEvent, bool]:
        async with self.session_factory() as session:
            existing = await session.scalar(
                select(LiveMatchEvent)
                .where(LiveMatchEvent.match_id == match_id)
                .where(LiveMatchEvent.idempotency_key == idempotency_key)
                .limit(1)
            )
            if existing is not None:
                return existing, False
            event = LiveMatchEvent(
                event_id=event_id,
                match_id=match_id,
                match_session=match_session,
                event_type=event_type,
                source=source,
                description=description,
                confidence=max(0.0, min(1.0, float(confidence or 0.0))),
                payload=payload or {},
                idempotency_key=idempotency_key,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event, True

    async def get_live_event(self, event_id: str) -> Optional[LiveMatchEvent]:
        async with self.session_factory() as session:
            return await session.get(LiveMatchEvent, event_id)

    async def mark_live_event_processed(
        self,
        event_id: str,
        *,
        notes_version: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        async with self.session_factory() as session:
            event = await session.get(LiveMatchEvent, event_id)
            if event is None:
                return
            event.processed = error is None
            event.error = error
            event.notes_version = notes_version
            event.processed_at = datetime.utcnow()
            await session.commit()


def notes_store_from_result(result: NotesResult) -> NotesStore:
    return NotesStore.from_dict(result.notes_store_json)


def notes_store_from_version(version: NotesVersion) -> NotesStore:
    return NotesStore.from_dict(version.notes_store_json)


def build_vlm_context_payload(
    notes_store: NotesStore,
    notes_version: int = 1,
    vlm_context_version: int = 1,
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Build the compact, versioned context package consumed by VLM workers."""
    return {
        "notes_version": notes_version,
        "vlm_context_version": vlm_context_version,
        "markdown_context": notes_store.raw_markdown[:max_chars],
        "beat_count": len(notes_store.beats),
        "lookup_tags": sorted(notes_store.lookup.keys()),
        "beats": [
            {
                "text": beat.text,
                "event_tags": beat.event_tags,
                "players": beat.players,
                "section": beat.section,
                "source": beat.source,
                "confidence": beat.confidence,
            }
            for beat in notes_store.beats[:80]
        ],
    }


def job_to_dict(job: NotesJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "match_session": job.match_session,
        "home_team": job.home_team,
        "away_team": job.away_team,
        "sport": job.sport,
        "competition": job.competition,
        "match_id": job.match_id,
        "status": job.status,
        "phase": job.phase,
        "progress": job.progress,
        "error": job.error,
        "attempts": job.attempts,
        "idempotency_key": job.idempotency_key,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def result_to_response(result: NotesResult) -> dict[str, Any]:
    notes_store = notes_store_from_result(result)
    quality_report = (result.vlm_context_json or {}).get("quality_report", {})
    return {
        "status": "success",
        "job_id": result.job_id,
        "match_session": result.match_session,
        "markdown_notes": result.markdown_notes,
        "beats": [
            {
                "text": beat.text,
                "event_tags": beat.event_tags,
                "players": beat.players,
                "section": beat.section,
                "source": beat.source,
                "source_urls": beat.source_urls,
                "source_attribution": beat.source_attribution,
                "confidence": beat.confidence,
            }
            for beat in notes_store.beats
        ],
        "preparation_time_ms": result.preparation_time_ms,
        "notes_version": result.notes_version,
        "vlm_context_version": result.vlm_context_version,
        "vlm_context": result.vlm_context_json,
        "competition": (result.vlm_context_json or {}).get("competition", ""),
        "quality_report": quality_report,
        "degraded_sections": quality_report.get("degraded_sections", []) if isinstance(quality_report, dict) else [],
        "unavailable_facts": quality_report.get("unavailable_facts", []) if isinstance(quality_report, dict) else [],
        "agents_completed": None,
        "errors": result.errors,
        "warnings": result.warnings,
        "beat_count": result.beat_count,
    }


def match_to_dict(match: MatchSchedule) -> dict[str, Any]:
    return {
        "match_id": match.match_id,
        "match_session": match.match_session,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "sport": match.sport,
        "competition": match.competition,
        "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
        "venue": match.venue,
        "venue_lat": match.venue_lat,
        "venue_lon": match.venue_lon,
        "status": match.status,
        "notes_job_id": match.notes_job_id,
        "notes_version": match.notes_version,
        "vlm_context_version": match.vlm_context_version,
        "last_notes_update_at": match.last_notes_update_at.isoformat() if match.last_notes_update_at else None,
    }


def notes_version_to_response(version: NotesVersion) -> dict[str, Any]:
    notes_store = notes_store_from_version(version)
    quality_report = (version.vlm_context_json or {}).get("quality_report", {})
    return {
        "status": "ready",
        "match_id": version.match_id,
        "match_session": version.match_session,
        "markdown_notes": version.markdown_notes,
        "beats": [
            {
                "text": beat.text,
                "event_tags": beat.event_tags,
                "players": beat.players,
                "section": beat.section,
                "source": beat.source,
                "source_urls": beat.source_urls,
                "source_attribution": beat.source_attribution,
                "confidence": beat.confidence,
            }
            for beat in notes_store.beats
        ],
        "beat_count": len(notes_store.beats),
        "notes_version": version.notes_version,
        "vlm_context_version": version.vlm_context_version,
        "vlm_context": version.vlm_context_json,
        "competition": (version.vlm_context_json or {}).get("competition", ""),
        "quality_report": quality_report,
        "degraded_sections": quality_report.get("degraded_sections", []) if isinstance(quality_report, dict) else [],
        "unavailable_facts": quality_report.get("unavailable_facts", []) if isinstance(quality_report, dict) else [],
        "update_type": version.update_type,
        "source_event_id": version.source_event_id,
        "warnings": version.warnings,
        "errors": version.errors,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
