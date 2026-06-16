# Commentary Notes Follow-Up TODO

Context: Belgium vs Egypt notes generation completed successfully after Exa-first fixture search, but the live run exposed quality and runtime issues that should be fixed before treating the flow as production-ready. Use Panama vs England for all new notes-generation validation runs from here onward.

Latest status: Priority 1 implementation is in place and focused tests pass. The latest completed full job was `belgium-egypt-priority1-final4-20260615T201424Z`; Qwen review passed refusal/degraded/position-glued gates but failed the player-card/lineup usability gate. Follow-up fixes for that Qwen failure are implemented and unit-tested, but a fresh full regeneration (`final5`) hung after Tavily plan-limit fallbacks and was terminated before writing an artifact.

## Priority 1

- **DONE** Fix Celery event-loop reuse errors in notes agents.
  - Observed errors:
    - `NewsAgent: Semaphore object is bound to a different event loop`
    - `HistoricalContextAgent: Semaphore object is bound to a different event loop`
  - Expected outcome: notes jobs can run repeatedly in the worker without asyncio semaphore failures.
  - Implemented:
    - Wafer commentary-notes semaphore is now loop-local and prunes closed loops.
    - FootballData semaphore is now loop-local.
  - Validation:
    - Focused quality-gate tests include loop-local semaphore coverage.

- **DONE** Clean lineup and player extraction.
  - Current issue: candidate player strings can include labels or malformed names such as `Predicted XI` and position-glued names.
  - Expected outcome: lineup fields contain only real player names and structured positions.
  - Implemented:
    - News lineup parsing now strips labels and keeps structured position/name entries.
    - Fixture resolver strips leading/trailing position tokens, handles glued position/name forms, side-scopes lineup extraction, filters article headings/ad fragments/club parentheticals, and avoids Belgium-name spillover into Egypt.
    - Note organizer dedupes alias names such as `Mo Salah` / `Mohamed Salah`.
    - Note organizer suppresses malformed plausible XIs when role groups are not usable.
    - Fixture-candidate player cards no longer render `Unknown` / `N/A` placeholder-heavy rows.
  - Validation:
    - Focused tests cover position-glued names, lineup side assignment, non-player phrase filtering, parenthetical club filtering, duplicate Salah handling, and malformed plausible XI suppression.
  - Remaining full-run validation:
    - Needs a fresh full Panama vs England notes job and Qwen review after provider limits clear. The attempted Belgium vs Egypt `final5` rerun hung after Tavily quota errors and was terminated without writing an artifact.

- **DONE** Prevent fallback/refusal text from entering final tactical notes.
  - Current issue: tactical output can include text like "I'm unable to provide..." instead of usable analysis.
  - Expected outcome: low-confidence tactical sections are either regenerated, omitted, or replaced with a clean degraded-state note.
  - Implemented:
    - Matchup analysis detects refusal text and replaces it with deterministic degraded tactical implications.
    - Note organizer filters unsafe tactical summaries before final markdown.
    - Degraded historical/weather/team-news sections now use concise unavailable markers.
  - Validation:
    - Qwen review for `final4` reported:
      - `no_refusal_text: true`
      - `no_position_glued_names: true`
      - `degraded_sections_are_clean: true`

## Priority 2

- **DONE** Improve weather fallback behavior.
  - Current issue: weather remains degraded for the tested fixture.
  - Expected outcome: weather section uses a reliable venue/date lookup path or emits a concise unavailable state.
  - Implemented:
    - Weather retrieval now falls back from Tavily to Open-Meteo when venue coordinates and kickoff date are available.
    - Weather unavailable states now return deterministic concise text instead of an LLM-generated filler narrative.
    - Open-Meteo is treated as trusted weather evidence.

- **DONE** Add regression coverage for Exa-first fixture evidence in end-to-end notes flow.
  - Current unit coverage verifies resolver ordering.
  - Expected outcome: a notes job test proves Exa-sourced fixture URLs can flow into accepted beats.
  - Implemented:
    - Commentary notes workflow e2e coverage now verifies an Exa fixture URL enters targeted evidence and generated narrative beats.

- **DONE** Avoid repeated Tavily calls once plan limit is detected.
  - Current issue: after Tavily returns plan-limit 403s, later lookup paths continue attempting Tavily and slow or hang full notes generation.
  - Expected outcome: mark Tavily unavailable for the current run after a quota/plan-limit response and fall back immediately to Exa/cache/structured sources.
  - Implemented:
    - Tavily search service now marks itself unavailable for the current service instance after quota/plan-limit failures while still allowing cached results before live calls.

- **DONE** Fix FootballData audited proxy call shape for H2H.
  - Current issue in retrieval audit: `FootballDataRetriever.get_head_to_head() got an unexpected keyword argument 'limit'`.
  - Expected outcome: H2H retrieval/audit path should call provider-compatible signatures and avoid noisy false errors.
  - Implemented:
    - FootballData H2H now accepts `limit`, preserving the audited proxy call shape used by historical notes.
    - Retrieval audit regression coverage verifies the H2H proxy path records a successful event.

## Validation Checklist

- **DONE** Run fixture resolver unit tests.
- **DONE** Run Exa search service tests.
- **DONE** Run focused quality-gate tests.
  - Latest focused run: `45 passed, 21 warnings`.
- **DONE** Run a fresh notes job for Belgium vs Egypt.
  - Latest completed job: `belgium-egypt-priority1-final4-20260615T201424Z`.
  - Markdown: `logs/commentary_notes_manual/belgium-egypt-priority1-final4-20260615T201424Z.md`
  - Job JSON: `logs/commentary_notes_manual/belgium-egypt-priority1-final4-20260615T201424Z.json`
  - Audit dir: `debug/retrievals/notes_belgium-egypt-priority1-final4-20260615T201424Z`
- **DONE** Confirm final job status is `succeeded`.
  - `final4` completed with no workflow errors.
- **DONE** Confirm accepted evidence includes Exa fixture sources.
  - `final4` audit has successful `exa_search` events; no Exa 403 remained after unavailable-domain retry handling.
- **DONE** Confirm no agent event-loop errors are reported.
  - `final4` completed without semaphore/event-loop errors.
- **DONE** Review final markdown output for malformed names, fallback text, and degraded sections.
  - Static scan on `final4` found no refusal text, no position-glued names, and no Belgium players assigned to Egypt.
- **DONE** Review final markdown with Qwen.
  - Qwen model: `Qwen3.5-397B-A17B`
  - Review JSON: `logs/commentary_notes_manual/belgium-egypt-priority1-final4-20260615T201424Z.qwen-review.json`
  - Result: `overall: fail`
  - Passed Priority 1 gates: refusal text, position-glued names, degraded sections.
  - Failed Priority 1 gate: lineups/player cards were not air-ready due duplicate Salah and placeholder-heavy Egypt rows.
- **TODO** Rerun full Panama vs England job and Qwen review after the post-review lineup/card fixes.
  - Use Panama vs England for this and future live validation runs.
  - Previous blocker: Tavily plan-limit fallbacks caused the Belgium vs Egypt `final5` regeneration to hang before artifact write.
