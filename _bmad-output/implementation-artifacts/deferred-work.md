# Deferred Work

## Deferred from: code review of 1-1-narrative-data-models-tag-system (2026-05-05)

- Goal safety gate silently suppresses goal tags without logging — enhancement, not bug [models/notes_store.py:142-147]
- NotesStore.__post_init__ skips lookup rebuild when pre-populated — already in spec review findings [models/notes_store.py:170-171]
- index: Optional[Any] too vague — placeholder per spec, loses type safety [models/notes_store.py:166]
- Casefold without Unicode normalization — edge case, not critical [models/notes_store.py:106,111,118]
