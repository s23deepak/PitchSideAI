# Deferred Work

## Deferred from: code review of 4.1 & 4.3 (2026-05-05)

- Font stack anti-pattern (Inter duplicated) in `frontend/src/index.css` — pre-existing pattern, not introduced by this diff
- Aggressive motion reduction (0.01ms may cause issues) in `frontend/src/index.css:116-122` — spec-compliant (UX-DR20), theoretical concern only
- Missing CSP headers for static serving in `api/server.py` — enhancement not required by spec
- 8 shadcn/ui components not evidenced in diff — components exist per story 4.3 file, just not shown in diff
