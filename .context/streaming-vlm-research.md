# StreamingVLM Research

## Context

StreamingVLM enables real-time continuous video understanding with a compact KV-cache algorithm for football broadcast use.

### Judging Criteria
1. Application of Technology
2. Presentation
3. Business Value
4. Originality

---

## StreamingVLM ([arXiv 2510.09608](https://arxiv.org/abs/2510.09608))

**Source**: MIT HAN Lab (Song Han's group) — [github.com/mit-han-lab/streaming-vlm](https://github.com/mit-han-lab/streaming-vlm)
**Stars**: 969 | **License**: MIT

### Core Innovation

StreamingVLM enables real-time, stable understanding of effectively infinite video by:
1. **Compact KV-cache**: Reuses attention sinks + short window of recent vision tokens + long window of recent text tokens
2. **Training-inference alignment**: SFT on short, overlapped video chunks mimics streaming inference attention patterns — no training on prohibitively long contexts needed
3. **No quadratic cost**: Avoids full-attention blowup and sliding-window pitfalls

### Key Metrics
- **8 FPS** on a single NVIDIA H100
- **66.18% win rate** vs GPT-4o mini on Inf-Streams-Eval (videos averaging 2+ hours)
- Improves general VQA: LongVideoBench +4.30, OVOBench Realtime +5.96
- Evaluated on **LiveSports3k-cc** benchmark

### Architecture

```
Inference: Full attention on short chunks → compact KV-cache maintained across chunks
Training:   SFT Stage 1 (main data) → SFT Stage 2 (high-quality annealing)
```

### How It Works (Inference)
1. Process current video chunk with full attention
2. Retain in KV-cache: attention sinks + recent N vision tokens + recent M text tokens
3. Drop everything else — constant memory, no recomputation
4. Next chunk reuses cached states, only computes new frames

### Built On
- Qwen-VL (same family as PitchAI's current `Qwen2.5-VL-3B-Instruct-AWQ`)

---

## LiveVLM ([arXiv 2505.15269](https://arxiv.org/abs/2505.15269))

**Source**: SJTU Zhao Lab — [github.com/sjtu-zhao-lab/LiveVLM](https://github.com/sjtu-zhao-lab/LiveVLM)
**Venue**: DAC 2026 | **License**: MIT | **Stars**: 1 (new repo, Mar 2026)

### Core Innovation

LiveVLM is a **training-free, query-agnostic** framework for online video understanding. Unlike StreamingVLM which requires SFT for chunked attention patterns, LiveVLM works with off-the-shelf Video LLMs without any retraining. Two key mechanisms:

1. **Vision Sink Bucketing (VSB)**: Processes video streams in real time, retaining long-term video details while eliminating redundant KVs. Uses vision-to-vision attention scores as the compression metric and maximizes contextual coverage during compression. Effectively acts as a diversity-aware KV eviction policy — keeps both high-attention "sink" tokens and scattered tokens across the temporal span.

2. **Position-agnostic KV Retrieval (PaR)**: Since query-agnostic compression inevitably drops some query-relevant information, PaR retrieves relevant KVs from pre-compression cache at inference time. The key insight: decoupling positional embeddings makes key tensors more similar across positions, enabling efficient page-granularity retrieval without storing full position-specific KV.

### Architecture

```
Streaming chunks → Full attention per chunk → VSB compresses KV cache (diversity scoring)
                                              ↓
                                         Fixed-size KV memory maintained across chunks
                                              ↓
                                    At QA time: PaR retrieves relevant KVs from backup
```

### Key Parameters

| Parameter | Description | Default |
|---|---|---|
| `cache_size` | Total KV cache token budget | 12000 |
| `recent_frames` | Number of frames with recent tokens always retained | 2 |
| `clip_frame_num` | Video chunk size processed at once | 32 |
| `scatter_ratio` | Fraction of cache reserved for diversity-scattered tokens (vs top-K) | 0.5 |
| `retr_ratio` | Fraction of tokens retrieved from pre-compression cache for QA | 0.4 |

### Key Metrics
- Built on **LLaVA-OneVision** (LLaVA-NeXT based, unlike PitchAI's Qwen)
- Evaluated on MLVU and standard long video QA benchmarks
- SOTA among training-free query-agnostic methods; competitive with training-based approaches
- Code is based on LLaVA-NeXT and ReKV

### PitchAI Relevance
- **Training-free** — could potentially wrap around existing `Qwen2.5-VL-3B` without retraining
- VSB diversity mechanism is complementary to StreamingVLM's attention-sink approach
- PaR retrieval could enhance commentary accuracy for specific game queries
- Built on different base model family (LLaVA vs Qwen) — would need porting to Qwen-VL architecture

---

## StreamMem ([arXiv 2508.15717](https://arxiv.org/abs/2508.15717))

**Source**: Yanlai Yang, Zhuokai Zhao, Satya Narayan Shukla, Aashu Singh, Shlok Kumar Mishra, Lizhu Zhang, Mengye Ren (UMD + collaborators)
**Date**: August 2025 | **Status**: Paper, no public implementation repo yet

### Core Innovation

StreamMem is a **query-agnostic KV cache memory** mechanism for streaming video understanding. The key problem it addresses: existing visual compression methods require either encoding the entire visual context before compression, or having access to the questions in advance — both impractical for long video and multi-turn conversation settings.

StreamMem's approach:
1. **Streaming encoding**: New video frames are encoded as they arrive, no need to pre-load entire video
2. **Generic query token compression**: Uses attention scores between visual tokens and a small set of learnable/curated **generic query tokens** to decide which KV entries to keep. These generic tokens proxy for future real queries, making compression query-agnostic.
3. **Fixed-size KV memory**: Maintains a constant memory footprint regardless of video duration, enabling efficient QA in memory-constrained long-video scenarios.

### Architecture

```
Frame stream → Vision encoder → Visual tokens
                                    ↓
                           Attention vs. generic query tokens → compression score
                                    ↓
                           Fixed-size KV memory (constant memory)
                                    ↓
                           At QA time: full attention over compressed memory
```

### How It Compares to StreamingVLM and LiveVLM

| Aspect | StreamingVLM | LiveVLM | StreamMem |
|---|---|---|---|
| **Training required** | Yes (SFT on chunks) | No (training-free) | No (training-free) |
| **Compression metric** | Attention sinks + recency | Vision-to-vision attention + diversity | Vision-to-generic-query attention |
| **Query awareness** | Query-agnostic | Query-agnostic (but PaR adds query-time retrieval) | Query-agnostic |
| **Retrieval** | No retrieval | PaR: page-granularity from backup | No retrieval (compression is the memory) |
| **Base model** | Qwen-VL | LLaVA-OneVision | MLLM-agnostic |
| **Public code** | Yes | Yes | Not yet |

### Key Metrics
- Evaluated on 3 long video understanding + 2 streaming video QA benchmarks
- SOTA in query-agnostic KV cache compression
- Competitive with query-aware compression approaches (which have an easier task)

### Related: StreamMemBench (ICLR 2026 Workshop)
- Separate benchmark project: [github.com/landian60/StreamMemBench](https://github.com/landian60/StreamMemBench)
- Evaluates memory systems in streaming interaction settings (4 protocols: Formation, Management, Retrieval, Application)
- Not the StreamMem model itself, but relevant for benchmarking streaming memory approaches

### PitchAI Relevance
- Generic query token approach could be adapted to sports domain (sports-specific query tokens)
- Query-agnostic design maps well to live commentary (don't know what the commentator will say next)
- No public implementation yet — would need to replicate from paper
- MLLM-agnostic design means it could work with Qwen-VL family

---

## Real-Time Video Stream Inference: The Full Stack

For real-time video stream inference, the right tools are **model-level frameworks** — StreamingVLM, LiveVLM, and StreamMem — then serve the resulting model via **SGLang** or **vLLM** underneath.

### Model-Level Streaming Frameworks

| Framework | Source | Key Idea | Status |
|---|---|---|---|
| **StreamingVLM** | MIT HAN Lab | Compact KV-cache with attention sinks + sliding windows | Released, 969 stars |
| **LiveVLM** | SJTU (Zhao Lab) | Training-free streaming KV-cache with Vision Sink Bucketing + Position-agnostic Retrieval | Released, DAC'26 |
| **StreamMem** | UMD + independent | Query-agnostic KV memory with generic-query-token attention compression for fixed-size cache | Paper, Aug 2025 |

### Serving Engines for Video Streaming

| Engine | Strengths for Video | Weaknesses |
|---|---|---|
| **SGLang** | Lower TTFT, RadixAttention for prefix reuse across frames, better streaming smoothness | Smaller community than vLLM |
| **vLLM** | Mature, AMD ROCm support, PitchAI already uses it | Higher TTFT, less prefix-sharing optimization |

### Why Neither Engine Alone Solves Continuous Video Streaming

Both SGLang and vLLM serve models — they don't manage video-specific state. You still need to handle:
- **Frame sampling** (which frames to process, at what cadence)
- **KV state management** between chunks (which tokens to keep/drop)
- **Attention windowing** (how far back the model looks)
- **Temporal alignment** (mapping detections to real timestamps)

This is exactly what StreamingVLM provides at the model level.

### Disaggregated Prefill/Decode

Both SGLang and vLLM support separating prefill and decode across different GPUs:
- **Prefill** (expensive): Process incoming video frames through vision encoder + project into KV-cache
- **Decode** (cheap): Generate text commentary from cached visual context

This is valuable for sports commentary because video frame prefill is compute-heavy (vision transformer) while commentary decode is relatively light.

---

## Practical Recommendation for PitchAI

### Recommended Stack

| Layer | Choice | Rationale |
|---|---|---|
| **Primary streaming model** | StreamingVLM | Designed for infinite video streams; same model family as current `Qwen2.5-VL-3B` |
| **Alternative streaming model** | LiveVLM (training-free) | No SFT required; VSB diversity + PaR retrieval; needs porting from LLaVA to Qwen |
| **Future streaming model** | StreamMem | Generic query tokens for query-agnostic compression; no public code yet |
| **Serving engine** | SGLang | Lower TTFT, better streaming smoothness, RadixAttention for frame prefix reuse |
| **Optimization** | Disaggregated prefill/decode | Separate vision frame processing from commentary text generation |

### Migration Path (Current → Target)

```
Current:   vLLM + Qwen2.5-VL-3B → frame-by-frame VisionAgent → multi-agent commentary
Target:    SGLang + StreamingVLM → continuous video understanding → multi-agent commentary
Alt Path:  SGLang + LiveVLM      → training-free continuous vision → multi-agent commentary
Future:    StreamMem style KV memory → fixed-budget streaming for any MLLM
```

### Fallback Plan
If StreamingVLM ROCm port hits issues:
1. Try **LiveVLM** first — training-free, could be easier to get running without custom CUDA kernels
2. Fallback to current vLLM + Qwen2.5-VL pipeline but:
   - Optimize for MI300X memory bandwidth (larger KV-cache → longer temporal context)
   - Implement manual frame-sampling improvements in VisionAgent (borrow VSB diversity scoring)
3. Still a valid Track 3 submission

### Key Risk: ROCm Compatibility
- StreamingVLM developed on NVIDIA H100
- MI300X uses ROCm (AMD's CUDA equivalent)
- PitchAI's .venv already has AMD MI300X vLLM configs — path partially paved
- Custom attention kernels in StreamingVLM may need ROCm-compatible Flash Attention

---

## Implementation Plan

### Day 1-2: Environment + Inference
- Spin up MI300X on AMD Developer Cloud
- Install StreamingVLM inference dependencies (ROCm-compatible PyTorch, flash-attention)
- Run StreamingVLM inference with pre-trained Qwen-VL checkpoint
- Benchmark FPS on MI300X

### Day 3-4: Integration
- Replace PitchAI's per-frame VisionAgent with StreamingVLM streaming inference
- Wire into existing `video_stream_ws` WebSocket endpoint
- Connect streaming visual understanding → GameState → commentary agents
- Test with recorded football footage

### Day 5: Polish
- Frontend UI improvements for real-time commentary
- Record demo video showing live commentary
- Prepare slide deck

### Day 6: Submit
- Publish to Hugging Face Space
- Submit on lablab.ai
- Build-in-public posts (Twitter/LinkedIn)

---

## References

- [StreamingVLM Paper](https://arxiv.org/abs/2510.09608)
- [StreamingVLM GitHub](https://github.com/mit-han-lab/streaming-vlm)
- [StreamingVLM Demo](https://streamingvlm.hanlab.ai)
- [LiveVLM Paper](https://arxiv.org/abs/2505.15269)
- [LiveVLM GitHub](https://github.com/sjtu-zhao-lab/LiveVLM)
- [LiveVLM — ReKV (upstream)](https://github.com/Becomebright/ReKV)
- [StreamMem Paper](https://arxiv.org/abs/2508.15717)
- [StreamMemBench (related benchmark)](https://github.com/landian60/StreamMemBench)

- [AMD AI Developer Program](https://www.amd.com/en/developer/ai-dev-program.html)
- [AMD Developer Cloud](https://www.amd.com/en/developer/resources/cloud-access/amd-developer-cloud.html)
- [ROCm Documentation](https://rocm.docs.amd.com/en/latest/)
- [SGLang](https://github.com/sgl-project/sglang)