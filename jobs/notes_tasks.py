"""Celery tasks for durable commentary-notes generation."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_sources.retrieval_audit import (
    get_audit_dir,
    llm_audit_enabled,
    retrieval_audit_enabled,
    set_audit_run_id,
)
from jobs.celery_app import celery_app
from jobs.notes_cache import cache_notes_version, notes_update_lock, publish_notes_updated
from jobs.notes_events import publish_notes_job_event
from models.notes_jobs import (
    MatchScheduleStatus,
    NotesJobRepository,
    build_vlm_context_payload,
    init_notes_job_db,
    result_to_response,
)
from workflows import (
    CommentaryNotesState,
    LiveNotesPatchState,
    LiveNotesPatchWorkflow,
    create_workflow,
)


logger = logging.getLogger(__name__)

PROGRESS_MAP = {
    "initialize": 0.05,
    "parallel_phase": 0.12,
    "initial_context": 0.25,
    "squad_research": 0.45,
    "form_analysis": 0.70,
    "matchup_analysis": 0.82,
    "synthesis": 0.90,
    "complete": 1.0,
}


def _match_id_from_session(match_session: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"pitchsideai:{match_session}"))


async def _run_generate_commentary_notes(job_id: str) -> dict[str, Any]:
    logger.info("commentary_notes_task_start job_id=%s", job_id)
    set_audit_run_id(f"notes_{job_id}")
    repo = NotesJobRepository()
    await init_notes_job_db()
    job = await repo.get_job(job_id)
    if job is None:
        logger.error("commentary_notes_task_missing_job job_id=%s", job_id)
        raise ValueError(f"Notes job not found: {job_id}")

    logger.info(
        "commentary_notes_task_loaded job_id=%s match=%s_vs_%s sport=%s competition=%s",
        job_id,
        job.home_team,
        job.away_team,
        job.sport,
        job.competition or "",
    )
    await repo.mark_running(job_id)
    await publish_notes_job_event(job_id, {
        "phase": "initialize",
        "message": "Notes job started",
        "progress": 0.01,
        "done": False,
        "audit_dir": str(get_audit_dir())
        if (retrieval_audit_enabled() or llm_audit_enabled())
        else None,
    })

    match = (
        await repo.get_match(job.match_id)
        if job.match_id
        else await repo.get_match_by_session(job.match_session)
    )
    workflow_state = CommentaryNotesState(
        match_id=job.match_id or _match_id_from_session(job.match_session),
        home_team=job.home_team,
        away_team=job.away_team,
        sport=job.sport,
        competition=job.competition or (match.competition if match else ""),
        match_datetime=match.kickoff_at.isoformat() if match and match.kickoff_at else "",
        venue=match.venue if match else "",
        venue_lat=match.venue_lat if match else 0.0,
        venue_lon=match.venue_lon if match else 0.0,
    )
    workflow = create_workflow()

    async def on_progress(phase: str, message: str, extra: dict[str, Any]) -> None:
        progress = PROGRESS_MAP.get(phase, 0.0)
        if extra.get("done", False):
            progress = min(1.0, progress + 0.05)
        logger.info(
            "commentary_notes_task_progress job_id=%s phase=%s progress=%.2f message=%s",
            job_id,
            phase,
            progress,
            message,
        )
        event = {
            "phase": phase,
            "message": message,
            "progress": progress,
            "done": extra.get("done", False),
        }
        await repo.update_progress(job_id, phase, progress)
        await publish_notes_job_event(job_id, event)

    try:
        completed_state = await workflow.run_workflow(workflow_state, on_progress=on_progress)
        if completed_state.notes_store is None:
            raise ValueError("Notes workflow completed without a NotesStore")

        duration_ms = (
            (completed_state.end_time - completed_state.start_time).total_seconds() * 1000
            if completed_state.end_time
            else (datetime.utcnow() - completed_state.start_time).total_seconds() * 1000
        )
        await repo.complete_job(
            job_id=job_id,
            notes_store=completed_state.notes_store,
            preparation_time_ms=duration_ms,
            warnings=completed_state.warnings,
            errors=completed_state.errors,
            quality_report=completed_state.quality_report,
        )
        result = await repo.get_result(job_id)
        if job.match_id and completed_state.notes_store is not None:
            version = await repo.create_notes_version(
                match_id=job.match_id,
                match_session=job.match_session,
                notes_store=completed_state.notes_store,
                update_type="prematch",
                warnings=completed_state.warnings,
                errors=completed_state.errors,
                provenance=completed_state.source_provenance,
                vlm_context={
                    **build_vlm_context_payload(
                        completed_state.notes_store,
                        result.notes_version if result else 1,
                        result.vlm_context_version if result else 1,
                    ),
                    "quality_report": completed_state.quality_report,
                    "competition": job.competition,
                },
            )
            await cache_notes_version(version)
            await publish_notes_updated(version)
        response = result_to_response(result)
        response.update({
            "workflow_id": completed_state.workflow_id,
            "match": f"{job.home_team} vs {job.away_team}",
            "sport": job.sport,
            "competition": job.competition,
            "agents_completed": len(completed_state.completed_agents),
        })
        if retrieval_audit_enabled() or llm_audit_enabled():
            response["audit_dir"] = str(get_audit_dir())
        await publish_notes_job_event(job_id, {
            "phase": "complete",
            "message": "Done",
            "progress": 1.0,
            "done": True,
            "result": response,
        })
        logger.info(
            "commentary_notes_task_succeeded job_id=%s workflow_id=%s agents_completed=%s",
            job_id,
            completed_state.workflow_id,
            len(completed_state.completed_agents),
        )
        return response
    except Exception as exc:
        error = str(exc)
        logger.exception("commentary_notes_task_failed job_id=%s error=%s", job_id, error)
        await repo.fail_job(job_id, error)
        await publish_notes_job_event(job_id, {
            "phase": "error",
            "message": error,
            "progress": 1.0,
            "done": True,
        })
        raise


@celery_app.task(
    name="jobs.notes_tasks.generate_commentary_notes",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def generate_commentary_notes(job_id: str) -> dict[str, Any]:
    return asyncio.run(_run_generate_commentary_notes(job_id))


@celery_app.task(
    name="jobs.notes_tasks.generate_prematch_notes",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def generate_prematch_notes(match_id: str) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        repo = NotesJobRepository()
        await init_notes_job_db()
        match = await repo.get_match(match_id)
        if match is None:
            raise ValueError(f"Match not found: {match_id}")
        job_id = match.notes_job_id or str(uuid.uuid4())
        job, created = await repo.create_or_get_active_job(
            job_id=job_id,
            match_id=match.match_id,
            match_session=match.match_session,
            home_team=match.home_team,
            away_team=match.away_team,
            sport=match.sport,
            competition=getattr(match, "competition", ""),
            idempotency_key=f"prematch:{match.match_id}",
        )
        if created or match.notes_job_id != job.job_id:
            await repo.mark_match_notes_job(match.match_id, job.job_id, MatchScheduleStatus.NOTES_QUEUED.value)
        return await _run_generate_commentary_notes(job.job_id)

    return asyncio.run(_run())


@celery_app.task(name="jobs.notes_tasks.schedule_prematch_notes")
def schedule_prematch_notes() -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        repo = NotesJobRepository()
        await init_notes_job_db()
        due_matches = await repo.get_matches_due_for_prematch_notes()
        enqueued = []
        for match in due_matches:
            job_id = match.notes_job_id or str(uuid.uuid4())
            job, created = await repo.create_or_get_active_job(
                job_id=job_id,
                match_id=match.match_id,
                match_session=match.match_session,
                home_team=match.home_team,
                away_team=match.away_team,
                sport=match.sport,
                competition=getattr(match, "competition", ""),
                idempotency_key=f"prematch:{match.match_id}",
            )
            await repo.mark_match_notes_job(match.match_id, job.job_id, MatchScheduleStatus.NOTES_QUEUED.value)
            if created:
                generate_prematch_notes.delay(match.match_id)
                enqueued.append({"match_id": match.match_id, "job_id": job.job_id})
        return {"enqueued": enqueued, "count": len(enqueued)}

    return asyncio.run(_run())


@celery_app.task(
    name="jobs.notes_tasks.update_live_notes",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def update_live_notes(match_id: str, event_id: str) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        repo = NotesJobRepository()
        await init_notes_job_db()
        event = await repo.get_live_event(event_id)
        if event is None:
            raise ValueError(f"Live event not found: {event_id}")
        latest = await repo.get_latest_notes_version(match_id=match_id)
        if latest is None:
            result = await repo.get_latest_result_for_session(event.match_session)
            if result is None:
                raise ValueError(f"No notes available to patch for match: {match_id}")
            notes_store_payload = result.notes_store_json
        else:
            notes_store_payload = latest.notes_store_json

        async with notes_update_lock(match_id) as acquired:
            if not acquired:
                return {"status": "skipped", "reason": "notes_update_lock_busy", "event_id": event_id}
            workflow = LiveNotesPatchWorkflow()
            state = await workflow.run(LiveNotesPatchState(
                match_id=match_id,
                match_session=event.match_session,
                event_id=event.event_id,
                event_type=event.event_type,
                description=event.description,
                source=event.source,
                confidence=event.confidence,
                payload=event.payload,
                notes_store_payload=notes_store_payload,
            ))
            if state.patched_notes_store is None:
                raise ValueError("Live notes patch did not produce notes")
            version = await repo.create_notes_version(
                match_id=match_id,
                match_session=event.match_session,
                notes_store=state.patched_notes_store,
                update_type="live_patch",
                source_event_id=event.event_id,
                warnings=state.warnings,
                errors=state.errors,
                provenance={"source": event.source, "event_type": event.event_type},
                vlm_context=state.vlm_context,
            )
            await repo.mark_live_event_processed(event.event_id, notes_version=version.notes_version)
            await cache_notes_version(version)
            await publish_notes_updated(version)
            return {
                "status": "updated",
                "match_id": match_id,
                "event_id": event_id,
                "notes_version": version.notes_version,
                "vlm_context_version": version.vlm_context_version,
                "patch_summary": state.patch_summary,
            }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        async def _mark_failed() -> None:
            repo = NotesJobRepository()
            await repo.mark_live_event_processed(event_id, error=str(exc))

        asyncio.run(_mark_failed())
        raise


def enqueue_commentary_notes_job(job_id: str) -> None:
    logger.info("commentary_notes_task_enqueue job_id=%s", job_id)
    generate_commentary_notes.delay(job_id)


def enqueue_live_notes_update(match_id: str, event_id: str) -> None:
    update_live_notes.delay(match_id, event_id)
