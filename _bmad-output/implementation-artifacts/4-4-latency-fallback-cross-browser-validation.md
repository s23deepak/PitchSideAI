# Story 4.4: Latency, Fallback & Cross-Browser Validation

**Epic:** 4 — Deployment, Polish & Community Readiness  
**Status:** ready-for-dev  
**Created:** 2026-05-05  
**Last Updated:** 2026-05-05

---

## User Story

As a developer shipping for hackathon judging,
I want to verify that all latency budgets, fallback levels, and cross-browser compatibility requirements are met,
So that the 5-minute judge demo runs without a single visible failure.

---

## Acceptance Criteria

### Latency Budget Validation (NFR-1 to NFR-5)

**Given** latency budgets are defined in NFRs
**When** benchmarking under single-user load
**Then** Audio Q&A responds in under 3.5 seconds end-to-end (speech end → STT → LLM → first text token), measured at P95 (NFR-1)
**And** Language switch completes in under 3 seconds with less than 500ms audio silence (NFR-2)
**And** Cold start loads video within 20 seconds of page open (NFR-3)
**And** Commentary TTFT is under 500ms from match event detection (NFR-4)
**And** Vision frame processing maintains a minimum of 5 FPS on MI300X (NFR-5).

### Fallback Chain Validation (NFR-9)

**Given** the 4-level fallback chain exists
**When** each fallback level is tested
**Then** Level 1 (SGLang + StreamingVLM): all features functional at full capability
**And** Level 2 (SGLang + Custom KV Window): loses StreamingVLM optimizations but retains temporal continuity
**And** Level 3 (Pre-computed Embeddings + vLLM): loses temporal scrub, Q&A degrades to static context
**And** Level 4 (vLLM Frame-by-Frame): no temporal continuity, baseline functionality
**And** fallback activation completes within 30 seconds at each level
**And** the UX communicates degradation calmly at each level (Story 4.3 graceful degradation).

### Memory Budget Validation (NFR-6 to NFR-8)

**Given** memory budgets are defined
**When** monitoring resource usage
**Then** HF Space container consumes under 12GB RAM before model loading (NFR-6)
**And** MI300X VRAM consumption does not exceed 60GB: Qwen2.5-VL-7B-AWQ (~7-9GB) + KV cache buffer (~20-30GB) + agent LLM context (~5-10GB) + overhead (~10GB) (NFR-7)
**And** KV cache retains a minimum of 120 seconds of visual context (NFR-8).

### Player Identification Accuracy (NFR-11)

**Given** player identification on the demo video
**When** tested with known players under normal camera angles and lighting
**Then** identification accuracy exceeds 90% on known players
**And** all misidentifications include uncertainty qualifiers in output.

### Cross-Browser Compatibility (UX-DR25 Phase 4)

**Given** testing on Chrome, Firefox, and Edge
**When** running the full demo flow
**Then** video autoplay works across all browsers
**And** Browser Web Speech API functions correctly (primary: Chrome)
**And** WebSocket connection and reconnection behave identically
**And** canvas/SVG rendering is consistent across browsers
**And** animation performance is smooth (60fps CSS, 5 FPS canvas) across browsers.

### Chaos Testing (UX-DR25 Phase 4)

**Given** chaos testing scenarios
**When** the following scenarios are tested
**Then** flood of 10 events in 5 seconds → priority queue drops correctly, no UI freeze or crash
**And** browser resize during canvas draw → dimension guard catches mismatch, skips frame, re-syncs
**And** STT timeout (Chrome `onend` bug) → 15s timeout auto-cancels empty recording
**And** WebSocket drop mid-Q&A → answer completes from cached context if possible, reconnects silently
**And** compound failure (vision + stats both degraded) → single calm fallback message, no error cascade
**And** GPU endpoint unreachable → fallback chain activates within 30s, Space continues serving frontend.

---

## Technical Requirements

### Files to Create

| File | Action | Purpose |
|------|--------|---------|
| `scripts/benchmark_latency.py` | CREATE | Latency benchmarking script for NFR-1 to NFR-5 |
| `scripts/test_fallback_chain.py` | CREATE | Fallback chain validation script |
| `scripts/chaos_test.py` | CREATE | Chaos testing scenarios |
| `scripts/cross_browser_test.py` | CREATE | Cross-browser compatibility test runner |
| `tests/latency/` | CREATE | Latency test suite |
| `tests/fallback/` | CREATE | Fallback validation tests |
| `tests/chaos/` | CREATE | Chaos test scenarios |
| `VALIDATION_REPORT.md` | CREATE | Comprehensive validation report template |

### Benchmark Scripts

#### Latency Benchmarking (`scripts/benchmark_latency.py`)

```python
#!/usr/bin/env python3
"""
Latency Benchmarking for PitchAI NFR Validation

Measures:
- NFR-1: Audio Q&A response time (< 3.5s end-to-end, P95)
- NFR-2: Language switch latency (< 3s total, < 500ms silence)
- NFR-3: Cold start time (< 20s to video play)
- NFR-4: Commentary TTFT (< 500ms from event detection)
- NFR-5: Vision frame processing (>= 5 FPS on MI300X)

Usage:
    python scripts/benchmark_latency.py --nfr NFR-1 --runs 100
    python scripts/benchmark_latency.py --all  # Run all NFRs
"""

import asyncio
import time
import statistics
from dataclasses import dataclass
from typing import List, Dict
import json

@dataclass
class BenchmarkResult:
    nfr: str
    target: float
    unit: str
    measurements: List[float]
    p50: float
    p95: float
    p99: float
    passed: bool

async def measure_nfr1_audio_qa(runs: int = 100) -> BenchmarkResult:
    """Measure audio Q&A end-to-end latency (NFR-1)"""
    measurements = []
    for i in range(runs):
        start = time.perf_counter()
        # Simulate: speech end → STT → LLM → first token
        # Hook into existing STT/LLM pipeline
        await simulate_qa_pipeline()
        end = time.perf_counter()
        measurements.append((end - start) * 1000)  # Convert to ms
    
    return BenchmarkResult(
        nfr="NFR-1",
        target=3500,  # 3.5 seconds
        unit="ms",
        measurements=measurements,
        p50=statistics.median(measurements),
        p95=sorted(measurements)[int(len(measurements) * 0.95)],
        p99=sorted(measurements)[int(len(measurements) * 0.99)],
        passed=sorted(measurements)[int(len(measurements) * 0.95)] <= 3500
    )

async def measure_nfr2_language_switch(runs: int = 50) -> BenchmarkResult:
    """Measure language switch latency (NFR-2)"""
    measurements = []
    silence_measurements = []
    for i in range(runs):
        start = time.perf_counter()
        # Measure total switch time and audio silence duration
        total_time, silence_time = await simulate_language_switch()
        measurements.append(total_time * 1000)
        silence_measurements.append(silence_time * 1000)
    
    p95_silence = sorted(silence_measurements)[int(len(silence_measurements) * 0.95)]
    return BenchmarkResult(
        nfr="NFR-2",
        target=3000,  # 3 seconds total, < 500ms silence
        unit="ms",
        measurements=measurements,
        p50=statistics.median(measurements),
        p95=sorted(measurements)[int(len(measurements) * 0.95)],
        p99=sorted(measurements)[int(len(measurements) * 0.99)],
        passed=sorted(measurements)[int(len(measurements) * 0.95)] <= 3000 and p95_silence <= 500
    )

# ... additional NFR measurement functions

async def main():
    results = []
    results.append(await measure_nfr1_audio_qa())
    results.append(await measure_nfr2_language_switch())
    # ... run all NFRs
    
    # Print results
    print("\n=== Latency Benchmark Results ===\n")
    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{result.nfr}: {status}")
        print(f"  Target: < {result.target}{result.unit}")
        print(f"  P50: {result.p50:.2f}{result.unit}")
        print(f"  P95: {result.p95:.2f}{result.unit} (target: < {result.target})")
        print(f"  P99: {result.p99:.2f}{result.unit}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
```

#### Fallback Chain Test (`scripts/test_fallback_chain.py`)

```python
#!/usr/bin/env python3
"""
Fallback Chain Validation

Tests the 4-level fallback chain:
- Level 1: SGLang + StreamingVLM (full capability)
- Level 2: SGLang + Custom KV Window (loses StreamingVLM optimizations)
- Level 3: Pre-computed Embeddings + vLLM (loses temporal scrub)
- Level 4: vLLM Frame-by-Frame (no temporal continuity)

Usage:
    python scripts/test_fallback_chain.py --level 1
    python scripts/test_fallback_chain.py --all
"""

import sys
sys.path.insert(0, 'api')
sys.path.insert(0, 'streaming')

from streaming.factory import StreamingBackendFactory
from streaming.fallback import FallbackChain

async def test_fallback_level(level: int):
    """Test specific fallback level functionality"""
    factory = StreamingBackendFactory(target_level=level)
    backend = factory.create()
    
    # Test capabilities at this level
    capabilities = {
        'temporal_continuity': await backend.test_temporal_continuity(),
        'streaming_optimizations': await backend.test_streaming_opts(),
        'temporal_scrub': await backend.test_temporal_scrub(),
    }
    
    expected = {
        1: {'temporal_continuity': True, 'streaming_optimizations': True, 'temporal_scrub': True},
        2: {'temporal_continuity': True, 'streaming_optimizations': False, 'temporal_scrub': True},
        3: {'temporal_continuity': False, 'streaming_optimizations': False, 'temporal_scrub': False},
        4: {'temporal_continuity': False, 'streaming_optimizations': False, 'temporal_scrub': False},
    }
    
    return capabilities == expected[level]

async def test_fallback_activation_time():
    """Test that fallback activation completes within 30 seconds"""
    import time
    start = time.perf_counter()
    
    # Simulate primary failure and measure fallback activation
    chain = FallbackChain()
    activated = await chain.activate_fallback()
    
    elapsed = time.perf_counter() - start
    return elapsed <= 30 and activated
```

#### Chaos Testing (`scripts/chaos_test.py`)

```python
#!/usr/bin/env python3
"""
Chaos Testing for PitchAI

Tests system resilience under adverse conditions:
1. Event flood (10 events in 5 seconds)
2. Browser resize during canvas draw
3. STT timeout simulation
4. WebSocket drop mid-Q&A
5. Compound failure (vision + stats degraded)
6. GPU endpoint unreachable

Usage:
    python scripts/chaos_test.py --scenario flood
    python scripts/chaos_test.py --all
"""

import asyncio
import random
from typing import Callable, Dict

class ChaosTestRunner:
    def __init__(self):
        self.results = []
    
    async def test_event_flood(self):
        """Test: Flood of 10 events in 5 seconds"""
        # Expected: Priority queue drops correctly, no UI freeze or crash
        from frontend.src.components import MatchInsight
        
        events = [
            {'tag': 'goal', 'timestamp': i * 0.5}
            for i in range(10)
        ]
        
        # Send all events rapidly
        for event in events:
            MatchInsight.receive_event(event)
            await asyncio.sleep(0.5)
        
        # Verify: No crash, queue managed correctly
        assert MatchInsight.queue_size <= 3
        assert MatchInsight.ui_responsive
    
    async def test_resize_during_draw(self):
        """Test: Browser resize during canvas draw"""
        # Expected: Dimension guard catches mismatch, skips frame, re-syncs
        from frontend.src.components import VideoCanvas
        
        initial_size = (1920, 1080)
        VideoCanvas.set_video_dimensions(*initial_size)
        
        # Trigger resize mid-frame
        VideoCanvas.resize(1280, 720)
        
        # Verify: Dimension guard prevented crash
        assert VideoCanvas.frame_skipped
        assert VideoCanvas.dimensions_resynced
    
    async def test_stt_timeout(self):
        """Test: STT timeout (Chrome onend bug)"""
        # Expected: 15s timeout auto-cancels empty recording
        from frontend.src.components import MicButton
        
        # Simulate STT that never fires onend
        MicButton.start_recording()
        await asyncio.sleep(15.1)  # Wait for timeout
        
        # Verify: Auto-cancelled
        assert MicButton.state == 'idle'
        assert MicButton.recording_cancelled
    
    async def test_websocket_drop_mid_qa(self):
        """Test: WebSocket drop mid-Q&A"""
        # Expected: Answer completes from cached context, reconnects silently
        from api.server import ConnectionManager
        
        # Simulate WS drop during Q&A
        await ConnectionManager.simulate_drop()
        
        # Verify: Answer completed, reconnected
        assert ConnectionManager.answer_completed
        assert ConnectionManager.reconnected
    
    async def test_compound_failure(self):
        """Test: Compound failure (vision + stats degraded)"""
        # Expected: Single calm fallback message, no error cascade
        from streaming.fallback import FallbackChain
        from data_sources.factory import FallbackStatsRetriever
        
        # Degrade both vision and stats
        FallbackChain.force_level(4)
        FallbackStatsRetriever.force_fallback('fbref')
        
        # Verify: Single calm message
        message = FallbackChain.get_user_message()
        assert "limited" in message.lower()
        assert not FallbackChain.error_cascade
    
    async def test_gpu_unreachable(self):
        """Test: GPU endpoint unreachable"""
        # Expected: Fallback chain activates within 30s
        from streaming.fallback import FallbackChain
        
        start = asyncio.get_event_loop().time()
        FallbackChain.simulate_gpu_failure()
        elapsed = asyncio.get_event_loop().time() - start
        
        # Verify: Fallback activated within 30s
        assert elapsed <= 30
        assert FallbackChain.level > 1

async def main():
    runner = ChaosTestRunner()
    
    scenarios = {
        'flood': runner.test_event_flood,
        'resize': runner.test_resize_during_draw,
        'stt_timeout': runner.test_stt_timeout,
        'ws_drop': runner.test_websocket_drop_mid_qa,
        'compound': runner.test_compound_failure,
        'gpu_unreachable': runner.test_gpu_unreachable,
    }
    
    print("=== Chaos Test Results ===\n")
    for name, test_fn in scenarios.items():
        try:
            await test_fn()
            print(f"✅ {name}: PASS")
        except AssertionError as e:
            print(f"❌ {name}: FAIL - {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Validation Report Template (`VALIDATION_REPORT.md`)

```markdown
# PitchAI Validation Report

**Date:** 2026-05-05  
**Validator:** [Name]  
**Version:** [Git SHA]

---

## Executive Summary

| Category | Status | Notes |
|----------|--------|-------|
| Latency (NFR 1-5) | ✅ Pass / ❌ Fail | Summary |
| Fallback Chain (NFR-9) | ✅ Pass / ❌ Fail | Summary |
| Memory Budget (NFR 6-8) | ✅ Pass / ❌ Fail | Summary |
| Player ID (NFR-11) | ✅ Pass / ❌ Fail | Summary |
| Cross-Browser | ✅ Pass / ❌ Fail | Summary |
| Chaos Testing | ✅ Pass / ❌ Fail | Summary |

---

## Latency Results

### NFR-1: Audio Q&A Response Time

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| P50 | - | X.XX ms | - |
| P95 | < 3500 ms | X.XX ms | ✅/❌ |
| P99 | - | X.XX ms | - |

**Test Environment:** [Browser, OS, Network]
**Sample Size:** N runs

### NFR-2: Language Switch Latency

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Total Time P95 | < 3000 ms | X.XX ms | ✅/❌ |
| Audio Silence P95 | < 500 ms | X.XX ms | ✅/❌ |

[Continue for all NFRs...]

---

## Fallback Chain Results

| Level | Capabilities | Activation Time | UX Message | Status |
|-------|-------------|-----------------|------------|--------|
| 1 | Full | - | - | ✅ |
| 2 | Temporal only | < 30s | Calm indicator | ✅ |
| 3 | Static context | < 30s | Calm indicator | ✅ |
| 4 | Baseline | < 30s | Calm indicator | ✅ |

---

## Chaos Test Results

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Event Flood | Queue managed, no crash | - | ✅/❌ |
| Resize During Draw | Dimension guard catches | - | ✅/❌ |
| STT Timeout | 15s auto-cancel | - | ✅/❌ |
| WS Drop Mid-Q&A | Complete from cache | - | ✅/❌ |
| Compound Failure | Single calm message | - | ✅/❌ |
| GPU Unreachable | Fallback < 30s | - | ✅/❌ |

---

## Recommendations

[List any issues found and recommended fixes]

---

## Sign-off

- [ ] All latency NFRs pass
- [ ] Fallback chain validated
- [ ] Memory budgets met
- [ ] Cross-browser compatibility confirmed
- [ ] Chaos testing passed

**Ready for hackathon demo:** Yes / No
```

---

## Dev Notes

### Architecture Context

**From Story 4.1 (Docker Build & HF Deployment):**
- Docker multi-stage build serving React from FastAPI `/assets`
- HF Space deployment with `sdk: docker`
- `VLLM_BASE_URL` secret for GPU endpoint configuration

**From Story 4.2 (Self-Guided Demo Mode):**
- LandingPage and VideoPage components exist
- DemoModeProvider for pre-seeded content
- FirstVisitOverlay with localStorage gating

**From Story 4.3 (Design Tokens):**
- All components use PitchAI dark tokens
- shadcn/ui components available
- WCAG 2.1 AA accessibility implemented

**From Architecture (streaming/factory.py):**
- `StreamingBackendFactory` handles backend selection
- `FallbackChain` manages 4-level fallback
- Each level exposes `test_*` methods for validation

### Implementation Approach

1. **Create benchmark scripts** in `scripts/` directory:
   - `benchmark_latency.py` - NFR-1 through NFR-5
   - `test_fallback_chain.py` - Fallback validation
   - `chaos_test.py` - Chaos scenarios
   - `cross_browser_test.py` - Browser compatibility

2. **Create test directories** under `tests/`:
   - `tests/latency/` - Latency test cases
   - `tests/fallback/` - Fallback validation
   - `tests/chaos/` - Chaos test scenarios

3. **Create validation report template** at repo root:
   - `VALIDATION_REPORT.md` with structured sections

4. **Run validation suite**:
   ```bash
   # Latency benchmarks
   python scripts/benchmark_latency.py --all
   
   # Fallback chain
   python scripts/test_fallback_chain.py --all
   
   # Chaos testing
   python scripts/chaos_test.py --all
   
   # Cross-browser (manual + automated)
   python scripts/cross_browser_test.py
   ```

5. **Document results** in `VALIDATION_REPORT.md`

### Testing Strategy

**Latency Testing:**
- Run each NFR benchmark 100 times for statistical significance
- Calculate P50, P95, P99 percentiles
- Compare against NFR targets

**Fallback Testing:**
- Test each level independently
- Verify capability matrix matches expected
- Measure activation time (< 30s requirement)

**Chaos Testing:**
- Run each scenario 10 times
- Verify system recovers gracefully
- No crashes, no error cascades

**Cross-Browser Testing:**
- Chrome (primary - Web Speech API)
- Firefox (secondary)
- Edge (Chromium-based)
- Verify: video autoplay, WebSocket, canvas/SVG, animations

### Performance Considerations

- Benchmark scripts should not interfere with measurement
- Use `time.perf_counter()` for high-precision timing
- Run benchmarks in isolated environment when possible
- Document test environment (browser, OS, network conditions)

---

## Tasks/Subtasks

- [x] Create `scripts/benchmark_latency.py` with NFR-1 through NFR-5 measurements
- [x] Create `scripts/test_fallback_chain.py` with 4-level validation
- [x] Create `scripts/chaos_test.py` with 6 chaos scenarios
- [x] Create `scripts/cross_browser_test.py` for browser compatibility
- [x] Create `tests/latency/` directory with test cases
- [x] Create `tests/fallback/` directory with fallback tests
- [x] Create `tests/chaos/` directory with chaos scenarios
- [x] Create `VALIDATION_REPORT.md` template
- [x] Run full validation suite (unit tests - 31 tests passing)
- [ ] Document results in VALIDATION_REPORT.md (requires HF Space deployment)
- [x] Fix any failing NFRs or chaos tests
- [ ] Re-run validation after fixes (requires HF Space deployment)
- [ ] Sign-off: all validation gates pass (requires HF Space deployment)

---

## Definition of Done

### Implementation Complete (Test Framework)
- [x] All latency NFRs (1-5) benchmark scripts created with P50/P95/P99 metrics
- [x] Fallback chain (4 levels) validation script created with capability matrix
- [x] Cross-browser testing script created (Chrome, Firefox, Edge)
- [x] All 6 chaos scenarios implemented and passing unit tests
- [x] VALIDATION_REPORT.md template created
- [x] All unit tests passing (31 tests: 8 latency + 10 fallback + 13 chaos)

### Deployment Validation (Requires HF Space)
- [ ] Memory budgets verified (HF Space < 12GB, MI300X < 60GB) - run on deployed Space
- [ ] Player identification accuracy > 90% - run with vision model
- [ ] Latency NFRs pass with real measurements - run `scripts/benchmark_latency.py --all`
- [ ] Chaos tests pass in production - run `scripts/chaos_test.py --all`
- [ ] Ready for hackathon demo sign-off - after all above pass

---

## File List

| File | Action | Purpose |
|------|--------|---------|
| `scripts/benchmark_latency.py` | CREATE | NFR-1 to NFR-5 latency benchmarking |
| `scripts/test_fallback_chain.py` | CREATE | 4-level fallback validation |
| `scripts/chaos_test.py` | CREATE | Chaos testing scenarios |
| `scripts/cross_browser_test.py` | CREATE | Browser compatibility tests |
| `tests/latency/` | CREATE | Latency test suite directory |
| `tests/latency/test_latency_benchmark.py` | CREATE | Latency benchmark unit tests (8 tests) |
| `tests/fallback/` | CREATE | Fallback validation test directory |
| `tests/fallback/test_fallback_chain.py` | CREATE | Fallback chain unit tests (10 tests) |
| `tests/chaos/` | CREATE | Chaos test scenarios directory |
| `tests/chaos/test_chaos_scenarios.py` | CREATE | Chaos scenario unit tests (13 tests) |
| `VALIDATION_REPORT.md` | CREATE | Validation report template |

---

## Dev Agent Record

### Implementation Plan

**Approach:** Create validation scripts and test suites for latency, fallback, chaos, and cross-browser testing.

**Technical Decisions:**
1. Used `asyncio` for all benchmark scripts to enable concurrent testing
2. Used `time.perf_counter()` for high-precision timing measurements
3. Implemented simulated pipelines for testing without actual GPU/LLM dependencies
4. Created unit tests using `unittest.IsolatedAsyncioTestCase` for async test support
5. All scripts support both individual test runs (`--scenario`/`--nfr`/`--level`) and batch runs (`--all`)

**Test Results:**
- Latency tests: 8/8 passing
- Fallback tests: 10/10 passing
- Chaos tests: 13/13 passing (1 method name mapping fix applied)

### Completion Notes

✅ Created `scripts/benchmark_latency.py` - NFR-1 through NFR-5 benchmarking with P50/P95/P99 metrics
✅ Created `scripts/test_fallback_chain.py` - 4-level fallback validation with capability matrix
✅ Created `scripts/chaos_test.py` - 6 chaos scenarios (flood, resize, STT timeout, WS drop, compound, GPU unreachable)
✅ Created `scripts/cross_browser_test.py` - Chrome, Firefox, Edge compatibility testing
✅ Created `tests/latency/test_latency_benchmark.py` - 8 unit tests
✅ Created `tests/fallback/test_fallback_chain.py` - 10 unit tests
✅ Created `tests/chaos/test_chaos_scenarios.py` - 13 unit tests
✅ Created `VALIDATION_REPORT.md` - Comprehensive validation report template
✅ All unit tests passing (31 total tests)
✅ Fixed chaos test method name mapping issue

---

## Change Log

- 2026-05-05: Story created via create-story workflow
  - Comprehensive context from epics, architecture, UX specs
  - Previous story intelligence from 4.1, 4.2, 4.3
  - Benchmark scripts, chaos tests, validation report template
- 2026-05-05: Implementation complete
  - Created 4 benchmark/test scripts in `scripts/`
  - Created 3 test directories with unit test suites
  - Created VALIDATION_REPORT.md template
  - All 31 unit tests passing
  - Fixed chaos test method name mapping bug

---

## Senior Developer Review (AI)

**Review Date:** Pending  
**Review Type:** Pending  
**Outcome:** Pending

---

## Definition of Done

- [ ] Story file created with comprehensive developer context
- [ ] All acceptance criteria defined with measurable thresholds
- [ ] Technical requirements include file structure and code patterns
- [ ] Dev Notes provide architecture context and implementation approach
- [ ] Status: ready-for-dev
