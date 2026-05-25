# Commentary Notes Speedups

## What Changed

- Moved `team_form` into the first parallel research round because it only needs team names.
- Kept `matchup_analysis` sequential after `player_research`, because it depends on researched lineups.
- Fetched match-day weather and forecast trend concurrently before weather impact synthesis.
- Batched player profile generation to one LLM call per squad instead of one LLM call per player.
- Raced the first two available API/source retrievers for player stats, recent form, team news, and injuries, while preserving per-source rate limiters.
- Standardized notes inference on `vllm` for the active self-hosted path.
- Kept the active README setup path on `vllm` for notes inference.

## Parallel vs Sequential

Parallel:

- news
- weather
- historical context
- player research
- team form
- per-player source enrichment within each squad
- fast API/source races with bounded fanout

Sequential:

- initialization when match venue/date are missing
- matchup analysis after player research
- final notes synthesis after all selected research is complete
- weather impact after current weather is known
- provider rate limiting inside each retriever

## Expected Effect

The largest latency reduction should come from removing per-player LLM calls and eliminating the artificial wait for squad research before team form. API/source racing should also reduce long tail latency when a primary source is empty or slow.
