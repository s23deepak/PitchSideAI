from types import SimpleNamespace

import jobs.celery_app as celery_app_module
import jobs.notes_tasks as notes_tasks
from models.notes_jobs import MatchScheduleStatus


class FakeRepo:
    def __init__(self, due_matches, job_created_by_match):
        self.due_matches = due_matches
        self.job_created_by_match = job_created_by_match
        self.marked = []

    async def get_matches_due_for_prematch_notes(self):
        return self.due_matches

    async def create_or_get_active_job(self, **kwargs):
        match_id = kwargs["match_id"]
        created = self.job_created_by_match[match_id]
        job = SimpleNamespace(job_id=kwargs["job_id"], match_id=match_id)
        return job, created

    async def mark_match_notes_job(self, match_id, job_id, status=MatchScheduleStatus.NOTES_QUEUED.value):
        self.marked.append((match_id, job_id, status))


def _match(match_id, notes_job_id=None):
    return SimpleNamespace(
        match_id=match_id,
        match_session=f"session:{match_id}",
        home_team="Arsenal",
        away_team="Chelsea",
        sport="soccer",
        notes_job_id=notes_job_id,
    )


def test_schedule_prematch_notes_enqueues_only_new_jobs(monkeypatch):
    due_matches = [
        _match("match-new", notes_job_id="job-new"),
        _match("match-existing", notes_job_id="job-existing"),
    ]
    fake_repo = FakeRepo(
        due_matches=due_matches,
        job_created_by_match={
            "match-new": True,
            "match-existing": False,
        },
    )
    delayed_match_ids = []

    async def noop_init_db():
        return None

    monkeypatch.setattr(notes_tasks, "init_notes_job_db", noop_init_db)
    monkeypatch.setattr(notes_tasks, "NotesJobRepository", lambda: fake_repo)
    monkeypatch.setattr(
        notes_tasks.generate_prematch_notes,
        "delay",
        lambda match_id: delayed_match_ids.append(match_id),
    )

    result = notes_tasks.schedule_prematch_notes()

    assert result == {"enqueued": [{"match_id": "match-new", "job_id": "job-new"}], "count": 1}
    assert delayed_match_ids == ["match-new"]
    assert fake_repo.marked == [
        ("match-new", "job-new", MatchScheduleStatus.NOTES_QUEUED.value),
        ("match-existing", "job-existing", MatchScheduleStatus.NOTES_QUEUED.value),
    ]


def test_story1_celery_beat_and_retry_configuration():
    beat_entry = celery_app_module.celery_app.conf.beat_schedule["schedule-prematch-notes-every-minute"]

    assert beat_entry["task"] == "jobs.notes_tasks.schedule_prematch_notes"
    assert beat_entry["schedule"] == 60.0
    assert notes_tasks.generate_prematch_notes.name == "jobs.notes_tasks.generate_prematch_notes"
    assert notes_tasks.generate_prematch_notes.max_retries == 3
    assert notes_tasks.generate_commentary_notes.max_retries == 3
