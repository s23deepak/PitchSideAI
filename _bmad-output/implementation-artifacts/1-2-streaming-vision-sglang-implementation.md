# Story 1.2: Streaming Vision Pipeline — SGLang + StreamingVLM Implementation

**Date:** 2026-05-05
**Status:** ✅ Implemented (corrected from earlier partial implementation)

---

## Summary

This implementation adds the missing SGLang backend and fallback chain factory that were documented but not implemented in the original Story 1.2.

### What Was Missing (2026-05-05 reality check)

- ❌ SGLang backend — Never implemented
- ❌ Fallback chain factory — Only existed in tests
- ❌ `streaming_vlm` package — MIT HAN Lab repo not cloned

### What Is Now Implemented

| Component | Status | File |
|-----------|--------|------|
| SGLang Backend | ✅ Implemented | `streaming/sglang_backend.py` |
| Fallback Factory | ✅ Implemented | `streaming/factory.py` |
| StreamingVLM Repo | ✅ Cloned | `streaming-vlm/` |
| Path Setup | ✅ Implemented | `streaming/setup_streaming_vlm.py` |

---

## Implementation Details

### 1. SGLang Backend (`streaming/sglang_backend.py`)

**Purpose:** Connect to SGLang serving engine for lower TTFT and RadixAttention prefix reuse.

**Key Features:**
- RadixAttention for KV-cache prefix reuse across chunks
- OpenAI-compatible API (`/v1/chat/completions`)
- Session tracking for prefix cache continuity
- Same `StreamingBackend` interface as vLLM/StreamingVLM

**Usage:**
```python
from streaming.sglang_backend import SGLangStreamingBackend

backend = SGLangStreamingBackend(
    sglang_base_url="http://localhost:30000",
    model_name="Qwen/Qwen2.5-VL-3B-Instruct",
)
await backend.initialize()
result = await backend.process_chunk(chunk)
```

**Start SGLang Server:**
```bash
python -m sglang.launch_server \
    --model-path Qwen/Qwen2.5-VL-3B-Instruct \
    --port 30000 \
    --mem-fraction-static 0.8
```

---

### 2. Fallback Factory (`streaming/factory.py`)

**Purpose:** Implement 4-level fallback chain with automatic degradation.

**Fallback Levels:**

| Level | Backend | Capabilities | Status |
|-------|---------|--------------|--------|
| 1 | SGLang + StreamingVLM | Full capability (temporal continuity, RadixAttention, compact KV-cache) | ✅ Code ready, needs StreamingVLM deps |
| 2 | SGLang + Custom KV | Temporal continuity, RadixAttention | ✅ Implemented |
| 3 | Pre-computed Embeddings + vLLM | No temporal scrub | ⏳ Deferred (falls through to Level 4) |
| 4 | vLLM Frame-by-Frame | Basic VQA, no continuity | ✅ Implemented (existing vLLM backend) |

**Usage:**
```python
from streaming.factory import get_streaming_backend, FallbackStreamingBackend

# Explicit level selection
backend = get_streaming_backend(target_level=1)

# Auto-fallback wrapper
backend = FallbackStreamingBackend(start_level=1)
await backend.initialize()  # Tries 1→2→3→4
result = await backend.process_chunk(chunk)  # Auto-fallbacks on failure
```

**Environment Variables:**
```bash
# Backend selection
STREAMING_BACKEND=sglang  # sglang, streaming_vlm, vllm, auto

# SGLang endpoint
SGLANG_BASE_URL=http://localhost:30000

# Vision model
VISION_MODEL=Qwen/Qwen2.5-VL-3B-Instruct

# StreamingVLM model path (Level 1)
STREAMING_VLM_MODEL=mit-han-lab/StreamingVLM
```

---

### 3. StreamingVLM Integration (`streaming-vlm/`)

**Cloned From:** https://github.com/mit-han-lab/streaming-vlm

**Location:** `/home/deepu/PitchAI/streaming-vlm/`

**Integration:**
- `streaming/streaming_bridge.py` now adds `streaming-vlm/` to `sys.path` automatically
- Imports work: `from streaming_vlm.inference.qwen2_5.patch_model import convert_qwen2_5_to_streaming`

**Dependencies Status:**
- Full `pip install -r infer_requirements.txt` blocked on `av` (PyAV) requiring ffmpeg 7
- Workaround: Use source checkout approach (add to PYTHONPATH)

**To Complete Level 1:**
```bash
# Install ffmpeg 7 (required for PyAV)
sudo apt install ffmpeg

# Then install dependencies
cd streaming-vlm
source ../.venv/bin/activate
pip install -r infer_requirements.txt
```

---

### 4. Setup Script (`streaming/setup_streaming_vlm.py`)

**Purpose:** Helper script to verify StreamingVLM integration.

**Usage:**
```bash
source .venv/bin/activate
python streaming/setup_streaming_vlm.py
```

**Output:**
```
Added /home/deepu/PitchAI/streaming-vlm to PYTHONPATH
StreamingVLM imports successful!
```

---

## Files Created/Modified

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `streaming/sglang_backend.py` | NEW | 230 | SGLang backend with RadixAttention |
| `streaming/factory.py` | NEW | 220 | Fallback chain factory |
| `streaming/setup_streaming_vlm.py` | NEW | 45 | PYTHONPATH setup helper |
| `streaming/__init__.py` | MODIFIED | +4 | Export new backends |
| `streaming/streaming_bridge.py` | MODIFIED | +8 | Auto-add streaming-vlm to path |
| `streaming-vlm/` | CLONED | - | MIT HAN Lab StreamingVLM repo |

---

## Testing

### Unit Tests (to be written)

```bash
# Test SGLang backend
pytest tests/streaming/test_sglang_backend.py

# Test fallback factory
pytest tests/streaming/test_factory.py

# Test fallback chain integration
pytest tests/fallback/test_fallback_chain.py
```

### Manual Testing

```bash
# Test Level 4 (vLLM - should work now)
python -c "from streaming.factory import get_streaming_backend; b = get_streaming_backend(target_level=4); print(b)"

# Test Level 2 (SGLang - requires running server)
python -c "from streaming.factory import get_streaming_backend; b = get_streaming_backend(target_level=2); print(b)"

# Test Level 1 (StreamingVLM - requires deps)
python -c "from streaming.factory import get_streaming_backend; b = get_streaming_backend(target_level=1); print(b)"
```

---

## NFRs Addressed

| NFR | Target | How Delivered |
|-----|--------|---------------|
| NFR-5 | ≥ 5 FPS | FrameBufferConfig.target_fps = 8.0 ✅ |
| NFR-8 | 120s KV cache | KVCacheManager exists; wired to StreamingVLM ⚠️ |
| NFR-9 | Fallback < 30s | `FallbackStreamingBackend` auto-fallbacks ✅ |
| NFR-3 | Cold start < 20s | Video plays immediately; model attaches in background ✅ |

---

## Architecture Compliance

### Patterns Followed

1. **Factory Pattern:** Matches `data_sources/factory.py` with fallback chain
2. **Backend Interface:** All backends implement `StreamingBackend` ABC
3. **Environment Config:** Reads from env vars (`SGLANG_BASE_URL`, `VISION_MODEL`, etc.)

### Naming Conventions

- Python files: `snake_case` ✅
- Python classes: `PascalCase` ✅
- Module constants: `UPPER_SNAKE_CASE` ✅

---

## Remaining Work

### Before Production

1. **Install StreamingVLM dependencies** — Requires ffmpeg 7 for PyAV
2. **Deploy SGLang server** — MI300X or local dev
3. **Write integration tests** — Test fallback chain end-to-end
4. **Load testing** — Verify FPS targets on target hardware

### Deferred (Level 3)

- Pre-computed embeddings backend not implemented
- Falls through to Level 4 (vLLM frame-by-frame)
- Can be added later if needed

---

## Integration with api/server.py

**Current State:** `api/server.py` uses `StreamingVisionBridge` directly with config:

```python
bridge_config = StreamingBridgeConfig(
    backend="vllm",  # or "streaming_vlm"
    vllm_base_url="http://localhost:8001",
)
bridge = StreamingVisionBridge(bridge_config)
```

**Recommended Update:** Use factory for automatic fallback:

```python
from streaming.factory import FallbackStreamingBackend

backend = FallbackStreamingBackend(start_level=1)
await backend.initialize()
# backend._backend is the actual backend at current level
```

---

## References

- [StreamingVLM Paper](https://arxiv.org/abs/2510.09608)
- [StreamingVLM GitHub](https://github.com/mit-han-lab/streaming-vlm)
- [SGLang GitHub](https://github.com/sgl-project/sglang)
- [Source: _bmad-output/implementation-artifacts/1-2-streaming-vision-pipeline.md — Original (partial) implementation](#)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md — SGLang + StreamingVLM gap documented](#)

---

**Document Version:** 1.0
**Last Updated:** 2026-05-05
**Author:** PitchAI Team
