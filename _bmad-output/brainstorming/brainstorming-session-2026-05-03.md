---
stepsCompleted: [1, 2]
selected_approach: 'progressive-flow'
techniques_used: ['dream-fusion-laboratory', 'morphological-analysis', 'six-thinking-hats', 'decision-tree-mapping']
inputDocuments: [".context/streaming-vlm-research.md"]
session_topic: 'PitchAI Hackathon Architecture: Three-Pillar System to Win All Three Tracks'
session_goals: '1. Architecture decisions (SGLang vs vLLM, model strategy per pillar), 2. Multi-agent Peter Drury notes pipeline, 3. Low-latency contextual Q&A with temporal vision grounding, 4. Meaning-preserving style-matching translation pipeline, 5. Convergent demo flow for Hugging Face Space + Reachy Mini'
selected_approach: ''
techniques_used: []
ideas_generated: []
context_file: '.context/streaming-vlm-research.md'
---

# Brainstorming Session Results

**Facilitator:** Deepu
**Date:** 2026-05-03

## Session Overview

**Topic:** PitchAI Hackathon Architecture: Three-Pillar System to Win All Three Tracks

**Goals:**
1. Architecture decisions (serving engine, model strategy per pillar)
2. Multi-agent Peter Drury notes pipeline design
3. Low-latency contextual Q&A with temporal vision grounding
4. Meaning-preserving, style-matching translation pipeline
5. Convergent demo flow that showcases all three pillars
6. Hugging Face Space + Reachy Mini as explicit prize targets

### Context Guidance

Loaded from `.context/streaming-vlm-research.md`:
- AMD Hackathon May 4-10, 2026 with MI300X GPU access
- Three tracks: AI Agents (Track 1), Vision & Multimodal AI (Track 3), Qwen Sponsor Challenge
- StreamingVLM/LiveVLM/StreamMem as model-level streaming frameworks
- Existing multi-agent commentary architecture in PitchAI
- Judging criteria: Application of Technology, Presentation, Business Value, Originality
- User's explicit target: Hugging Face Special Prize + Reachy Mini Wireless

### Three Pillar Architecture (User's Vision)

1. **Commentary Notes Engine** — Multi-agent Peter Drury-style notes → streaming commentary
2. **Contextual Stream Q&A** — Questions grounded in what's happening on screen NOW
3. **Cross-Language Commentary** — Meaning-preserving, style-matching translation with background audio passthrough

## Phase 1: Dream Fusion Laboratory

### Ideas Captured

**[Category UX-1]**: The Split-Screen Timeline
_Concept_: When a user asks a question during live streaming, the screen splits vertically — left half continues showing the live match, right half scrubs back to the exact timestamp where the answer lives with AI-drawn overlays (circles, arrows, offside lines). Same commentator voice explains. Then snaps back to live.
_Novelty_: Not a separate Q&A page — seamless temporal navigation of the stream. The match video becomes the answer medium.

**[Category UX-2]**: Context-Aware Commentary Highlighter
_Concept_: Multi-agent commentary notes aren't static. As the match progresses, the UI actively highlights relevant pre-generated notes. Vision model first detects the match situation (corner, free kick, sub), pulls relevant data. Then the commentary agent decides the narrative beat and surfaces the right note at the right moment.
_Novelty_: Two-stage relevance — vision detects WHAT is happening, agent decides WHY it matters narratively.

**[Category UX-3]**: Commentary Personalization Dial
_Concept_: Three dimensions live-configurable: (1) Bias slider (Team A fan → neutral → Team B fan), (2) Excitement level (whispered → GOOOAL), (3) Knowledge depth (beginner explanations → tactical deep dives). Same AI changes vocabulary, tone, detail, and emotional register.
_Novelty_: Persona transformation on the same underlying commentary — not re-generation, rendering.

**[Category UX-4]**: Dual-View Notes Engine
_Concept_: Same notes engine, two renderings. Commentator dashboard: synced scrolling notes like Spotify lyrics + teleprompter, 40% of screen, continuously updating. Viewer overlay: small trivia cards (5% of screen, 2-line max), fades after 5 seconds, only at key moments.
_Novelty_: One engine, two personas. Professional tool vs bite-sized education.

**[Category UX-5]**: Graceful Model Loading
_Concept_: Raw match video plays immediately on page load. Vision and audio models warm up in background, attach to the stream when ready. Translation switching: mute 2-3s, resume in new language. Content is never blocked.
_Novelty_: Models attach to the stream; they don't hold it hostage.

**[Category UX-6]**: Skip the Landing, Start the Experience
_Concept_: Demo URL opens directly into a single streaming page. No navigation, no "here's what it could look like." All features accessible from one view. The product IS the demo.
_Novelty_: Zero friction between judge and experience.

**[Category DEMO-1]**: The 5-Minute Escalating Narrative
_Concept_: Each minute escalates. 0-1: Dual-view visible (trivia + commentary highlights). 1-3: Split-screen QA with AI overlays. 3-4: Language switch + bias toggle. 4-5: Notes generation + full settings panel. Features compose, never compete.
_Novelty_: Demo as narrative arc. The product reveals itself progressively.

### Viewer vs Commentator: Resolved

| | Commentator View | Viewer View |
|---|---|---|
| What they see | Dashboard with synced scrolling notes — teleprompter + Spotify lyrics. Full sentences, narrative arcs, tactical cues | Small pop-up cards. "Did you know?" One fact. 2-line max. Fades after 5s |
| When it updates | Continuously — next narrative beat always visible before spoken | Sparingly — only at match moments (goal, card, free kick, sub) |
| Why it exists | Professional tool for delivering Peter Drury-quality lines | Education without lecture for new fans |
| UI footprint | 40% of screen | 5% corner, ephemeral |

Same engine. Same data. Two renderings. Demo shows both side-by-side.