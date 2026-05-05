# Deferred Work

## Deferred from: code review of 1-1-narrative-data-models-tag-system (2026-05-05)

- Goal safety gate silently suppresses goal tags without logging — enhancement, not bug [models/notes_store.py:142-147]
- NotesStore.__post_init__ skips lookup rebuild when pre-populated — already in spec review findings [models/notes_store.py:170-171]
- index: Optional[Any] too vague — placeholder per spec, loses type safety [models/notes_store.py:166]
- Casefold without Unicode normalization — edge case, not critical [models/notes_store.py:106,111,118]

## Deferred from: code review of 2-1-voice-input-micbutton-stt (2026-05-05)

- Split-Screen State Race Condition — Recording cuts off abruptly when split-screen activates — deferred to Story 2.3 (SplitScreen implementation will define proper behavior)
- Multiple Tabs Same Origin — Web Speech API single-instance conflict — deferred, browser limitation
- AC5 Partial — Chip suggestion UI not implemented (only console.log) — deferred to Story 2.2 (Q&A Backend will define chip format)
- AC6 Partial — Gradient ring uses simple spin, not true gradient rotation — deferred, visual polish
- No exponential backoff for failures — deferred, not required for MVP
- Hardcoded 1000ms confirmation delay — deferred, accessibility enhancement
- Missing language change effect — deferred, language is static for now
- Interim Transcript Memory Leak — deferred, minor performance issue
