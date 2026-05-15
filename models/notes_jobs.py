"""Persistent commentary-notes job state and results."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DATABASE_URL
from models.notes_store import NotesStore


class NotesJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Base(DeclarativeBase):
    pass


class NotesJob(Base):
    __tablename__ = "notes_jobs"
    __table_args__ = (Index("ix_notes_jobs_match_session_status", "match_session", "status"),)

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    match_session: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    sport: Mapped[str] = mapped_column(String(40), nullable=False, default="soccer")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=NotesJobStatus.QUEUED.value)
    phase: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_notes_job_db() -> None:
    """Create notes job tables when migrations have not run yet."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
                return active, False

            job = NotesJob(
                job_id=job_id,
                match_session=match_session,
                home_team=home_team,
                away_team=away_team,
                sport=sport,
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
    ) -> None:
        async with self.session_factory() as session:
            job = await session.get(NotesJob, job_id)
            if job is None:
                return

            existing = await session.get(NotesResult, job_id)
            payload = notes_store.to_dict()
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
                )
                session.add(existing)
            else:
                existing.markdown_notes = notes_store.raw_markdown
                existing.notes_store_json = payload
                existing.beat_count = len(notes_store.beats)
                existing.preparation_time_ms = preparation_time_ms
                existing.warnings = warnings
                existing.errors = errors

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


def notes_store_from_result(result: NotesResult) -> NotesStore:
    return NotesStore.from_dict(result.notes_store_json)


def job_to_dict(job: NotesJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "match_session": job.match_session,
        "home_team": job.home_team,
        "away_team": job.away_team,
        "sport": job.sport,
        "status": job.status,
        "phase": job.phase,
        "progress": job.progress,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def result_to_response(result: NotesResult) -> dict[str, Any]:
    notes_store = notes_store_from_result(result)
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
        "agents_completed": None,
        "errors": result.errors,
        "warnings": result.warnings,
        "beat_count": result.beat_count,
    }
