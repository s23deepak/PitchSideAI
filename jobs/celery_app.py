"""Celery application for PitchSideAI background jobs."""

from pathlib import Path
import sys

from celery import Celery

# Celery workers may fork or change cwd after bootstrap. Keep the project root
# as an absolute import path so runtime imports like `agents.*` stay resolvable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND


celery_app = Celery(
    "pitchai",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["jobs.notes_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    worker_prefetch_multiplier=1,
    beat_schedule={
        "schedule-prematch-notes-every-minute": {
            "task": "jobs.notes_tasks.schedule_prematch_notes",
            "schedule": 60.0,
        },
    },
)
