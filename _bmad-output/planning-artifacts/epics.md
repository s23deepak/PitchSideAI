---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/architecture.md"
  - "_bmad-output/planning-artifacts/ux-design-specification.md"
---

# PitchAI - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for PitchAI, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: **Multi-Agent Pipeline Execution** — The system shall execute the 7-agent commentary notes pipeline (PlayerResearch, TeamForm, HistoricalContext, Weather, Matchup, News, NoteOrganizer) in three phases: Phase 1 (parallel — PlayerResearch, TeamForm, Historical, Weather, News), Phase 2 (Matchup — depends on player data), Phase 3 (NoteOrganizer — final synthesis). Each agent shall fetch live data from the internet via the 3-layer fallback chain (StatsBomb → Firecrawl → FBref).

FR2: **Progress Callbacks** — The system shall emit progress updates as each agent completes, including agent name, status (running/complete/failed), and items processed (e.g., "22/25 players researched"). Progress shall be broadcast over WebSocket for real-time UI rendering.

FR3: **Dual-View Rendering** — The system shall produce commentary notes in two formats from the same engine: (a) Full Markdown document with narrative arcs, player profiles, tactical previews for the Commentator Dashboard; (b) Individual trivia facts (2-line max) keyed to match event types (goal, card, substitution, free kick) for the Fan Lens overlay.

FR4: **Vision-Triggered Note Highlighting** — During live streaming, the system shall detect match events via the vision model (confidence > 0.6) and broadcast which pre-generated notes are relevant to the current moment. The Commentator Dashboard shall highlight the current narrative beat and show the next 3 upcoming lines.

FR5: **Pre-Match Generation** — The system shall support generating commentary notes before the match begins by accepting a fixture (home team, away team, venue, sport) and running the full 7-agent pipeline. Generated notes shall persist for the duration of the WebSocket session.

FR6: **Player Identification** — The system shall identify players on screen using visual cues (jersey number, position on pitch, movement pattern, build) fused with contextual information (lineup, recent touches). When uncertain, the system shall indicate ambiguity rather than misidentify.

FR7: **Audio Input for Questions** — The system shall accept fan questions via browser Web Speech API (primary) with PushToTalk.jsx + WebSocket binary audio as fallback. The microphone button shall be a floating, semi-transparent element in the bottom-right corner of the video. Hold to record (button turns red), release to submit.

FR8: **STT Confirmation Display** — Before answering, the system shall display the recognized question text for 1.5 seconds with a dismiss (X) button. If the user dismisses, the question is cancelled and no answer is generated.

FR9: **Split-Screen Temporal Navigation** — When a question is submitted, the system shall split the screen vertically: left half continues showing the live match, right half scrubs to the most relevant timestamp based on the question's semantic content. The system shall render AI-drawn overlays (circles, arrows, offside lines) on the relevant frame using canvas/SVG rendering.

FR10: **KV Cache Retention for Temporal Context** — The system shall retain a minimum of 120 seconds of visual context in the KV cache to enable temporal navigation for Q&A. When sufficient context is unavailable for a specific question, the system shall answer with available context and indicate the temporal limitation.

FR11: **Graceful Fallback for Q&A** — When temporal navigation is unavailable (fallback level 3 or 4), the system shall degrade to static contextual answers using pre-computed embeddings or general football knowledge, clearly indicating the degraded mode.

FR12: **Trivia Card Triggering** — The system shall automatically surface trivia cards in the Fan Lens when a vision detection (confidence > 0.6) matches a pre-computed note. Cards shall fade in over 400ms, display for 5 seconds, and fade out. Cards shall never exceed 2 lines of text and shall not obstruct the match ball or active play area.

FR13: **Same-Commentator Voice for Answers** — Q&A responses shall use the same commentator voice and style as live commentary. If commentary settings (bias, excitement, knowledge depth) are configured, Q&A responses shall respect those settings.

FR14: **Language Toggle** — The system shall provide a visible language toggle button. When activated, the system shall mute commentary audio for a maximum of 3 seconds, then resume commentary in the selected language with preserved meaning and emotional register.

FR15: **Meaning-Preserving Translation** — Translation shall preserve semantic meaning and poetic register across languages. "Roma have risen from their ruins" shall carry the same historical allusion and dramatic weight in Spanish — not be replaced with culturally-stereotyped excitement patterns.

FR16: **Trivia Card Translation** — When the commentary language is switched, trivia cards shall also display in the selected language.

FR17: **Commentary Settings** — The system shall expose three live-configurable commentary settings via sliders: (a) Bias — from Team A fan (-1) through Neutral (0) to Team B fan (+1); (b) Excitement — from subdued (0) to maximum (1); (c) Knowledge Depth — from beginner explanations (0) to tactical deep-dive (1). Settings shall be sent via WebSocket `{"type": "settings_update"}` and injected into every subsequent commentary prompt.

FR18: **HF Space Deployment** — The system shall deploy as a Docker container on Hugging Face Spaces with the React frontend served as static files and FastAPI handling WebSocket connections. The GPU inference endpoint URL shall be configurable via a single Space secret (`VLLM_BASE_URL`) without requiring a Space rebuild.

FR19: **README YAML Frontmatter** — The Space README.md shall include YAML frontmatter with `sdk: docker`, `tags: [amd, amd-hackathon-2026, vllm, gradio]`, and clear setup instructions for Space secrets.

FR20: **Self-Guided Demo Mode** — The Space shall include a self-guided experience for community visitors who arrive outside the live demo window. This includes a sample match video, pre-generated commentary notes, and a "Try It" button that triggers the full demo flow with pre-seeded settings.

### Non-Functional Requirements

NFR1: **Audio Q&A Response Time** — The system shall respond to audio questions in under 3.5 seconds end-to-end (speech end → STT → LLM → first text token), measured at P95 under single-user load.

NFR2: **Language Switch Latency** — The system shall complete a language switch in under 3 seconds with less than 500ms of audio silence, measured from toggle click to first word in the new language.

NFR3: **Cold Start Time** — The HF Space shall load and begin playing video within 20 seconds of page open, with vision model attaching to the stream within an additional 30 seconds (background warm-up).

NFR4: **Commentary TTFT** — Time-to-first-token for commentary generation following a match event detection (confidence > 0.6) shall be under 500ms.

NFR5: **Vision Frame Processing** — The system shall process video frames at a minimum of 5 FPS on MI300X for Qwen2.5-VL-7B-AWQ under StreamingVLM, sufficient for real-time match event detection.

NFR6: **HF Space Container Memory** — The HF Space Docker container shall consume under 12GB RAM before model loading (frontend serving + FastAPI + WebSocket connections only). GPU models shall run exclusively on the AMD droplet, not in the Space container.

NFR7: **MI300X VRAM Budget** — Total GPU memory consumption on MI300X shall not exceed 60GB: Qwen2.5-VL-7B-AWQ (~7-9GB) + KV cache buffer (~20-30GB) + agent LLM context (~5-10GB) + TTS (if used, ~2GB) + framework overhead (~10GB). Remaining 132GB+ headroom available for KV cache expansion.

NFR8: **KV Cache Temporal Retention** — The system shall retain a minimum of 120 seconds of visual context in the KV cache, supporting temporal navigation for split-screen Q&A.

NFR9: **Fallback Chain Activation** — When the primary streaming path (SGLang + StreamingVLM) fails to initialize, the system shall activate the next fallback level within 30 seconds. Each fallback level shall document which capabilities are degraded: Level 2 (custom KV window — retains temporal continuity), Level 3 (pre-computed embeddings + vLLM — loses temporal scrub), Level 4 (frame-by-frame — no temporal continuity).

NFR10: **Configuration Agility** — The GPU inference endpoint URL shall be changeable via a single environment variable (`VLLM_BASE_URL`) without requiring a Space rebuild or code change. The system shall reconnect to the new endpoint within 10 seconds of variable change and Space restart.

NFR11: **Player Identification Accuracy** — Player identification shall exceed 90% accuracy on known players in the demo video under normal camera angles and lighting conditions. Misidentifications shall be indicated with uncertainty qualifiers in commentary output.

NFR12: **Single Command Deployment** — The Space shall be deployable with a single `git push` to the HF Space repository. No manual SSH, no droplet-side configuration beyond the initial vLLM/SGLang endpoint startup.

### Additional Requirements (from Architecture)

- **Existing Codebase Foundation (Not Greenfield):** The existing React/Vite + FastAPI codebase provides the application scaffold. New code extends this foundation rather than replacing it. All new components must integrate with the existing `useWebSocket` patterns, `BaseAgent` class, `ConnectionManager`, and WebSocket protocol at `/ws/live`.

- **New Backend Files Required:** `models/narrative_beat.py` (NarrativeBeat dataclass — pure data), `models/notes_store.py` (StructuredNotes + lookup + tag resolver), `streaming/sglang_client.py` (SGLang + StreamingVLM HTTP client), `streaming/frame_sampler.py` (frame selection + FPS control + diversity scoring), `streaming/kv_cache.py` (KV cache window management + retention config), `streaming/factory.py` (streaming backend selection), `scripts/generate_notes.py` (CLI for pre-match notes), `scripts/deploy_hf.sh` (single-command deploy).

- **New WebSocket Message Types:** `notes_ready` (pre-match notes generation complete, with beat_count + sections metadata), `state_snapshot` (full state on reconnect — game_state + last 3 commentary lines). All messages follow format `{"type": "...", ...data, "timestamp": "ISO8601"}`.

- **WebSocket Reconnection:** State snapshot approach — on reconnect, server sends full `game_state` + last 3 commentary lines. Exponential backoff with jitter. No event replay infrastructure needed for hackathon scope.

- **Structured Notes Store Architecture:** `NoteOrganizer` return type changes from `str` to `NotesStore`. `NotesStore` contains: `raw_markdown` (for backwards compat), `beats: List[NarrativeBeat]`, `lookup: Dict[str, List[int]]` (event_tag → beat_indices, O(1)), `index: Optional[numpy array]` (cosine similarity fallback). `NarrativeBeat` schema: `text`, `event_tags`, `players`, `section`, `source`, `confidence`.

- **Event Tags Taxonomy (8 Canonical Tags):** `goal`, `yellow_card`, `red_card`, `substitution`, `foul`, `corner`, `free_kick_dangerous`, `offside`. `tag_resolver.py` with 3-tier resolution: exact match → synonym/parent → substring → None (semantic fallback). Safety gate: before "goal" tag fires, verify `game_state` score has changed.

- **Confidence-Gated Progression Pattern:** Applied uniformly across 5 components (STT, vision event detection, player identification, overlay rendering, teleprompter highlighting). Three tiers: > 0.9 proceed (skip confirmation), ≥ 0.7 confirm (1.5s max verification), < 0.7 reject (auto-reject, prompt retry).

- **GPU Workload Scheduling (Single MI300X):** Three priority levels sharing one GPU — Priority 1 (Highest): Q&A Decode (fan question, < 3.5s E2E), Priority 2: Streaming Prefill (continuous video frames, 5 FPS min), Priority 3 (Background): Commentary Generation (60s timer + event triggers, < 500ms TTFT). SGLang's disaggregated prefill/decode handles priority 1 vs 2 naturally.

- **4-Level Fallback Chain:** Level 1: SGLang + StreamingVLM 7B (full capability). Level 2: SGLang + Custom KV Sliding Window (loses StreamingVLM optimizations, retains temporal continuity). Level 3: Pre-computed Vision Embeddings + vLLM (loses temporal scrub, Q&A degrades to static context). Level 4: vLLM Frame-by-Frame (no temporal continuity). Architecture supports all levels without code change.

- **Docker Multi-Stage Build:** Stage 1: Frontend build (node, npm build → static dist/). Stage 2: Backend (python:3.11-slim, FastAPI + uvicorn, copies dist/, agents/, config/, data_sources/, models/, api/). HEALTHCHECK at /health. Single container → HF Space (Docker SDK).

- **HF Space Configuration:** `sdk: docker`, `tags: [amd, amd-hackathon-2026, vllm, gradio]`, README YAML frontmatter with setup instructions, Space secret `VLLM_BASE_URL` for GPU endpoint.

- **Integration Order (from Architecture):** 1. Add `NarrativeBeat` + `NotesStore` in `models/`. 2. Modify `NoteOrganizer` to return `NotesStore` (backwards compatible via `raw_markdown`). 3. Wire lookup table into `LiveAgent.generate_live_commentary()`. 4. Add numpy cosine similarity fallback if Day 5 has slack.

- **Implementation Phase Order:** Day 1-2: environment + inference (models/, streaming/, SGLang setup). Day 3-4: integration (frontend components + backend wiring). Day 5: polish (animations, accessibility, testing). Day 6: submit (HF Space deploy, README, self-guided mode).

- **CPU Embedder for Semantic Fallback (Stretch):** `all-MiniLM-L6-v2` (~80MB) for numpy cosine similarity over ~100 beats. Separate CPU process to avoid GPU contention. `< 1ms` search time. Only if Day 5 has slack.

### UX Design Requirements

UX-DR1: **Design Token Implementation** — Implement Tailwind CSS dark theme with full token set: Background Slate 950 (#020617), Surface Slate 900 (#0F172A), Narrative Accent Amber 400 (#FBBF24), Interactive Accent Cyan 400 (#22D3EE), Success Emerald 500 (#10B981), Warning Amber 500 (#F59E0B), Danger Red 500 (#EF4444), Text Primary Slate 100 (#F1F5F9), Text Secondary Slate 400 (#94A3B8), Overlay Stroke White 90% opacity with 1px blur dark dropshadow.

UX-DR2: **Color System Accessibility** — All 7 semantic color tokens must meet WCAG 2.1 AA minimum. Primary text must meet AAA (7:1+). Confidence never communicated by color alone — always paired with numeric badge. State indicators must include icon + color + text. Interactive elements must have visible Cyan 400 focus rings (2px, offset).

UX-DR3: **Typography System** — Two-typeface system: Inter (UI, system stack fallback) + JetBrains Mono (data/stats). 7-level type scale (xs 12px through 3xl 30px) with 4-level weight hierarchy (Regular 400, Medium 500, Semibold 600, Bold 700). Mono reserved for source attribution, confidence badges, agent progress, timestamps.

UX-DR4: **Spacing System** — 4px base unit (Tailwind default). 8-token spacing scale: space-1 (4px) through space-12 (48px). All spacing values must be multiples of 4px. No responsive breakpoints for hackathon — fixed viewport 1440px reference, minimum 1280px.

UX-DR5: **VideoCanvas Component** — Video element with canvas overlay for real-time AI annotations. 5 FPS draw loop with dimension guard (skip frame if dimensions mismatch). Integrated WebSocket connection status dot (6×6px, emerald/amber/red). Four states: Loading, Playing, Model Warming, Reconnecting. Canvas API: drawCircle, drawArrow, drawLine, drawLabel, clear. Mirror overlay data to hidden `aria-live` region.

UX-DR6: **MicButton Component** — Floating hold-to-record button (48×48px, Slate 900 at 85% opacity, backdrop-blur, bottom-right corner). Seven states: Idle, Hover (Cyan ring), Recording (Red ring, max 15s, progress arc, ghost text), Processing (Amber rotating gradient), Disabled-ModelWarming, Disabled-NoMic, Hidden (during active Q&A). Defensive: 15s max recording auto-submit/cancel, ignore clicks (only respond to hold ≥ 300ms), STT timeout failsafe. Tooltip on first hover: "Hold to ask a question" (localStorage gated).

UX-DR7: **MatchInsight Component** — Merged TriviaCard + QuestionChips. Trivia card: Slate 900 at 92% opacity, 3px Amber 400 left border, title + 1-2 line body, max 280px, anchored bottom-left. Suggested question chips: row of 3 pills, 8px gap, centered below video. Priority queue (max depth 3): Goal bypasses queue, Red card bypasses queue, Substitution queued priority, General trivia queued (oldest dropped when full). Five states: Hidden, Fading In (400ms ease-out), Visible (5s display), Dismissed by Priority (200ms accelerated fade), Fading Out (400ms ease-in). Minimum 8s gap between consecutive non-priority cards. Cards: `role="status" aria-live="polite"`. Chips: `role="button"`.

UX-DR8: **Teleprompter Component** — Scrolling commentary notes panel (40% width, Slate 900, scrollable). Static mode is default (always works). Auto-highlight is enhancement (requires vision events). Seven states: Empty, Generating (progress bar + agent status), Ready (pre-match, manual scroll), Live Syncing (auto-highlight, amber 400 bg at 15%, 3px left border, ▶ marker, next 3 lines visible), Hold Mode (manual scroll paused, contextual "Back to live"/"Catch up" button), Degraded (static mode indicator), Error (retry). Smooth scroll 300ms on beat change. Current beat at ~30% from top. Metadata per line: source badge + confidence (JetBrains Mono, text-xs). `role="complementary" aria-label="Commentary teleprompter"`.

UX-DR9: **SplitScreen Component** — Animated 60/40 split layout for Q&A temporal navigation. Left: live match continues (60%). Right: frozen frame with SVG overlay (40%). Five states: Hidden, Sliding In (300ms ease-out), Active, Sliding Out (300ms ease-in), Content Not Ready (500ms timeout → loading skeleton). Divider: 2px Slate 800, non-draggable. SVG overlay rendering with stroke-dasharray draw-on animation (200ms per element) and dropshadow filter for pitch visibility. Canvas reserved exclusively for live FPS overlays on left panel. Escape dismisses. Auto-resolves after 5-8s. Reduced motion: instant snap. `role="region" aria-label="Question answer: showing the relevant match moment"`.

UX-DR10: **ControlsTray Component** — Five controls in a bottom bar: Language toggle (EN | ES), Bias slider (red-neutral-blue gradient), Excitement slider (amber gradient), Knowledge Depth slider (cyan gradient), View toggle (Fan Lens / Commentator Dashboard). Always visible during narrated demo. Auto-hidden after 3s idle in Community Visitor mode. Sliders apply immediately — no "apply" button. Tooltip on first hover for every control. Keyboard navigation: Tab order mirrors visual order, arrow keys adjust sliders ±10%.

UX-DR11: **Fan Lens Layout** — Full video (100% width, 16:9, centered). Trivia cards anchored bottom-left (8px from edge, max 280px wide). Mic button anchored bottom-right (16px from edge, 48×48px). Controls tray at bottom. Suggested question chips in row below video (8px gap, centered, appear on match event, fade after 8s). Cards must avoid active play zone (ball position tracked by vision model). All overlays ephemeral — match is always the priority.

UX-DR12: **Commentator Dashboard Layout** — Video 60% width (left-aligned, 16:9). Teleprompter 40% width (right panel, Slate 900). Current beat highlighted in amber (Amber 400 at 15% bg, 3px left border, ▶ marker, text-lg Medium). Next 3 lines visible below (text-sm, slate-400, fading opacity). Previous line above (text-xs, slate-600). Source + confidence badges per line (JetBrains Mono, text-xs). "Generate Notes" button (dashed border). View toggle in controls tray. Keyboard shortcut for quick-toggle between views (demo narration).

UX-DR13: **Landing Page** — Centered hero on Slate 950. "PitchAI" title in Inter Bold, amber. "Your AI Broadcast Companion" tagline. Amber pill CTA: "Start Watching." Three feature pills: "Live Commentary Notes", "Contextual Q&A", "Cross-Language Translation." Subtle green pitch line accent at bottom. Skipped during narrated demo video (Space URL opens directly to stream). Serves Community Visitor mode as entry point.

UX-DR14: **First-Visit Overlay** — Shown once for 4 seconds when arriving directly at video (deep link scenario). Text identifies product: "PitchAI — Your AI Broadcast Companion. Trivia cards explain the action. Hold the mic to ask questions." Fades out automatically, doesn't require dismissal. Skipped on return visits via localStorage.

UX-DR15: **Q&A Voice Path Interaction** — Full flow: hold mic → speak (progress ring fills, ghost text at 50% opacity) → release → STT confidence check (> 90% skip confirmation, 70-90% show text 1s with dismiss X, < 70% auto-reject with retry) → processing (ring animation, video vignette 5%) → voice answer starts at ~2s → screen splits (300ms ease-out) → SVG overlays draw sequentially (200ms each, precise if high confidence, zone highlight if medium) → resolve (300ms ease-in) → mic button pulses once. After 3x STT failure: offer suggested chips as alternative.

UX-DR16: **Q&A Tap Path Interaction** — Vision detects match event → suggested question chips appear (fade in 300ms) → user taps chip (selected chip highlights amber, others fade) → pre-computed answer begins within 1s → split-screen with pre-mapped overlay coordinates → voice + visual deliver answer → resolve. Pre-computed Q&A pairs generated alongside commentary notes during pre-match pipeline.

UX-DR17: **Language Toggle Interaction** — Click toggles between EN and ES. Pre-loaded language prompts enable routing change (not model load). Commentary mutes briefly (crossfade transition, < 3s total, < 500ms silence). Trivia cards also translate. Toggle prominently labeled "EN | ES." Defers during high-intensity moments (never interrupt a goal celebration). `aria-label` updates dynamically: "Switch commentary to Spanish" / "Switch commentary to English."

UX-DR18: **Commentary Settings Sliders** — Three sliders in ControlsTray or Settings panel: Bias (Team A fan [-1] to Neutral [0] to Team B fan [+1]), Excitement (Subdued [0] to Maximum [1]), Knowledge Depth (Beginner [0] to Tactical Deep-Dive [1]). Each slider has a gradient track. Preview text updates with settings changes. Changes sent via WebSocket `{"type": "settings_update"}` and applied immediately to next commentary cycle. No queueing, no "apply" button.

UX-DR19: **Connection State Indicator** — Integrated status dot in VideoCanvas (6×6px, top-right corner, 12px inset). Emerald 500 at 60% opacity (connected), Amber 500 pulse (reconnecting with exponential backoff), Red 500 (disconnected). After 5s disconnected: "Reconnecting..." text beside dot. Subtle — not a banner, not an alarm. `aria-label` updates with state.

UX-DR20: **Accessibility Implementation** — Full keyboard navigation: Tab order (Mic → Language → Bias → Excitement → Knowledge → View toggle), Space/Enter activates, Arrow keys adjust sliders, Escape dismisses Q&A/panels. Screen reader ARIA labels on all interactive elements. Motion sensitivity: `prefers-reduced-motion` respected at both CSS (transitions 0ms) and JS level (canvas animations, split-screen slide render instantly, card fades become cuts). All shadcn/ui components include Radix primitive ARIA support.

UX-DR21: **Confidence-Gated UI** — Consistent 3-tier confidence visualization: High (> 90%) — precise, skip confirmations; Medium (70-90%) — brief verification, wider zone; Low (< 70%) — auto-reject or indicate uncertainty. Applied uniformly to STT confirmation, player identification display, overlay precision (circle vs zone), teleprompter highlighting (don't highlight below threshold). Source attribution on every stat (StatsBomb/Firecrawl/FBref badge). Honesty builds trust.

UX-DR22: **Graceful Degradation UX** — Calm indicators for all degraded states: "Based on available footage" (KV cache miss), "Notes available — manual scroll" (vision events unavailable), "Commentary is limited right now — enjoy the match" (compound failure). Degraded modes are product states, not error states. Never "something went wrong" without a next action.

UX-DR23: **shadcn/ui Component Integration** — 8 shadcn/ui components themed to PitchAI dark tokens: Button (mic base, language toggle, view toggle, CTA), Slider (bias/excitement/knowledge), Card (trivia container, teleprompter panel, settings panel), Badge (confidence, source, LIVE, agent status), Dialog (notes generation progress modal), Toggle (Fan/Commentator view switch), Tooltip (control hover labels, feature explanations), Progress (agent pipeline completion bar). Components copied into project (not npm dependency), themed via Tailwind config.

UX-DR24: **Design Token Enforcement** — Amber 400 reserved exclusively for narrative moments (teleprompter current beat, recording state). Cyan 400 reserved exclusively for interactive states (focus rings, hover, selected chips, slider thumbs). Never use amber for interactive elements or cyan for narrative elements. Two-accent system prevents meaning dilution.

UX-DR25: **Component Implementation Phases** — Phase 1 Core (Day 1-2): VideoCanvas, MicButton, useWebSocket hook. Phase 2 Fan Experience (Day 3-4): MatchInsight, SplitScreen. Phase 3 Commentator (Day 4-5, parallel with Phase 2): Teleprompter (static mode first, auto-highlight second). Phase 4 Polish (Day 5-6): animation tuning, accessibility audit, cross-browser testing, chaos testing.

UX-DR26: **Teleprompter Interaction Details** — Auto-scroll keeps current beat at ~30% from top. Smooth scroll 300ms when beat changes. Manual scroll within 500ms of auto-scroll → cancel animation, enter hold mode. Contextual return button: "Back to live" (scrolled up, reviewing past), "Catch up" (scrolled past beat, browsed ahead). Teleprompter and MatchInsight are independent renderers of same structured notes data — no shared component state.

UX-DR27: **Overlay Rendering Strategy** — SVG for frozen frame annotations in SplitScreen (sharper rendering, stroke-dasharray draw-on animation, better text labels, dropshadow filter). Canvas for live FPS overlays in VideoCanvas (real-time player tracking dots, movement trails, continuous redraw at 5 FPS). Never use canvas for text-heavy overlays or SVG for FPS-sensitive continuous rendering.

UX-DR28: **Community Visitor Self-Guidance** — Controls tray always visible (unlike narrated demo). Tooltip on first hover for every control. Suggested question chips appear on FIRST trivia card (accelerated vs demo pacing). Language toggle prominently labeled. README below video fold: scannable in < 5s. First impression target: within 10s sees football + trivia card, within 30s tries a feature. Suggested questions pre-seeded for sample video.

### FR Coverage Map

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR1 | Epic 1 | Multi-agent pipeline (7 agents, 3 phases) |
| FR2 | Epic 1 | Progress callbacks over WebSocket |
| FR3 | Epic 1 + 3 | Dual-view rendering (trivia in E1, teleprompter in E3) |
| FR4 | Epic 3 | Vision-triggered note highlighting (teleprompter) |
| FR5 | Epic 1 | Pre-match notes generation from fixture input |
| FR6 | Epic 2 | Player identification (visual cues + lineup context) |
| FR7 | Epic 2 | Audio input via browser Web Speech API |
| FR8 | Epic 2 | STT confirmation display (1.5s with dismiss) |
| FR9 | Epic 2 | Split-screen temporal navigation |
| FR10 | Epic 2 | KV cache retention (≥ 120s for temporal context) |
| FR11 | Epic 2 | Graceful fallback for Q&A (degraded modes) |
| FR12 | Epic 1 | Trivia card auto-surfacing (confidence > 0.6) |
| FR13 | Epic 2 | Same-commentator voice for Q&A responses |
| FR14 | Epic 3 | Language toggle (< 3s switch, crossfade) |
| FR15 | Epic 3 | Meaning-preserving translation (poetic register) |
| FR16 | Epic 3 | Trivia card translation |
| FR17 | Epic 3 | Commentary settings (3 sliders, real-time) |
| FR18 | Epic 4 | HF Space Docker deployment |
| FR19 | Epic 4 | README YAML frontmatter + tags |
| FR20 | Epic 4 | Self-guided demo mode (sample video + pre-seeded) |

**NFR Coverage:** All 12 NFRs validated in Epic 4.

## Epic List

### Epic 1: Core Streaming & Notes Intelligence

The system can watch football in real-time, understand what's happening, generate Peter Drury-style commentary notes, and surface trivia cards — providing passive value before the user does anything.

**FRs covered:** FR1, FR2, FR3 (Fan Lens side), FR5, FR12
**UX-DRs covered:** UX-DR5 (VideoCanvas), UX-DR7 (MatchInsight), UX-DR11 (Fan Lens layout), UX-DR23 (shadcn/ui integration), UX-DR25 (Phase 1 + 2)

### Epic 2: Fan Q&A — Ask & Understand

Fans can ask questions by voice or by tapping suggested chips, and the system answers with split-screen temporal navigation showing AI-drawn overlays on the exact match moment.

**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR11, FR13
**UX-DRs covered:** UX-DR6 (MicButton), UX-DR9 (SplitScreen), UX-DR15 (Q&A voice path), UX-DR16 (Q&A tap path), UX-DR19 (Connection indicator), UX-DR27 (Overlay rendering strategy)

### Epic 3: Commentator Dashboard & Personalization

Commentators can generate pre-match notes with live progress, use a teleprompter that auto-syncs to match events, and all users can customize commentary language, bias, excitement, and knowledge depth.

**FRs covered:** FR3 (Commentator Dashboard side), FR4, FR14, FR15, FR16, FR17
**UX-DRs covered:** UX-DR8 (Teleprompter), UX-DR10 (ControlsTray), UX-DR12 (Commentator Dashboard layout), UX-DR17 (Language toggle), UX-DR18 (Settings sliders), UX-DR24 (Design token enforcement), UX-DR26 (Teleprompter interaction)

### Epic 4: Deployment, Polish & Community Readiness

The Space is live on Hugging Face, deployable with a single `git push`, includes self-guided demo mode for community visitors, and meets all latency, accessibility, and memory requirements.

**FRs covered:** FR18, FR19, FR20
**NFRs covered:** NFR1 through NFR12
**UX-DRs covered:** UX-DR1-4 (Design tokens), UX-DR13 (Landing page), UX-DR14 (First-visit overlay), UX-DR20 (Accessibility), UX-DR21 (Confidence-gated UI), UX-DR22 (Graceful degradation), UX-DR25 (Phase 4 polish), UX-DR28 (Community self-guidance)

## Epic 1: Core Streaming & Notes Intelligence

The system can watch football in real-time, understand what's happening, generate Peter Drury-style commentary notes, and surface trivia cards — providing passive value before the user does anything.

**FRs covered:** FR1, FR2, FR3 (Fan Lens side), FR5, FR12

### Story 1.1: Narrative Data Models & Tag System

As a system architect,
I want structured data models for narrative beats with an 8-tag event taxonomy and O(1) lookup,
So that pre-match commentary notes can be efficiently retrieved by event type during live match play.

**Acceptance Criteria:**

**Given** the models package exists
**When** `NarrativeBeat` dataclass is defined in `models/narrative_beat.py`
**Then** it has fields: `text` (str), `event_tags` (List[str]), `players` (List[str]), `section` (str), `source` (str), `confidence` (float, 0.0-1.0)
**And** all fields have type hints and default values where appropriate.

**Given** `NotesStore` is defined in `models/notes_store.py`
**When** initialized with a list of NarrativeBeats and raw_markdown string
**Then** it builds a `lookup` dict mapping event_tag → List[beat_indices]
**And** `raw_markdown` is accessible as an attribute for backwards compatibility
**And** `beats` exposes the full list of NarrativeBeats.

**Given** the 8 canonical event tags (goal, yellow_card, red_card, substitution, foul, corner, free_kick_dangerous, offside)
**When** `tag_resolver.resolve(vision_label)` is called
**Then** it returns the canonical tag via exact match → synonym map → substring match → None (3-tier resolution)
**And** synonym map covers vision-specific labels (e.g., "Goal scored" → "goal", "Booking" → "yellow_card").

**Given** a "goal" tag is resolved
**When** the tag fires
**Then** a safety gate verifies `game_state` score has changed before the tag is accepted.

### Story 1.2: Streaming Vision Pipeline

As a system operator,
I want a streaming vision pipeline that processes video frames at 5 FPS through the vision model and detects match events with confidence scores,
So that the system can react to live match action in real-time.

**Acceptance Criteria:**

**Given** the `streaming/` package is created
**When** `streaming/factory.py` is called with backend="sglang"
**Then** it returns an SGLang client instance conforming to the streaming interface
**And** factory supports backend selection by config/env var
**And** factory follows the same pattern as `data_sources/factory.py`.

**Given** `streaming/sglang_client.py` connects to the GPU endpoint at `VLLM_BASE_URL`
**When** video frames are sent via HTTP to the SGLang endpoint
**Then** the client receives vision analysis results including detected events with confidence scores
**And** connection failures trigger the next fallback level within 30 seconds (NFR-9)
**And** fallback level is exposed via a `level` attribute (1-4).

**Given** `streaming/frame_sampler.py` receives a video stream
**When** frames arrive at native rate (25-30 FPS)
**Then** the sampler selects frames at 5 FPS minimum (NFR-5)
**And** uses diversity scoring to avoid redundant consecutive frames
**And** throttles via `lastFrameTime` delta check (>200ms between draws).

**Given** `streaming/kv_cache.py` manages the KV cache window
**When** frames accumulate in the cache
**Then** a minimum of 120 seconds of visual context is retained (NFR-8)
**And** cache eviction policy drops oldest frames first when capacity is reached
**And** cache size is configurable via environment variable.

### Story 1.3: Notes Pipeline with Structured Output

As a commentator preparing for a match,
I want to enter a fixture and run the 7-agent pipeline that generates structured notes with live progress visible,
So that I have 5 pages of research-quality Peter Drury-style material organized by event type before the match begins.

**Acceptance Criteria:**

**Given** a fixture is submitted (home_team, away_team, venue, sport)
**When** the 7-agent pipeline executes in 3 phases (Phase 1: PlayerResearch, TeamForm, Historical, Weather, News in parallel; Phase 2: Matchup; Phase 3: NoteOrganizer)
**Then** each agent fetches data via the 3-layer stats chain (StatsBomb → Firecrawl → FBref)
**And** if an agent fails, remaining agents continue and the failed source is indicated in output.

**Given** an agent completes or fails
**When** status changes
**Then** a progress callback is broadcast over WebSocket: `{"type": "progress", "agent": "PlayerResearch", "status": "running|complete|failed", "items": "22/25"}`
**And** all 7 agents report their final status before pipeline completion.

**Given** the NoteOrganizer agent receives all agent outputs
**When** it synthesizes the final notes
**Then** it returns a `NotesStore` instance (not raw string)
**And** `notes_store.raw_markdown` contains the full 5-page Markdown document
**And** `notes_store.beats` contains at least 50 NarrativeBeats tagged with event types
**And** `notes_store.lookup` provides O(1) tag→beat_indices mapping
**And** existing code that accessed the old string output continues to work via `.raw_markdown`.

**Given** notes generation completes
**When** the pipeline finishes
**Then** a `notes_ready` WebSocket message is broadcast: `{"type": "notes_ready", "beat_count": N, "sections": ["match_info", "home_team", "away_team", "tactical", "historical"], "timestamp": "ISO8601"}`
**And** the NotesStore persists in-memory for the duration of the WebSocket session (FR-5).

### Story 1.4: Vision-Triggered Commentary & Trivia Broadcast

As a system,
I want to match vision detections to pre-computed notes and broadcast commentary with game state over WebSocket,
So that fans receive the right narrative at the right match moment without doing anything.

**Acceptance Criteria:**

**Given** a vision event is detected with confidence > 0.6 (from Story 1.2)
**When** the event tag is resolved through `tag_resolver` (from Story 1.1)
**Then** `NotesStore.lookup(event_tag)` returns matching narrative beats in O(1)
**And** the top beat (highest confidence) is injected into the LiveAgent commentary prompt.

**Given** a commentary seed is built
**When** it's sent to the LLM
**Then** `game_state.to_context_string()` is ALWAYS prepended to the seed
**And** commentary is generated within 500ms TTFT (NFR-4)
**And** the response includes the `source` field from the matched NarrativeBeat.

**Given** commentary is generated
**When** broadcast over WebSocket
**Then** the message includes: `{"type": "commentary", "text": "...", "gameState": {...}, "source": "StatsBomb|Firecrawl|FBref", "timestamp": "ISO8601"}`
**And** a trivia-formatted version (2-line max, keyed to event type) is included for the Fan Lens
**And** both full commentary and trivia are sent in the same broadcast for dual-view rendering (FR-3 Fan Lens side).

**Given** no vision event is detected for 60 seconds
**When** the periodic timer fires
**Then** a general commentary line is generated using current game_state context (existing `_periodic_commentary` pattern)
**And** no trivia card is generated (periodic ≠ event-triggered).

### Story 1.5: Video Player with Canvas Overlay & Connection State

As a fan opening PitchAI,
I want the match video to play immediately with AI connection status visible,
So that I'm immersed in the match instantly without waiting for models to load.

**Acceptance Criteria:**

**Given** the user opens the PitchAI Space URL
**When** the page loads
**Then** the video element begins playing within 20 seconds (NFR-3)
**And** the video is 100% width, 16:9 aspect ratio, centered in the viewport (UX-DR11)
**And** there is no loading spinner, no "loading model..." message — video plays immediately.

**Given** the `useWebSocket` hook connects to `/ws/live`
**When** connection state changes
**Then** the hook exposes typed props for all components: `{ connectionState, gameState, commentary, triviaCard, notesReady, answer, error }`
**And** on reconnect, requests and receives a `state_snapshot` (game_state + last 3 commentary lines)
**And** reconnection uses exponential backoff with jitter.

**Given** the `VideoCanvas` component renders
**When** video is playing
**Then** a canvas overlay is synced to the video element dimensions
**And** the draw loop runs at 5 FPS (throttled via 200ms delta check)
**And** if canvas dimensions don't match video dimensions, the frame is skipped and dimensions are re-synced first (dimension guard)
**And** the canvas exposes API: `drawCircle`, `drawArrow`, `drawLine`, `drawLabel`, `clear`.

**Given** the WebSocket status dot is integrated in VideoCanvas
**When** connection state changes
**Then** Emerald 500 at 60% opacity = connected, Amber 500 pulse = reconnecting, Red 500 = disconnected (UX-DR19)
**And** dot is 6×6px, top-right corner, 12px inset
**And** after 5s disconnected: "Reconnecting..." text appears beside the dot
**And** `aria-label` updates with the current state.

**Given** the vision model is still warming up (background)
**When** the user is watching video
**Then** the status dot pulses amber
**And** the canvas is visible but empty
**And** video continues playing uninterrupted — models attach to the stream, they don't hold it hostage.

### Story 1.6: Trivia Cards & Match Insights Display

As a new fan watching football,
I want trivia cards to fade in at key match moments with source attribution and suggested question chips,
So that I learn about the match passively without looking away from the action.

**Acceptance Criteria:**

**Given** a trivia-formatted commentary is received over WebSocket (from Story 1.4)
**When** the MatchInsight component receives the data
**Then** a card renders anchored bottom-left (8px from edge, max 280px wide)
**And** the card uses Slate 900 at 92% opacity with a 3px Amber 400 left border (UX-DR7)
**And** the card has a title ("Did you know?") + 1-2 line body (text-sm)
**And** source attribution badge is shown: `StatsBomb · 2023/24 season` in JetBrains Mono text-xs.

**Given** a trivia card is ready to display
**When** it enters the viewport
**Then** it fades in over 400ms ease-out (opacity 0→1, translateY 8px→0)
**And** displays for 5 seconds
**And** fades out over 400ms ease-in
**And** if `prefers-reduced-motion`, appears/disappears instantly with no animation.

**Given** the priority queue for trivia cards (max depth 3)
**When** a new card arrives
**Then** Goal and Red card events bypass the queue and immediately dismiss any active card (200ms accelerated fade)
**And** Substitution events are queued with priority over general trivia
**And** when the queue is full, the oldest non-priority card is dropped
**And** minimum 8 seconds gap between consecutive non-priority cards.

**Given** a trivia card is displayed
**When** the card is active
**Then** suggested question chips appear in a row below the video (3 pills, 8px gap, centered)
**And** chips fade in over 300ms and fade out after 8 seconds if not interacted with
**And** each chip has `role="button"` with question text as `aria-label`
**And** the card has `role="status" aria-live="polite"` for screen reader announcement without interruption.

**Given** the card position
**When** rendering
**Then** the card avoids the active play zone (ball position tracked by vision model, bottom-left default)
**And** the card never exceeds 5% of the screen area (UX-DR11)
**And** a dismiss X button appears on hover.


## Epic 2: Fan Q&A — Ask & Understand

Fans can ask questions by voice or by tapping suggested chips, and the system answers with split-screen temporal navigation showing AI-drawn overlays on the exact match moment.

**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR11, FR13

### Story 2.1: Voice Input — MicButton & STT

As a fan watching football,
I want to hold a floating microphone button, speak my question, and see it recognized before submission,
So that I can ask questions naturally without typing or navigating menus.

**Acceptance Criteria:**

**Given** the MicButton component is rendered on the video page
**When** in idle state
**Then** it displays as a 48×48px circle, Slate 900 at 85% opacity, backdrop-blur, anchored bottom-right (16px from edge)
**And** has an SVG microphone icon (18×18px, slate-400)
**And** has a 2px border ring (Slate 800 idle)
**And** `aria-label="Hold to ask a question"`.

**Given** the user hovers over the MicButton
**When** cursor enters the button area
**Then** the border ring turns Cyan 400 with a glow effect
**And** the mic icon turns white
**And** a tooltip appears: "Hold to ask a question" (first hover only, localStorage gated)
**And** on subsequent hovers, no tooltip is shown.

**Given** the user holds the MicButton (≥ 300ms hold, clicks ignored)
**When** recording begins
**Then** the border ring turns Red 500 and pulses (48→52px)
**And** a Snapchat-style progress arc fills as the user speaks
**And** Browser Web Speech API streams interim results as ghost text below the button (50% opacity, updating in real-time)
**And** `aria-label` updates to "Recording..."
**And** recording auto-stops at 15 seconds maximum.

**Given** recording exceeds 15 seconds
**When** the timeout fires
**Then** if interim results are non-empty, the recording auto-submits
**And** if interim results are empty, the recording auto-cancels and returns to idle
**And** this serves as the failsafe for STT `onend` never firing (Chrome bug).

**Given** the user releases the MicButton
**When** STT returns the recognized text
**Then** if confidence > 90%: skip confirmation, start processing immediately, ghost text fades
**And** if confidence 70-90%: show recognized text at full opacity for 1.5s with dismiss X button; processing begins at 1s mark
**And** if confidence < 70%: auto-reject, mic returns to idle, ghost text shows "I didn't quite catch that — try again?"
**And** if STT fails < 70% 3 times consecutively: offer suggested question chips as alternative: "Try tapping one of these instead?"

**Given** processing begins
**When** the question is submitted to the backend
**Then** the MicButton ring animates with an Amber 400 rotating gradient
**And** the video edges darken 5% (vignette)
**And** `aria-label` updates to "Processing your question"
**And** the MicButton is hidden (not dimmed) during active Q&A split-screen.

**Given** the vision model is still warming up
**When** the MicButton renders
**Then** it displays at 50% opacity with tooltip: "AI warming up... ready in ~20s"
**And** if no microphone is available: 50% opacity with tooltip "Microphone not available".

**Given** keyboard access
**When** the user holds the Space key
**Then** recording behavior matches mouse/touch hold
**And** Escape cancels recording or dismisses active Q&A.

### Story 2.2: Q&A Backend — Answer Generation

As a fan asking a question about the match,
I want the AI to answer in the same commentator voice and style as the live commentary,
So that the response feels like a knowledgeable companion talking to me, not a search result.

**Acceptance Criteria:**

**Given** a `query` WebSocket message is received: `{"type": "query", "text": "Why is that a red card?", "timestamp": "ISO8601"}`
**When** the server processes the question
**Then** `game_state.to_context_string()` is prepended to the LLM prompt
**And** current commentary settings (bias, excitement, knowledge_depth) are injected into the prompt template
**And** the LLM generates an answer in the same Peter Drury commentator voice/style
**And** the answer is broadcast: `{"type": "answer", "text": "...", "gameState": {...}, "timestamp": "ISO8601"}`.

**Given** Q&A decode is highest GPU priority (Priority 1)
**When** a fan question arrives during streaming prefill
**Then** Q&A decode preempts streaming prefill
**And** the answer first text token arrives within 3.5 seconds of question submission (NFR-1), measured at P95.

**Given** pre-computed Q&A pairs exist from the notes pipeline (Story 1.3)
**When** a question matches a pre-computed pair (e.g., "Why is that a red card?" triggered by a red card event)
**Then** the cached answer is returned within 1 second (tap path latency)
**And** pre-computed overlay coordinates are included in the answer payload.

**Given** the KV cache has sufficient temporal context for the question
**When** answering
**Then** the answer references the specific visual moment (e.g., "See how his studs made contact above the ankle")
**And** the most relevant timestamp is included in the answer payload for split-screen navigation.

**Given** the KV cache does not contain the relevant timestamp (> 120s ago, or fallback level 3-4)
**When** answering
**Then** the system answers with available context and includes `"temporal_context": "limited"` in the answer payload
**And** the answer text includes the calm indicator: "Based on available footage..."
**And** at fallback level 3-4, answers use pre-computed embeddings or general football knowledge (FR-11).

**Given** a non-football question is submitted
**When** the LLM processes it
**Then** the answer gracefully redirects: "I'm focused on the match right now — try asking about what's happening on the pitch!"
**And** the message type is still `answer` (not `error`).

### Story 2.3: Split-Screen Temporal Navigation

As a fan receiving a Q&A answer,
I want the screen to split and show the exact match moment with AI-drawn overlays explaining the answer,
So that I see the explanation drawn on the moment I asked about.

**Acceptance Criteria:**

**Given** an `answer` WebSocket message is received with temporal context
**When** the SplitScreen component activates
**Then** the screen splits with a 300ms ease-out slide animation
**And** the left panel shows the live match at 60% width (continues playing uninterrupted)
**And** the right panel shows the frozen frame at 40% width from the relevant timestamp
**And** a 2px Slate 800 divider separates the panels (non-draggable)
**And** if `prefers-reduced-motion`, the split is instant (no slide).

**Given** the frozen frame is displayed
**When** overlay coordinates are available in the answer payload
**Then** SVG overlays render on the frame with stroke-dasharray draw-on animation (200ms per element)
**And** elements draw in sequence: circle → arrow → line → label
**And** if overlay confidence is high: precise circle around the player/zone
**And** if overlay confidence is medium: wider zone highlight + label simultaneously (no precise circle)
**And** all overlay strokes use White 90% opacity with 1px blur dark dropshadow (50% black) for pitch visibility (UX-DR27).

**Given** SVG is used for frozen frame overlays
**When** rendering annotations
**Then** SVG handles text labels, circles, arrows, and offside lines (stroke-dasharray animation, dropshadow filter)
**And** Canvas is reserved exclusively for live FPS overlays on the left VideoCanvas panel (UX-DR27).

**Given** the SplitScreen is active
**When** the answer completes or 5-8 seconds pass
**Then** the right panel slides out (300ms ease-in)
**And** the left panel expands back to 100% width
**And** the MicButton reappears with a single gentle pulse to indicate readiness
**And** if `prefers-reduced-motion`, the transition is instant.

**Given** the frozen frame hasn't loaded within 500ms of the trigger
**When** the content-ready timeout fires
**Then** the SplitScreen still activates but the right panel shows a loading skeleton
**And** the answer voice begins playing regardless (audio-first, visual-follow).

**Given** the answer payload includes `"temporal_context": "limited"`
**When** the SplitScreen renders
**Then** the frozen frame is omitted and the right panel displays only the textual answer
**And** a calm indicator shows: "Based on available footage"
**And** the split resolves after the answer text is displayed.

**Given** user dismissal
**When** the user clicks the right panel, presses Escape, or taps outside
**Then** the split resolves immediately (200ms ease-in)
**And** the answer text is collapsed but available in a notification-style summary.

**Given** screen reader access
**When** the SplitScreen activates
**Then** `role="region" aria-label="Question answer: showing the relevant match moment"` is set
**And** the transition is announced to the screen reader.

### Story 2.4: Player Identification for Q&A

As a fan asking "who is number 10?" or "who just scored?",
I want the system to identify players from visual cues and lineup context with confidence indicators,
So that I know who's who on the pitch and the AI doesn't confidently misidentify players.

**Acceptance Criteria:**

**Given** a player is visible on screen
**When** the vision model processes the frame through `agents/vision_agent.py`
**Then** player identification uses visual cues in priority order: jersey number → position on pitch → movement pattern → build
**And** these cues are fused with contextual information: lineup data, recent touches, player proximity
**And** the result includes a confidence score (0.0-1.0).

**Given** a player identification result
**When** confidence > 90%
**Then** the player is identified by name in commentary and Q&A answers (e.g., "That's Mbappé making the run")
**And** no confidence qualifier is shown.

**Given** a player identification result
**When** confidence 70-90%
**Then** the player is identified with a qualifier (e.g., "That appears to be number 10 based on the lineup")
**And** the confidence badge shows the numeric score in the answer.

**Given** a player identification result
**When** confidence < 70%
**Then** the system indicates ambiguity rather than misidentifying (e.g., "the player in the central position")
**And** no specific player name is used in the answer
**And** the confidence badge indicates the uncertainty.

**Given** overall player identification accuracy
**When** measured on known players in the demo video under normal camera angles and lighting
**Then** accuracy exceeds 90% (NFR-11)
**And** misidentifications are always indicated with uncertainty qualifiers in output.

**Given** a Q&A answer references a player
**When** the answer is broadcast
**Then** the player identification confidence is included in the payload
**And** the SVG overlay uses precise circles for high-confidence IDs and zone highlights for medium-confidence IDs
**And** source of identification is indicated (e.g., "via jersey number + lineup data").


## Epic 3: Commentator Dashboard & Personalization

Commentators can generate pre-match notes with live progress, use a teleprompter that auto-syncs to match events, and all users can customize commentary language, bias, excitement, and knowledge depth.

**FRs covered:** FR3 (Commentator Dashboard side), FR4, FR14, FR15, FR16, FR17

### Story 3.1: Teleprompter — Static Notes Display

As a commentator preparing for or watching a match,
I want to view my pre-generated commentary notes in a scrollable teleprompter panel with tabbed review and long-sheet live modes,
So that I can review notes by section before the match or scan continuously during live play.

**Acceptance Criteria:**

**Given** the Commentator Dashboard layout is active (60/40 split: video left, teleprompter right)
**When** the Teleprompter component renders
**Then** the teleprompter panel is 40% width, Slate 900 background, scrollable
**And** the panel has `role="complementary" aria-label="Commentary teleprompter"`
**And** video remains at 60% width, left-aligned, 16:9 (UX-DR12).

**Given** no notes have been generated
**When** the teleprompter is in empty state
**Then** it displays: "Generate commentary notes to get started." with a dashed border CTA button
**And** the "Generate Notes" button triggers the 7-agent pipeline (Story 1.3).

**Given** notes generation is in progress
**When** progress callbacks arrive over WebSocket (Story 1.3)
**Then** a progress bar displays with agent-by-agent status
**And** each agent shows: agent name + status badge (running/complete/failed) + items processed
**And** failed agents are marked with the reason and notes continue from remaining agents.

**Given** notes are ready (`notes_ready` WebSocket message received)
**When** pre-match (match not yet playing)
**Then** the teleprompter defaults to **Tabbed Mode**: 5 sections as tabs (match_info, home_team, away_team, tactical, historical)
**And** Carlos can click through sections to review and verify accuracy
**And** each tab renders the raw_markdown for that section.

**Given** the match is playing live
**When** the commentator is using the teleprompter
**Then** the teleprompter switches to **Long-Sheet Mode**: continuous scroll of all notes
**And** a toggle button switches between Tabbed and Long-Sheet modes
**And** each line shows metadata badges: source (StatsBomb/Firecrawl/FBref) + confidence (JetBrains Mono, text-xs).

**Given** notes generation fails
**When** the error state triggers
**Then** the teleprompter shows: "Couldn't generate notes. [Retry]"
**And** the retry button re-initiates the pipeline.

**Given** the teleprompter is in degraded mode (vision events unavailable)
**When** notes are available but auto-highlighting is non-functional
**Then** the teleprompter shows a subtle indicator: "Notes available — manual scroll"
**And** all notes remain readable and scrollable in static mode
**And** static mode is always the fallback — it must never break.

### Story 3.2: Vision-Synced Teleprompter Highlighting

As a commentator calling a live match,
I want the teleprompter to automatically highlight the current narrative beat and show the next 3 lines as the match progresses,
So that I can scan the teleprompter in under a second and deliver the right line at the right moment.

**Acceptance Criteria:**

**Given** the match is live and vision events are being detected (Story 1.4)
**When** a narrative beat matches the current event
**Then** the current beat is highlighted: Amber 400 background at 15% opacity, 3px amber left border, ▶ marker, text-lg Medium (UX-DR8, UX-DR24)
**And** the next 3 lines are visible below: text-sm Regular, slate-400, fading opacity for each subsequent line
**And** the previous line above the current beat: text-xs Regular, slate-600
**And** Amber 400 is used exclusively for this narrative moment — never for interactive elements (UX-DR24).

**Given** auto-scroll is active
**When** the current beat changes
**Then** the teleprompter smoothly scrolls (300ms) to keep the current beat at ~30% from the top of the panel
**And** the scroll is smooth, not instant.

**Given** the commentator manually scrolls the teleprompter
**When** a scroll event occurs within 500ms of an auto-scroll animation
**Then** the auto-scroll animation is cancelled
**And** the teleprompter enters **Hold Mode**: auto-scroll pauses
**And** a return button appears with contextual label:
  - "Back to live" if the user scrolled up (reviewing past notes)
  - "Catch up" if the user scrolled past the current beat (browsed ahead)
**And** tapping the return button resumes auto-scroll to the current beat.

**Given** the current beat's confidence is below the highlighting threshold
**When** the beat has low confidence
**Then** the beat is NOT highlighted in amber (don't highlight if below threshold)
**And** the beat text is still visible in the scroll but at slate-400 (same as next lines)
**And** this prevents confidently wrong highlights.

**Given** a surprise event occurs (VAR, injury) not covered in pre-computed notes
**When** the vision model detects an unrecognized event
**Then** the teleprompter shows best available context without highlighting
**And** the system acknowledges the gap: a subtle indicator shows "Event outside pre-match notes"
**And** the live commentary agent handles the event with general football knowledge (Story 1.4 fallback).

**Given** `prefers-reduced-motion` is set
**When** auto-scroll fires
**Then** the scroll is instant (0ms) rather than smooth 300ms.

### Story 3.3: Commentary Settings — Bias, Excitement & Knowledge Depth

As a fan or commentator,
I want to adjust bias, excitement, and knowledge depth via sliders that transform the commentary in real-time,
So that the commentary matches my preferences — whose side I'm on, how energetic it feels, and how much tactical detail I get.

**Acceptance Criteria:**

**Given** the ControlsTray is rendered (always visible during demo, auto-hidden after 3s idle in Community Visitor mode)
**When** the user views the controls
**Then** three sliders are present with gradient tracks and labels:
  - Bias: Team A fan [-1] through Neutral [0] to Team B fan [+1], red-to-neutral-to-blue gradient
  - Excitement: Subdued [0] to Maximum [1], amber gradient
  - Knowledge Depth: Beginner explanations [0] to Tactical deep-dive [1], cyan gradient (UX-DR18)
**And** each slider has visible min/max labels
**And** sliders have `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, and descriptive `aria-label`.

**Given** the user adjusts any slider
**When** the value changes
**Then** a WebSocket message is sent immediately: `{"type": "settings_update", "bias": 0.3, "excitement": 0.8, "knowledge_depth": 0.5}`
**And** the server updates the prompt template on receive — no "apply" button, no queueing
**And** the next commentary cycle (via `_periodic_commentary` or event trigger) uses the new settings
**And** preview text updates to reflect the new setting (e.g., bias at +1 shows "Strong Team B perspective").

**Given** the bias slider is adjusted
**When** bias changes from neutral
**Then** Team A goal commentary lifts with joy, Team B goal commentary is respectful but subdued (at +1 bias for Team A)
**And** at neutral (0), both teams receive equal emotional weighting
**And** Q&A responses also respect the bias setting (FR-13).

**Given** the excitement slider is adjusted
**When** excitement changes
**Then** at maximum (1): vocabulary and energy level peak ("ABSOLUTELY MAGNIFICENT!" delivery style)
**And** at minimum (0): subdued, calm delivery with restrained vocabulary
**And** the slider affects word choice, sentence rhythm, and emotional intensity in LLM prompts.

**Given** the knowledge depth slider is adjusted
**When** knowledge changes
**Then** at beginner (0): explanations use simple terminology, explain rules ("A yellow card is a warning")
**And** at tactical deep-dive (1): assumes football knowledge, uses advanced terminology ("They've shifted to a 4-3-3 pressing high with inverted fullbacks")
**And** trivia cards also adapt depth to the slider setting.

**Given** the ControlsTray visibility behavior
**When** in narrated demo mode
**Then** the tray is always visible (judge must see features exist) (UX-DR10)
**And** when in Community Visitor mode: tray auto-hides after 3 seconds of no mouse movement
**And** tray reappears on any mouse movement
**And** tooltip appears on first hover for each control in Community Visitor mode.

**Given** keyboard navigation
**When** the ControlsTray has focus
**Then** Tab order follows visual order: Bias → Excitement → Knowledge → Language → View Toggle
**And** Arrow keys adjust sliders by ±10%
**And** Space/Enter toggles the language button and view toggle.

### Story 3.4: Language Toggle & Meaning-Preserving Translation

As a fan or commentator,
I want to switch commentary to another language with a single click and hear the same meaning and emotional register preserved,
So that the experience works for multilingual audiences without losing the poetic quality of the commentary.

**Acceptance Criteria:**

**Given** the language toggle button is visible in ControlsTray
**When** the toggle shows "EN | ES"
**Then** the current language is highlighted (Amber 400 for active, Slate 400 for inactive)
**And** the toggle has `aria-label="Switch commentary to Spanish"` (updates dynamically)
**And** the toggle is keyboard accessible (Space/Enter to toggle).

**Given** the user clicks the language toggle
**When** the switch is triggered
**Then** commentary audio mutes with a crossfade transition (not a hard cut)
**And** the switch completes in under 3 seconds total (NFR-2)
**And** audio silence is less than 500ms
**And** commentary resumes in the selected language with preserved meaning and emotional register (FR-15).

**Given** translation from English to Spanish
**When** translating commentary text
**Then** semantic meaning is preserved exactly (e.g., "Roma have risen from their ruins" carries the same historical allusion in Spanish)
**And** poetic register is maintained — no cultural stereotype substitution
**And** emotional intensity matches the original (excitement level preserved across languages)
**And** the translation reads from the same KV cache context as the English commentary, preserving temporal grounding.

**Given** the language switch occurs during a high-intensity moment (goal, red card)
**When** a goal celebration is in progress
**Then** the switch is deferred until the celebration subsides (never interrupt a peak moment)
**And** a subtle indicator shows "Switching to Spanish..." if deferred
**And** the switch completes automatically once the moment passes.

**Given** trivia cards are displayed
**When** the language is switched
**Then** active and future trivia cards also display in the selected language (FR-16)
**And** suggested question chips translate to match
**And** the transition is seamless — no flash of the old language on new cards.

**Given** language prompts are pre-loaded
**When** the system starts
**Then** both English and Spanish prompt templates are loaded into memory
**And** the toggle is a routing change (selecting which prompt template to use), not a model load
**And** this enables the < 3s switch latency (NFR-2).


## Epic 4: Deployment, Polish & Community Readiness

The Space is live on Hugging Face, deployable with a single `git push`, includes self-guided demo mode for community visitors, and meets all latency, accessibility, and memory requirements.

**FRs covered:** FR18, FR19, FR20
**NFRs covered:** NFR1 through NFR12

### Story 4.1: Docker Build & HF Space Deployment

As a developer,
I want a multi-stage Docker build that deploys to Hugging Face Spaces with a single `git push` and configurable GPU endpoint,
So that the Space is publicly accessible to judges and community visitors without manual infrastructure setup.

**Acceptance Criteria:**

**Given** the `Dockerfile` is at the project root
**When** the Docker build runs
**Then** Stage 1 builds the React frontend (node, npm build → static dist/)
**And** Stage 2 uses python:3.11-slim, copies dist/ for static file serving
**And** Stage 2 copies agents/, config/, data_sources/, models/, api/, streaming/, scripts/
**And** FastAPI serves static frontend files + WebSocket at `/ws/live`
**And** a HEALTHCHECK is configured at `/health`
**And** the container consumes under 12GB RAM before model loading (NFR-6) — GPU models run exclusively on the AMD droplet
**And** no model weights are included in the container.

**Given** the `huggingface-space.yml` metadata file
**When** the Space is configured
**Then** `sdk: docker` is set (Dockerfile-based, not Gradio)
**And** `tags: [amd, amd-hackathon-2026, vllm, gradio]` are present (FR-19)
**And** the README.md includes YAML frontmatter with `sdk: docker`, tags, and Space secrets setup instructions.

**Given** the GPU inference endpoint is configured via Space secret `VLLM_BASE_URL`
**When** the secret is set to the AMD droplet URL (http://<droplet-ip>:8000)
**Then** the FastAPI backend connects to the GPU endpoint for all vision model inference
**And** the endpoint URL can be changed without a Space rebuild (NFR-10)
**And** the system reconnects to the new endpoint within 10 seconds of Space restart.

**Given** the deployment script `scripts/deploy_hf.sh`
**When** executed
**Then** a single `git push` to the HF Space remote deploys the application (NFR-12)
**And** no manual SSH or droplet-side configuration is required beyond initial SGLang/vLLM endpoint startup
**And** the script validates that `VLLM_BASE_URL` is configured as a Space secret.

**Given** the Space is deployed
**When** a user opens the Space URL
**Then** the page loads and begins playing video within 20 seconds (NFR-3)
**And** the vision model attaches to the stream within an additional 30 seconds (background warm-up)
**And** the Space serves the demo without crashing or exceeding memory limits for the full 5-minute judge session (SC-09).

### Story 4.2: Self-Guided Demo Mode & Landing Page

As a community visitor arriving at the PitchAI HF Space outside the demo window,
I want to discover what PitchAI does within 10 seconds and try features on my own without a narrator,
So that I experience the "wow" moment and leave a like on the Space.

**Acceptance Criteria:**

**Given** the landing page renders for a first-time visitor
**When** the page loads
**Then** a centered hero displays on Slate 950 background: "PitchAI" in Inter Bold, amber + "Your AI Broadcast Companion" tagline (UX-DR13)
**And** an Amber pill CTA button: "Start Watching"
**And** three feature pills below: "Live Commentary Notes", "Contextual Q&A", "Cross-Language Translation"
**And** a subtle green pitch line accent at the bottom
**And** the landing page is skipped entirely during narrated demo (Space URL opens directly to video stream).

**Given** the visitor clicks "Start Watching" or arrives via a deep link
**When** the video page loads
**Then** a sample match video begins playing immediately (no spinner)
**And** pre-generated commentary notes are loaded (pre-computed for the sample match)
**And** within 10-30 seconds, the first trivia card fades in
**And** the visitor understands: "This is football + AI" within 10 seconds.

**Given** a first-time visitor arrives via a deep link directly to the video (bypassing the landing page)
**When** the page loads
**Then** a first-visit overlay appears for 4 seconds: "PitchAI — Your AI Broadcast Companion. Trivia cards explain the action. Hold the mic to ask questions." (UX-DR14)
**And** the overlay fades out automatically (no dismissal required)
**And** it is skipped on return visits via localStorage flag.

**Given** the Community Visitor mode (no narrator, no pre-set timing)
**When** the visitor explores
**Then** the controls tray is always visible (unlike narrated demo where narrator triggers features) (UX-DR28)
**And** tooltips appear on first hover for every control
**And** suggested question chips appear on the FIRST trivia card (accelerated vs demo pacing)
**And** the language toggle is prominently labeled "EN | ES"
**And** the visitor tries a feature (chip tap or control interaction) within 30 seconds.

**Given** the README below the video fold
**When** the visitor scrolls down
**Then** the README is scannable in under 5 seconds: screenshot, one-liner description, setup command, star button
**And** links to the original project repository
**And** clear attribution for data sources and models.

**Given** the self-guided mode needs pre-seeded content
**When** the Space starts
**Then** a sample match video is bundled or linked
**And** pre-generated commentary notes are available at startup (generated from the sample fixture)
**And** suggested questions are pre-seeded for the sample match: "Why is that a red card?", "Who is number 10?", "What formation are they playing?"
**And** the Q&A tap path works with these pre-seeded questions without a narrator.

### Story 4.3: Design Tokens, Accessibility & Visual Polish

As any user of PitchAI,
I want the UI to feel professional, consistent, and accessible regardless of how I interact with it,
So that the experience is polished for judges and usable by everyone, including screen reader and keyboard-only users.

**Acceptance Criteria:**

**Given** the Tailwind CSS config is updated
**When** the design tokens are applied
**Then** the dark theme uses the full semantic color palette: Background Slate 950 (#020617), Surface Slate 900 (#0F172A), Amber 400 narrative accent, Cyan 400 interactive accent (UX-DR1)
**And** Amber 400 is reserved exclusively for narrative moments (teleprompter beat, recording state) (UX-DR24)
**And** Cyan 400 is reserved exclusively for interactive states (focus rings, hover, selected chips, slider thumbs) (UX-DR24)
**And** all color combinations meet WCAG 2.1 AA minimum; primary text meets AAA 7:1+ (UX-DR2).

**Given** the typography system
**When** text renders across components
**Then** Inter is used for all UI text with system stack fallback (UX-DR3)
**And** JetBrains Mono is used for data: source attribution, confidence badges, agent progress, timestamps (UX-DR3)
**And** the 7-level type scale (xs 12px → 3xl 30px) and 4-level weight hierarchy (Regular → Bold) are applied consistently.

**Given** the spacing system
**When** components render
**Then** all spacing uses multiples of 4px (Tailwind default) (UX-DR4)
**And** the 8-token spacing scale (space-1 4px → space-12 48px) is applied consistently
**And** the viewport targets 1440px reference, minimum 1280px — no responsive breakpoints for hackathon scope.

**Given** accessibility requirements (UX-DR20)
**When** keyboard navigation is tested
**Then** Tab order follows: MicButton → Language Toggle → Bias → Excitement → Knowledge → View Toggle
**And** Space/Enter activates buttons and toggles
**And** Arrow keys adjust sliders by ±10%
**And** Escape dismisses Q&A, closes settings panels
**And** all interactive elements have visible Cyan 400 focus rings (2px, offset).

**Given** screen reader access
**When** ARIA labels are verified
**Then** all shadcn/ui components include ARIA labels via Radix primitives (UX-DR20)
**And** trivia cards have `role="status" aria-live="polite"`
**And** MicButton states announce via dynamic `aria-label`
**And** SplitScreen has `role="region" aria-label="Question answer: showing the relevant match moment"`
**And** Q&A answers use `role="alert" aria-live="assertive"`
**And** sliders have `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, descriptive `aria-label`.

**Given** motion sensitivity (UX-DR20)
**When** `prefers-reduced-motion: reduce` is set
**Then** all CSS transitions are set to 0ms
**And** canvas/JS animations (overlay draw, split-screen slide) check `window.matchMedia('(prefers-reduced-motion: reduce)')` and render instantly
**And** card fades become cuts
**And** split-screen becomes instant snap
**And** teleprompter auto-scroll becomes instant jump.

**Given** color independence (UX-DR2)
**When** confidence or state is communicated
**Then** confidence is never communicated by color alone — always paired with a numeric badge
**And** state indicators include icon + color + text (e.g., recording: red ring + mic icon + "Recording..." label)
**And** overlay annotations use stroke + fill + dropshadow contrast, not color alone for differentiation.

**Given** confidence-gated UI consistency (UX-DR21)
**When** reviewing all 5 components that use confidence gating
**Then** STT confirmation, player ID display, overlay precision, and teleprompter highlighting all follow the same 3-tier pattern
**And** source attribution badges appear on every stat (StatsBomb/Firecrawl/FBref)
**And** low-confidence results never present as certain.

**Given** graceful degradation UX (UX-DR22)
**When** reviewing all degraded states
**Then** "Based on available footage" is used for KV cache misses — calm, not alarming
**And** "Notes available — manual scroll" is used when vision events are unavailable
**And** "Commentary is limited right now — enjoy the match" is the single compound-failure message
**And** every degraded state has a path forward — never dead-end at "something went wrong."

**Given** shadcn/ui components are integrated (UX-DR23)
**When** the component library is imported
**Then** 8 components are themed to PitchAI dark tokens: Button, Slider, Card, Badge, Dialog, Toggle, Tooltip, Progress
**And** components are copied into the project (not npm dependency) for full source control
**And** all components use the dark theme via Tailwind `dark:` class.

### Story 4.4: Latency, Fallback & Cross-Browser Validation

As a developer shipping for hackathon judging,
I want to verify that all latency budgets, fallback levels, and cross-browser compatibility requirements are met,
So that the 5-minute judge demo runs without a single visible failure.

**Acceptance Criteria:**

**Given** latency budgets are measured (NFR-01 to NFR-05)
**When** benchmarking under single-user load
**Then** Audio Q&A responds in under 3.5 seconds end-to-end, measured at P95 (NFR-01)
**And** Language switch completes in under 3 seconds with less than 500ms audio silence (NFR-02)
**And** Cold start loads video within 20 seconds of page open (NFR-03)
**And** Commentary TTFT is under 500ms from match event detection (NFR-04)
**And** Vision frame processing maintains a minimum of 5 FPS on MI300X (NFR-05).

**Given** the 4-level fallback chain (NFR-09)
**When** each fallback level is tested
**Then** Level 1 (SGLang + StreamingVLM): all features functional at full capability
**And** Level 2 (SGLang + Custom KV Window): loses StreamingVLM optimizations but retains temporal continuity
**And** Level 3 (Pre-computed Embeddings + vLLM): loses temporal scrub, Q&A degrades to static context
**And** Level 4 (vLLM Frame-by-Frame): no temporal continuity, baseline functionality
**And** fallback activation completes within 30 seconds at each level
**And** the UX communicates degradation calmly at each level (Story 4.3 graceful degradation).

**Given** memory budgets (NFR-06 to NFR-08)
**When** monitoring resource usage
**Then** HF Space container consumes under 12GB RAM before model loading (NFR-06)
**And** MI300X VRAM consumption does not exceed 60GB: Qwen2.5-VL-7B-AWQ (~7-9GB) + KV cache buffer (~20-30GB) + agent LLM context (~5-10GB) + overhead (~10GB) (NFR-07)
**And** KV cache retains a minimum of 120 seconds of visual context (NFR-08).

**Given** player identification accuracy (NFR-11)
**When** tested on the demo video with known players under normal camera angles and lighting
**Then** identification accuracy exceeds 90% on known players
**And** all misidentifications include uncertainty qualifiers in output.

**Given** cross-browser testing (UX-DR25 Phase 4)
**When** testing on Chrome, Firefox, and Edge
**Then** video autoplay works across all browsers
**And** Browser Web Speech API functions correctly (primary: Chrome)
**And** WebSocket connection and reconnection behave identically
**And** canvas/SVG rendering is consistent across browsers
**And** animation performance is smooth (60fps CSS, 5 FPS canvas) across browsers.

**Given** chaos testing scenarios (UX-DR25 Phase 4)
**When** the following scenarios are tested
**Then** flood of 10 events in 5 seconds → priority queue drops correctly, no UI freeze or crash
**And** browser resize during canvas draw → dimension guard catches mismatch, skips frame, re-syncs
**And** STT timeout (Chrome `onend` bug) → 15s timeout auto-cancels empty recording
**And** WebSocket drop mid-Q&A → answer completes from cached context if possible, reconnects silently
**And** compound failure (vision + stats both degraded) → single calm fallback message, no error cascade
**And** GPU endpoint unreachable → fallback chain activates within 30s, Space continues serving frontend.