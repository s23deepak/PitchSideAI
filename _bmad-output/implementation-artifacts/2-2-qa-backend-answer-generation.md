---
story_id: "2.2"
story_key: "2-2-qa-backend-answer-generation"
epic: "Epic 2: Fan Q&A — Ask & Understand"
status: "ready-for-dev"
created: "2026-05-05"
---

# Story 2.2: Q&A Backend — Answer Generation

## User Story

As a fan asking a question about the match,
I want the AI to answer in the same commentator voice and style as the live commentary,
So that the response feels like a knowledgeable companion talking to me, not a search result.

**FRs covered:** FR13 (Same-Commentator Voice), FR11 (Graceful Fallback)

---

## Acceptance Criteria (BDD)

### AC1: Query Message Handling

**Given** a `query` WebSocket message is received: `{"type": "query", "text": "Why is that a red card?", "timestamp": "ISO8601"}`
**When** the server processes the question
**Then** `game_state.to_context_string()` is prepended to the LLM prompt
**And** current commentary settings (bias, excitement, knowledge_depth) are injected into the prompt template
**And** the LLM generates an answer in the same Peter Drury commentator voice/style
**And** the answer is broadcast: `{"type": "answer", "text": "...", "gameState": {...}, "timestamp": "ISO8601"}`.

### AC2: GPU Priority Scheduling

**Given** Q&A decode is highest GPU priority (Priority 1)
**When** a fan question arrives during streaming prefill
**Then** Q&A decode preempts streaming prefill
**And** the answer first text token arrives within 3.5 seconds of question submission (NFR-1), measured at P95.

### AC3: Pre-Computed Q&A Cache

**Given** pre-computed Q&A pairs exist from the notes pipeline (Story 1.3)
**When** a question matches a pre-computed pair (e.g., "Why is that a red card?" triggered by a red card event)
**Then** the cached answer is returned within 1 second (tap path latency)
**And** pre-computed overlay coordinates are included in the answer payload.

### AC4: KV Cache Temporal Context

**Given** the KV cache has sufficient temporal context for the question
**When** answering
**Then** the answer references the specific visual moment (e.g., "See how his studs made contact above the ankle")
**And** the most relevant timestamp is included in the answer payload for split-screen navigation.

### AC5: Limited Temporal Context Fallback

**Given** the KV cache does not contain the relevant timestamp (> 120s ago, or fallback level 3-4)
**When** answering
**Then** the system answers with available context and includes `"temporal_context": "limited"` in the answer payload
**And** the answer text includes the calm indicator: "Based on available footage..."
**And** at fallback level 3-4, answers use pre-computed embeddings or general football knowledge (FR-11).

### AC6: Non-Football Question Handling

**Given** a non-football question is submitted
**When** the LLM processes it
**Then** the answer gracefully redirects: "I'm focused on the match right now — try asking about what's happening on the pitch!"
**And** the message type is still `answer` (not `error`).

---

## Technical Requirements

### Implementation Details

1. **WebSocket Query Handler** (`api/server.py`)
   ```python
   async def handle_query(self, data: dict):
       question = data["text"]
       # 1. Check pre-computed Q&A cache
       # 2. Build prompt with game_state + settings
       # 3. Call LLM (Priority 1)
       # 4. Broadcast answer
   ```

2. **Prompt Template**
   ```
   {game_state.to_context_string()}
   
   Commentary Settings:
   - Bias: {bias} (Team A fan [-1] to Team B fan [+1])
   - Excitement: {excitement} (0=subdued, 1=maximum)
   - Knowledge Depth: {knowledge_depth} (0=beginner, 1=tactical)
   
   Question: {question}
   
   Answer in the style of Peter Drury commentary.
   {temporal_context_hint if available}
   ```

3. **Pre-Computed Q&A Cache**
   - Generated alongside notes in Story 1.3
   - Key: normalized question text
   - Value: `{answer_text, overlay_coordinates, timestamp}`
   - Check cache before LLM call

4. **KV Cache Lookup**
   - Query includes semantic search over retained frames
   - Return most relevant timestamp for split-screen
   - Include `temporal_context: "limited"` if > 120s or fallback 3-4

5. **GPU Priority Scheduling**
   - Q&A decode = Priority 1 (preempts streaming prefill)
   - SGLang's disaggregated prefill/decode handles this naturally
   - Measure P95 latency: must be < 3.5s end-to-end

---

## Architecture Compliance

### File Location
- **Handler:** `api/server.py` (extend `ConnectionManager`)
- **Prompt Template:** `config/prompts.py` (add Q&A template)
- **Cache:** `models/notes_store.py` (add `qa_cache: Dict[str, QAPair]`)

### WebSocket Protocol (from architecture.md)
| Direction | Message Type | Purpose |
|-----------|-------------|---------|
| Client → Server | `query` | Fan Q&A text question |
| Server → Client | `answer` | Q&A response text |

**Answer payload:**
```json
{
  "type": "answer",
  "text": "...",
  "gameState": {...},
  "temporal_context": "full" | "limited",
  "timestamp": "ISO8601",
  "overlay_coordinates": {...}  // if available
}
```

### Game State Injection (Pattern from architecture.md)
```python
seed = f"{game_state.to_context_string()}\n\n{qa_prompt}"
```
Always prepended — never bypass.

### Confidence-Gated Progression
- Player identification confidence included in answer if referencing a player
- Overlay precision matches confidence (circle vs zone)

---

## Library/Framework Requirements

### LLM Backend
- **Production:** Bedrock (Nova Pro)
- **Local Dev:** Ollama (qwen2.5:3b)
- **Hackathon:** AMD droplet (Qwen2.5-VL-7B-AWQ via SGLang)

### Caching
- In-memory dict for pre-computed Q&A (per session)
- TTL: session duration

---

## Testing Requirements

### Unit Tests
1. Query handler extracts question text
2. Game state prepended to prompt
3. Settings injected correctly
4. Pre-computed cache lookup works
5. KV cache semantic search returns timestamp

### Integration Tests
1. WebSocket query → answer round-trip
2. Latency < 3.5s P95
3. `temporal_context: "limited"` on cache miss
4. Non-football question graceful redirect

### Performance Tests
1. Q&A preempts streaming prefill
2. P95 latency under load

---

## Developer Notes

### Pre-Computed Q&A Generation (Story 1.3)
During notes pipeline, generate Q&A pairs for likely questions:
- "Why is that a red card?" → triggered by red card event
- "Who is number 10?" → triggered by player detection
- "What formation are they playing?" → triggered by tactical analysis

Store in `NotesStore.qa_cache` for O(1) lookup.

### KV Cache Semantic Search
```python
# Embed question, cosine similarity over frame captions
# Return most relevant timestamp
# If similarity < threshold → "limited" temporal context
```

### Commentator Voice
- Same prompt template as live commentary
- Reuse `LiveAgent.call_bedrock()` with Q&A template
- Settings (bias, excitement, knowledge) apply identically

---

## Project Context Reference

From `architecture.md`:
- **GPU Workload Scheduling:** Q&A decode = Priority 1 (highest)
- **KV Cache Retention:** ≥ 120s for temporal grounding
- **Fallback Chain:** Level 3-4 degrades to static context

From `epics.md`:
- Depends on Story 1.3 for pre-computed Q&A pairs
- Feeds Story 2.3 (SplitScreen) with temporal context and overlay coordinates

---

## Status
- **Created:** 2026-05-05
- **Ready for Dev:** Yes
- **Dependencies:** Story 1.3 (pre-computed Q&A), Story 2.4 (player ID for overlay coords)

---

## Dev Agent Record

### Implementation Plan
- Created `agents/qa_agent.py` with QAAgent class extending BaseLiveAgent
- Implemented pre-computed Q&A cache with O(1) lookup (QAPair dataclass)
- Added game state injection via `game_state.to_context_string()`
- Implemented temporal context search over retained KV cache frames
- Added commentary settings (bias, excitement, knowledge_depth)
- Implemented non-football question graceful redirect
- Created `agents/__tests__/test_qa_agent.py` with 16 tests covering all ACs

### Debug Log
- 2026-05-05: Initial implementation complete
- All 16 unit tests passing
- Integration test successful with 4 sample questions

### Completion Notes
✅ Story 2.2 implemented with full test coverage
- QAAgent handles WebSocket query messages
- Pre-computed cache returns answers in < 1s (tap path)
- Game state injection working correctly
- Temporal context search returns full/limited based on similarity threshold
- Non-football questions gracefully redirected
- Integrated into api/server.py WebSocket handler

### File List
- `agents/qa_agent.py` (new)
- `agents/__tests__/test_qa_agent.py` (new)
- `agents/__init__.py` (modified - added exports)
- `models/game_state.py` (modified - added active_players, recent_touches)
- `api/server.py` (modified - integrated parallel Q&A handler)
- `scripts/run_stories_2_2_2_4_parallel.py` (new)
- `_bmad-output/implementation-artifacts/2-2-2-4-agents-summary.md` (new)
- `_bmad-output/implementation-artifacts/2-2-2-4-implementation-complete.md` (new)

### Change Log
- Created QAAgent with pre-computed cache, temporal context search, game state injection
- Added 16 unit tests covering all 6 acceptance criteria
- Integrated into WebSocket handler for parallel execution with PlayerIDAgent
- Updated ConnectionManager to store Q&A runners per session
- Updated WebSocket protocol documentation to include new answer payload fields

---

## Tasks/Subtasks

- [x] **Task 1: Create QAAgent class with pre-computed cache support**
  - [x] Implement QAPair dataclass for cached Q&A
  - [x] Add _normalize_question() for cache lookup
  - [x] Implement _check_precomputed_cache() for O(1) lookup
  - [x] Write tests for cache hit/miss scenarios

- [x] **Task 2: Implement game state injection**
  - [x] Add game_state parameter to handle_query()
  - [x] Prepend game_state.to_context_string() to prompt
  - [x] Include gameState in answer payload
  - [x] Test game state inclusion in answers

- [x] **Task 3: Add temporal context search**
  - [x] Implement _search_kv_cache_temporal_context()
  - [x] Return TemporalContext with timestamp and similarity score
  - [x] Apply 0.3 similarity threshold for full/limited
  - [x] Test temporal context full/limited scenarios

- [x] **Task 4: Implement commentary settings**
  - [x] Add commentary_settings dict (bias, excitement, knowledge_depth)
  - [x] Inject settings into prompt template
  - [x] Test settings injection in prompts

- [x] **Task 5: Handle non-football questions**
  - [x] Implement _is_non_football_question() with keyword detection
  - [x] Return graceful redirect message
  - [x] Test non-football question handling

- [x] **Task 6: Integrate with WebSocket handler**
  - [x] Add _handle_fan_query_parallel() helper
  - [x] Update query message handler in live_audio_ws
  - [x] Include temporal_context, timestamp_ms, player_identification, overlay_coordinates in payload
  - [x] Test WebSocket answer payload structure
