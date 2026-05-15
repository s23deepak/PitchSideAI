"""Celery tasks for durable commentary-notes generation."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from jobs.celery_app import celery_app
from jobs.notes_events import publish_notes_job_event
from models.notes_jobs import NotesJobRepository, init_notes_job_db, result_to_response
from workflows import CommentaryNotesState, create_workflow


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


async def _run_generate_commentary_notes(job_id: str) -> dict[str, Any]:
    repo = NotesJobRepository()
    await init_notes_job_db()
    job = await repo.get_job(job_id)
    if job is None:
        raise ValueError(f"Notes job not found: {job_id}")

    await repo.mark_running(job_id)
    await publish_notes_job_event(job_id, {
        "phase": "initialize",
        "message": "Notes job started",
        "progress": 0.01,
        "done": False,
    })

    workflow_state = CommentaryNotesState(
        match_id=f"{job.home_team}_{job.away_team}",
        home_team=job.home_team,
        away_team=job.away_team,
        sport=job.sport,
    )
    workflow = create_workflow()

    async def on_progress(phase: str, message: str, extra: dict[str, Any]) -> None:
        progress = PROGRESS_MAP.get(phase, 0.0)
        if extra.get("done", False):
            progress = min(1.0, progress + 0.05)
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
        )
        result = await repo.get_result(job_id)
        response = result_to_response(result)
        response.update({
            "workflow_id": completed_state.workflow_id,
            "match": f"{job.home_team} vs {job.away_team}",
            "sport": job.sport,
            "agents_completed": len(completed_state.completed_agents),
        })
        await publish_notes_job_event(job_id, {
            "phase": "complete",
            "message": "Done",
            "progress": 1.0,
            "done": True,
            "result": response,
        })
        return response
    except Exception as exc:
        error = str(exc)
        await repo.fail_job(job_id, error)
        await publish_notes_job_event(job_id, {
            "phase": "error",
            "message": error,
            "progress": 1.0,
            "done": True,
        })
        raise


@celery_app.task(name="jobs.notes_tasks.generate_commentary_notes")
def generate_commentary_notes(job_id: str) -> dict[str, Any]:
    return asyncio.run(_run_generate_commentary_notes(job_id))


def enqueue_commentary_notes_job(job_id: str) -> None:
    generate_commentary_notes.delay(job_id)
