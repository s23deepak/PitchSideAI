"""Celery application for PitchSideAI background jobs."""

from celery import Celery

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
)
