# Story 1.2: Streaming Vision Pipeline

Status: **PARTIAL** — vLLM backend works; SGLang + StreamingVLM NOT implemented

## Implementation Notes — Reality Check

**What IS implemented in `streaming/` module:**

- ✅ `streaming/frame_buffer.py` — FrameBuffer class with 8 FPS target, 5-second chunk intervals, quality filtering
- ✅ `streaming/kv_cache_manager.py` — KVCacheManager with 16-second visual window, sliding window pruning
- ✅ `streaming/streaming_bridge.py` — Backend abstraction with TWO backends:
  - `VLLMStreamingBackend` — **WORKS** (vLLM OpenAI-compatible API, frame-by-frame VQA)
  - `StreamingVLMBackend` — **STUB** (imports from `streaming_vlm` package that doesn't exist)

**What is MISSING:**

- ❌ `streaming/sglang_client.py` — Never created (SGLang backend)
- ❌ `streaming/factory.py` — Never created (fallback chain)
- ❌ `streaming_vlm` package — MIT HAN Lab repo not cloned/installed
- ❌ SGLang serving infrastructure — Not deployed

**Integration point:** `api/server.py` imports `StreamingVisionBridge` but only vLLM backend is functional.

**Files created:**
- `streaming/__init__.py` — exports
- `streaming/frame_buffer.py` — 194 lines ✅
- `streaming/kv_cache_manager.py` — 128 lines ✅
- `streaming/streaming_bridge.py` — 627 lines (partial: vLLM works, StreamingVLM is stub)

**Files NOT created:**
- `streaming/sglang_client.py` — ❌
- `streaming/factory.py` — ❌
- `streaming/enums.py` — ❌
- `streaming/types.py` — ❌

**NFRs addressed:**
- NFR-5 (≥5 FPS): ✅ FrameBufferConfig.target_fps = 8.0
- NFR-8 (120s KV cache): ⚠️ KVCacheManager exists but not used with real streaming model
- NFR-9 (fallback <30s): ❌ Fallback chain not implemented

## Story

As a system operator,
I want a streaming vision pipeline that processes video frames at 5 FPS through the vision model and detects match events with confidence scores,
So that the system can react to live match action in real-time.

## Acceptance Criteria — Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| `streaming/factory.py` with fallback | ❌ NOT IMPLEMENTED | File doesn't exist |
| SGLang client at `VLLM_BASE_URL` | ❌ NOT IMPLEMENTED | No SGLang integration |
| Frame sampler at 5 FPS | ✅ IMPLEMENTED | `FrameBuffer` in `frame_buffer.py` |
| KV cache 120s window | ⚠️ PARTIAL | `KVCacheManager` exists but not wired to real streaming model |
| Fallback chain (4 levels) | ❌ NOT IMPLEMENTED | Only documented in tests |

### What Actually Works

**Given** `streaming/streaming_bridge.py` with `VLLMStreamingBackend`
**When** video frames are sent to vLLM endpoint at `http://localhost:8001`
**Then** frames are processed as individual VQA queries (not true streaming)
**And** commentary is generated per-chunk via HTTP to vLLM's OpenAI-compatible API

### What Doesn't Work

- **StreamingVLMBackend** — Import errors: `streaming_vlm.inference.qwen2_5.patch_model` not found
- **SGLang backend** — Never implemented
- **Fallback chain** — No factory, no automatic fallback

## Tasks / Subtasks

- [ ] Task 1: Create streaming package structure
  - [ ] 1.1 Create `streaming/__init__.py` with exports
  - [ ] 1.2 Create `streaming/enums.py` with `StreamingBackend` enum
  - [ ] 1.3 Define `VisionAnalysisResult` dataclass with fields: `frame_timestamp`, `events: List[Dict]`, `confidence`, `fallback_level`

- [ ] Task 2: Implement FrameSampler
  - [ ] 2.1 Create `streaming/frame_sampler.py` with `FrameSampler` class
  - [ ] 2.2 Implement `select_frame(frame: np.ndarray, timestamp: float) -> Optional[np.ndarray]` with 200ms delta check
  - [ ] 2.3 Implement diversity scoring using histogram comparison to avoid redundant frames
  - [ ] 2.4 Configurable target FPS via env var `VISION_TARGET_FPS` (default: 5)

- [ ] Task 3: Implement KVCacheManager
  - [ ] 3.1 Create `streaming/kv_cache.py` with `KVCacheManager` class
  - [ ] 3.2 Implement `add_frame(frame: np.ndarray, timestamp: float)` with circular buffer
  - [ ] 3.3 Implement `get_context_window(seconds: float = 120.0) -> List[np.ndarray]`
  - [ ] 3.4 Eviction policy: drop oldest first when `max_frames` exceeded
  - [ ] 3.5 Configurable via `KV_CACHE_SECONDS` (default: 120) and `KV_CACHE_MAX_FRAMES`

- [ ] Task 4: Implement SGLang Client
  - [ ] 4.1 Create `streaming/sglang_client.py` with `SGLangClient` class
  - [ ] 4.2 Implement `__init__(self, base_url: str, api_key: Optional[str] = None)` reading `VLLM_BASE_URL` from env
  - [ ] 4.3 Implement `analyze_frame(frame: np.ndarray) -> VisionAnalysisResult` via HTTP POST to `{base_url}/v1/chat/completions`
  - [ ] 4.4 Parse response to extract events: goal, card, substitution, etc. with confidence scores
  - [ ] 4.5 Connection timeout: 30 seconds, then trigger fallback

- [ ] Task 5: Implement Streaming Backend Factory
  - [ ] 5.1 Create `streaming/factory.py` with `get_streaming_backend(backend: Optional[str] = None) -> BaseStreamingClient`
  - [ ] 5.2 Backend selection: env var `STREAMING_BACKEND` ("sglang", "vllm", "mock")
  - [ ] 5.3 Follow `data_sources/factory.py` pattern with fallback chain
  - [ ] 5.4 Mock backend for development without GPU

- [ ] Task 6: Integration with Existing WebSocket
  - [ ] 6.1 Wire `SGLangClient` into `api/server.py` video_stream_ws handler
  - [ ] 6.2 Broadcast `tactical_detection` messages: `{"type": "tactical_detection", "events": [...], "timestamp": "ISO8601"}`
  - [ ] 6.3 Integrate `FrameSampler` and `KVCacheManager` into the video processing loop

## Dev Notes — AS OF 2026-05-05

### What Was Built vs What Was Planned

**Built:**
- ✅ `streaming/frame_buffer.py` — Frame buffering, chunk formation (5-second chunks, 8 FPS target)
- ✅ `streaming/kv_cache_manager.py` — KV cache data structures (not wired to real streaming model)
- ✅ `streaming/streaming_bridge.py` — Abstraction with two backends:
  - `VLLMStreamingBackend` — Works via vLLM OpenAI-compatible API
  - `StreamingVLMBackend` — Stub (imports missing `streaming_vlm` package)

**NOT Built:**
- ❌ `streaming/sglang_client.py` — SGLang integration never implemented
- ❌ `streaming/factory.py` — Fallback chain never implemented
- ❌ `streaming_vlm` package — MIT HAN Lab repo never cloned/installed
- ❌ SGLang serving — Never deployed

### What We're Actually Building (Remaining Work)

The **true streaming vision backbone** still needs:
1. Clone + install StreamingVLM from MIT HAN Lab
2. Serve via SGLang OR use StreamingVLM native PyTorch inference
3. Implement fallback chain factory
4. Wire KV cache to actual streaming model

### Architecture Debt

**Factory pattern:** Documented but not implemented. `data_sources/factory.py` has `FallbackStatsRetriever` pattern to follow.

**Fallback Chain:** Only exists in `scripts/test_fallback_chain.py` tests — no actual implementation.

**SGLang:** Mentioned throughout docs but zero code exists.

### NFRs Addressed

| NFR | Target | How This Story Delivers |
|-----|--------|------------------------|
| NFR-5 | ≥ 5 FPS | FrameSampler throttles to 5 FPS minimum |
| NFR-8 | 120s KV cache | KVCacheManager retains 120s context |
| NFR-9 | Fallback < 30s | Factory triggers fallback on connection timeout |
| NFR-3 | Cold start < 20s | Video plays immediately; model attaches in background |

### Environment Variables

```bash
# Streaming backend selection
STREAMING_BACKEND=sglang  # sglang, vllm, mock

# Vision model endpoint
VLLM_BASE_URL=http://localhost:8000

# Frame sampling
VISION_TARGET_FPS=5  # Minimum 5, max depends on GPU

# KV cache
KV_CACHE_SECONDS=120
KV_CACHE_MAX_FRAMES=600  # At 5 FPS, 120s = 600 frames
```

### Testing Requirements

- Unit test: FrameSampler delta check (reject frames < 200ms apart)
- Unit test: FrameSampler diversity scoring (prefer high-diversity frames)
- Unit test: KVCacheManager circular buffer (evict oldest when full)
- Unit test: KVCacheManager.get_context_window(120.0) returns correct slice
- Integration test: SGLangClient.analyze_frame() parses events correctly
- Integration test: Factory falls back when primary backend unavailable

Test file: `tests/streaming/test_frame_sampler.py`, `tests/streaming/test_kv_cache.py`, `tests/streaming/test_sglang_client.py`

### Files Being Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `streaming/__init__.py` | **NEW** | Package exports |
| `streaming/enums.py` | **NEW** | StreamingBackend enum |
| `streaming/types.py` | **NEW** | VisionAnalysisResult dataclass |
| `streaming/frame_sampler.py` | **NEW** | Frame selection logic |
| `streaming/kv_cache.py` | **NEW** | KV cache window management |
| `streaming/sglang_client.py` | **NEW** | SGLang HTTP client |
| `streaming/factory.py` | **NEW** | Backend factory with fallback |
| `api/server.py` | **MODIFY** | Wire streaming into video_stream_ws |
| `tests/streaming/` | **NEW** | Test files |

### Existing Code to Be Aware Of

`agents/vision_agent.py` — Current vision agent that processes frames. This story's streaming pipeline may replace or wrap it. Check if `VisionAgent.process_frame()` is used elsewhere before removing.

`api/server.py` lines 628-790 — Current `video_stream_ws` handler with GameState tracking. Wire the streaming pipeline into this handler's frame processing loop.

`data_sources/factory.py` — Pattern to follow for `streaming/factory.py` with fallback chain.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 1.2](#story-12-streaming-vision-pipeline)
- [Source: _bmad-output/planning-artifacts/architecture.md — SGLang + StreamingVLM](#decision-sglang--streamingvlm-primary-fallback-1)
- [Source: _bmad-output/planning-artifacts/architecture.md — 4-Level Fallback Chain](#ranked-fallback-chain)
- [Source: _bmad-output/planning-artifacts/architecture.md — GPU Workload Scheduling](#gpu-workload-scheduling-single-mi300x)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — VideoCanvas UX-DR5](#component-specifications)
- [Source: models/narrative_beat.py — Dataclass pattern]
- [Source: data_sources/factory.py — Factory pattern with fallback]

## Dev Agent Record

### Agent Model Used

Claude Code (existing implementation verified)

### Debug Log References — CORRECTED

- `streaming/streaming_bridge.py` (627 lines) — VLLM backend works; StreamingVLM is stub
- `streaming/frame_buffer.py` (194 lines) — Complete
- `streaming/kv_cache_manager.py` (128 lines) — Complete but not wired to real streaming model
- WebSocket `/ws/video/streaming` at `api/server.py:1472-1727` — Integrated but only vLLM works

### Completion Notes — CORRECTED

**What actually works:**
- FrameBuffer: 8 FPS target, 5-second chunk intervals, quality filtering ✅
- VLLMStreamingBackend: Calls vLLM `/v1/chat/completions` with vision ✅
- WebSocket endpoint: Fully wired ✅

**What doesn't work:**
- KVCacheManager: Data structures exist but NOT used with real streaming model ⚠️
- StreamingVLMBackend: Imports fail — `streaming_vlm` package missing ❌
- SGLang backend: Never implemented ❌
- Fallback chain: Only in tests, no implementation ❌

### File List — STATUS

**Existing (working):**
- `streaming/__init__.py` — exports
- `streaming/frame_buffer.py` — frame sampling and chunk formation ✅
- `streaming/kv_cache_manager.py` — KV cache data structures ⚠️
- `streaming/streaming_bridge.py` — VLLM backend works, StreamingVLM is stub ⚠️
- `api/server.py` — `/ws/video/streaming` WebSocket handler ✅

**Missing (need implementation):**
- `streaming/sglang_client.py` — ❌
- `streaming/factory.py` — ❌
- `streaming/enums.py` — ❌
- `streaming/types.py` — ❌
- `streaming_vlm/` package — ❌ (external repo)

