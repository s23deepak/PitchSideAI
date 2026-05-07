---
stepsCompleted: ["step-01-validate-prerequisites"]
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/architecture.md"
  - "_bmad-output/planning-artifacts/ux-design-specification-midnight-stadium.md"
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

FR19: **README YAML Frontmatter** — The Space README.md shall include YAML frontmatter with `sdk: docker`, `tags: [amd, amd-hackathon-2026, sglang, vllm]`, and clear setup instructions for Space secrets.

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

NFR9: **Fallback Chain Activation** — When the primary streaming path (SGLang + StreamingVLM) fails to initialize, the system shall activate the next fallback level within 30 seconds. Each fallback level shall document which capabilities are degraded: Level 2 (SGLang + Custom KV Window — loses StreamingVLM optimizations but retains temporal continuity), Level 3 (Pre-computed embeddings + vLLM — loses temporal scrub, Q&A degrades to static context), Level 4 (vLLM Frame-by-Frame — no temporal continuity).

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

- **4-Level Fallback Chain:** Level 1: SGLang + StreamingVLM 7B (full capability — primary path). Level 2: SGLang + Custom KV Sliding Window (loses StreamingVLM optimizations, retains temporal continuity). Level 3: Pre-computed Vision Embeddings + vLLM (loses temporal scrub, Q&A degrades to static context). Level 4: vLLM Frame-by-Frame (no temporal continuity). Architecture supports all levels without code change.

- **Docker Multi-Stage Build:** Stage 1: Frontend build (node, npm build → static dist/). Stage 2: Backend (python:3.11-slim, FastAPI + uvicorn, copies dist/, agents/, config/, data_sources/, models/, api/). HEALTHCHECK at /health. Single container → HF Space (Docker SDK).

- **HF Space Configuration:** `sdk: docker`, `tags: [amd, amd-hackathon-2026, sglang, vllm]`, README YAML frontmatter with setup instructions, Space secret `VLLM_BASE_URL` for GPU endpoint.

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

### Story 4.5: Local StreamingVLM Testing on RTX 5060 8GB

As a developer testing locally before deploying to the AMD MI300X,
I want to load StreamingVLM from HuggingFace (with Qwen2.5-VL 3B/7B fallback) and run inference on my RTX 5060 8GB,
So that I can validate the streaming vision pipeline works on consumer hardware before cloud deployment.

**Acceptance Criteria:**

**Given** the test script `scripts/test_streamingvlm_rtx5060.py` is executed
**When** the script starts
**Then** it detects the RTX 5060 8GB GPU via CUDA
**And** reports VRAM (free/total) and compute capability
**And** sets a memory budget of 6.0 GB (leaving 2GB headroom for system).

**Given** the model loading sequence
**When** loading models from HuggingFace
**Then** it tries in order: (1) `mit-han-lab/StreamingVLM-3B`, (2) `Qwen/Qwen2.5-VL-3B-Instruct`, (3) `Qwen/Qwen2.5-VL-7B-Instruct`
**And** uses the first successfully loaded model
**And** loads with `torch_dtype=torch.float16` for 8GB VRAM efficiency
**And** uses Flash Attention 2 if available, otherwise SDPA fallback.

**Given** a successfully loaded model
**When** the image QA test runs
**Then** it loads a test image (sports-related or dummy fallback)
**And** processes with the model's chat template
**And** generates a response with max 100 tokens
**And** decodes and displays the result.

**Given** a successfully loaded model
**When** the video chunk test runs
**Then** it creates 8 dummy frames (simulating ~1 second at 8 FPS)
**And** processes all frames through the model
**And** generates a response with max 50 tokens
**And** reports input shape and decoded response.

**Given** the test completes
**When** the summary is displayed
**Then** it shows: model name, Image QA result (PASS/FAIL), Video Chunk result (PASS/FAIL)
**And** provides next-step commands for SGLang serving and PitchAI integration.

**Given** model loading fails for all candidates
**When** all three model attempts fail
**Then** the script exits with helpful suggestions: check internet, run `huggingface-cli login`, download manually first.

**Given** memory constraints on 8GB card
**When** any test runs
**Then** `torch.cuda.empty_cache()` is called between tests
**And** VRAM usage is reported after model load and after each test
**And** tests use `torch.cuda.amp.autocast(dtype=torch.float16)` for memory efficiency.

---

## MCP Server for Recursive Testing

**Configuration:** As each story is completed, an MCP server should be configured to run recursive tests automatically.

### Test Categories by Story

**Story 1.1 (Narrative Data Models):**
- Unit tests for `NarrativeBeat` dataclass field defaults and type hints
- Unit tests for `NotesStore` lookup table construction (O(1) verification)
- Unit tests for `tag_resolver` 3-tier resolution (exact → synonym → substring → None)
- Unit tests for goal safety gate (score change verification)

**Story 1.2 (Streaming Vision Pipeline):**
- Integration tests for `streaming/factory.py` backend selection
- Mock HTTP tests for `sglang_client.py` connection and fallback triggering
- Unit tests for `frame_sampler.py` 5 FPS throttling and diversity scoring
- Unit tests for `kv_cache.py` 120s retention and eviction policy

**Story 1.3 (Notes Pipeline):**
- Integration tests for 7-agent 3-phase execution order
- Tests for 3-layer stats fallback chain (StatsBomb → Firecrawl → FBref)
- WebSocket message format validation for `progress` callbacks
- Tests for `notes_ready` message structure (beat_count, sections, timestamp)
- Backwards compatibility tests for `.raw_markdown` accessor

**Story 1.4 (Vision-Triggered Commentary):**
- Integration tests for tag resolution → lookup → commentary injection chain
- Latency tests for commentary TTFT (< 500ms from event detection)
- WebSocket message format validation for `commentary` broadcasts
- Tests for `game_state.to_context_string()` injection in every prompt

**Story 1.5 (VideoCanvas):**
- Component tests for video autoplay within 20s
- Tests for `useWebSocket` hook reconnection with exponential backoff
- Canvas draw loop tests (5 FPS throttling, dimension guard)
- Status dot state tests (emerald/amber/red transitions)

**Story 1.6 (Trivia Cards):**
- Component tests for card fade in/out timing (400ms, 5s display)
- Priority queue tests (goal/red card bypass, substitution priority, oldest drop)
- Tests for minimum 8s gap between non-priority cards
- Accessibility tests (`role="status"`, `aria-live="polite"`)

**Story 2.1 (MicButton & STT):**
- Component state tests (7 states: Idle, Hover, Recording, Processing, Disabled-ModelWarming, Disabled-NoMic, Hidden)
- Tests for 15s max recording timeout auto-submit/cancel
- Tests for hold ≥ 300ms (clicks ignored)
- STT confidence gate tests (> 90% proceed, 70-90% confirm, < 70% reject)
- Tests for 3x consecutive STT failure → suggested chips offer

**Story 2.2 (Q&A Backend):**
- WebSocket handler tests for `query` message processing
- Tests for `game_state` and settings injection in Q&A prompts
- Latency tests for Q&A end-to-end (< 3.5s P95)
- Tests for pre-computed Q&A pair cache hits (< 1s)
- Tests for KV cache miss graceful degradation ("Based on available footage")

**Story 2.3 (SplitScreen):**
- Component tests for 60/40 split animation (300ms ease-out/in)
- SVG overlay rendering tests (stroke-dasharray draw-on, 200ms per element)
- Tests for content-ready timeout (500ms → loading skeleton)
- Tests for Escape dismissal and auto-resolve (5-8s)
- Accessibility tests (`role="region"`, `aria-label`)

**Story 2.4 (Player Identification):**
- Vision agent tests for player ID confidence scoring
- Tests for confidence > 90% (no qualifier), 70-90% (qualifier), < 70% (ambiguity)
- Accuracy tests on demo video (> 90% on known players)
- Tests for SVG overlay precision (circle vs zone based on confidence)

**Story 3.1 (Teleprompter Static):**
- Component tests for empty/generating/ready/degraded states
- Tests for Tabbed Mode (5 sections) vs Long-Sheet Mode toggle
- Progress callback parsing tests (agent status, items processed)
- Accessibility tests (`role="complementary"`)

**Story 3.2 (Teleprompter Auto-Highlight):**
- Tests for amber highlighting (15% bg, 3px border, ▶ marker)
- Auto-scroll tests (300ms, current beat at ~30% from top)
- Hold Mode tests (manual scroll cancels auto, "Back to live"/"Catch up" buttons)
- Tests for confidence threshold (don't highlight below threshold)
- Tests for surprise event handling (gap acknowledgement)

**Story 3.3 (Commentary Settings):**
- Component tests for 3 sliders with gradient tracks
- WebSocket `settings_update` message format tests
- Tests for immediate application (no "apply" button)
- Tests for Bias effect on goal commentary (Team A joy vs Team B subdued)
- Tests for ControlsTray auto-hide (3s idle, desktop only)

**Story 3.4 (Language Toggle):**
- Component tests for EN|ES toggle state
- Tests for audio mute crossfade (< 3s total, < 500ms silence)
- Translation quality tests (semantic meaning + poetic register preserved)
- Tests for high-intensity moment deferral (never interrupt goal celebration)
- Tests for trivia card translation on switch

**Story 4.1 (Docker & HF Space):**
- Docker build tests (multi-stage, frontend build, backend copy)
- Container memory tests (< 12GB RAM before model loading)
- Tests for `VLLM_BASE_URL` secret reconnection (< 10s)
- Deployment script tests (single `git push` validation)

**Story 4.2 (Self-Guided Demo):**
- Landing page component tests (hero, feature pills, CTA)
- First-visit overlay tests (4s auto-fade, localStorage skip)
- Tests for suggested question chips on first trivia card
- README scannability tests (layout, links, attribution)

**Story 4.3 (Design Tokens & Accessibility):**
- Visual regression tests for all components (Midnight Stadium tokens)
- Keyboard navigation tests (Tab order, Space/Enter, Arrows, Escape)
- Screen reader tests (ARIA labels on all interactive elements)
- Tests for `prefers-reduced-motion` (0ms transitions, instant animations)
- Tests for confidence-gated UI consistency across 5 components

**Story 4.4 (Latency & Fallback Validation):**
- End-to-end latency benchmarks (Q&A < 3.5s, language switch < 3s, cold start < 20s)
- Fallback chain activation tests (Level 1→2→3→4, < 30s per level)
- Memory budget tests (Space < 12GB, MI300X < 60GB, KV cache ≥ 120s)
- Cross-browser tests (Chrome, Firefox, Edge: video autoplay, Web Speech API, WebSocket, canvas/SVG)
- Chaos tests: 10-event flood, browser resize during draw, STT timeout, WebSocket drop mid-Q&A, compound failure, GPU unreachable

**Story 4.5 (Local StreamingVLM Testing):**
- GPU detection tests (CUDA available, device name, VRAM reporting)
- Model loading tests (StreamingVLM → Qwen2.5-VL 3B → Qwen2.5-VL 7B fallback chain)
- Memory budget tests (6GB limit on 8GB card, `torch.cuda.empty_cache()` between tests)
- Image QA inference tests (load image, process, generate ≤100 tokens, decode)
- Video chunk tests (8 dummy frames, process, generate ≤50 tokens, report input shape)
- Flash Attention 2 availability detection (fallback to SDPA if unavailable)
- Test summary output (model name, Image QA PASS/FAIL, Video Chunk PASS/FAIL)
- Next-step commands display (SGLang serving, PitchAI integration, StreamingVLM inference)

### MCP Server Configuration

The MCP server should:
1. Watch for story completion markers in the task list
2. Trigger the relevant test suite automatically
3. Report pass/fail status back to the task list
4. Block story marking as "complete" until tests pass
5. Maintain a test results log in `_bmad-output/test-results/`

---

## Epic 5: UI/UX Revamp — Midnight Stadium Redesign

**Status:** in-progress  
**Priority:** Critical  
**Target:** Hackathon Demo Visual Excellence

Epic 5 represents a complete visual and interaction redesign of PitchAI, transforming the interface from a functional sports app into a premium "Midnight Stadium" experience. This epic implements the full design token system, component library, and responsive layouts that make PitchAI feel like a professional broadcast product.

### HTML Screen References

All Epic 5 stories are based on the HTML prototypes in `.bmad/screens/`. Each story maps to a reference screen:

| Story | Screen File | Description |
|-------|-------------|-------------|
| 5.1 | `midnight-stadium-design.md` | Design system documentation (tokens, typography, spacing) |
| 5.2 | N/A — Component library | shadcn/ui integration (no single screen) |
| 5.3 | `pitchai-landing-page.html` | Landing page with hero, feature pills, CTA |
| 5.4 | `fan-lens-broadcast.html` | Fan Lens view (video, trivia card, controls, mic button) |
| 5.5 | `commentator-dashboard.html` | Commentator Dashboard (60/40 split with teleprompter) |
| 5.6 | `commentator-dashboard.html` | Teleprompter component (static + auto-highlight modes) |
| 5.7 | `fan-lens-broadcast.html` | MicButton component (hold-to-record, 7 states) |
| 5.8 | `fan-ai-temporal-replay.html` | SplitScreen Q&A temporal navigation |
| 5.9 | `fan-lens-broadcast.html` | ControlsTray component (5 controls) |
| 5.10 | `fan-lens-broadcast.html` | TriviaCard component (priority queue, animations) |
| 5.11 | `fan-lens-broadcast.html` | VideoCanvas component (connection state, canvas overlays) |
| 5.12 | All screens | Responsive layout (desktop → tablet → mobile) |

**Playwright Testing Requirement:** Each story includes MCP server-based Playwright UI tests that validate the implemented component against the HTML reference screen. Tests verify visual regression, accessibility (ARIA, keyboard navigation), animation timing, and responsive behavior.

### Design Vision

**Theme:** "Midnight Stadium" — Dark, immersive, broadcast-quality UI that feels like being in a stadium at night under the lights.

**Design Principles:**
1. **Immersion First** — Match video is always the hero; UI elements are ephemeral guests
2. **Confidence Through Clarity** — Every stat, badge, and overlay communicates certainty levels
3. **Accessible Excellence** — WCAG 2.1 AA is the floor, not the ceiling
4. **Motion With Meaning** — Every animation serves a functional purpose, not decoration

---

### Story 5.1: Design System Foundation — Midnight Stadium Tokens

As a UI developer,
I want a complete design token system with semantic colors, typography, and spacing,
So that all components share a consistent visual language.

**Reference:** `.bmad/midnight-stadium-design.md` — Design system documentation

**Acceptance Criteria:**

**Given** the `frontend/src/design-tokens/` directory
**When** design tokens are defined
**Then** the following token categories exist:

**Color Tokens:**
- Background: `bg-primary` (#020617 Slate 950), `bg-surface` (#0F172A Slate 900), `bg-elevated` (#1E293B Slate 800)
- Narrative Accent: `accent-narrative` (#FBBF24 Amber 400) — teleprompter beats, recording state
- Interactive Accent: `accent-interactive` (#22D3EE Cyan 400) — focus rings, hover, selected
- Semantic: `success` (#10B981), `warning` (#F59E0B), `danger` (#EF4444)
- Text: `text-primary` (#F1F5F9), `text-secondary` (#94A3B8), `text-muted` (#64748B)

**Typography Tokens:**
- Fonts: `font-display` (Inter), `font-body` (Inter), `font-mono` (JetBrains Mono)
- Scale: `xs` (12px), `sm` (14px), `base` (16px), `lg` (18px), `xl` (20px), `2xl` (24px), `3xl` (30px)
- Weights: `regular` (400), `medium` (500), `semibold` (600), `bold` (700)

**Spacing Tokens:**
- Base unit: 4px
- Scale: `space-1` (4px) through `space-12` (48px) in Tailwind convention

**Motion Tokens:**
- Durations: `fast` (150ms), `normal` (300ms), `slow` (500ms)
- Easing: `ease-in-out`, `ease-out`, `linear`
- Reduced motion: `prefers-reduced-motion` media query support

**And** tokens are organized as CSS custom properties in `frontend/src/design-tokens/tokens.css`
**And** Tailwind config extends with token references in `tailwind.config.ts`
**And** A documentation file exists at `_bmad-output/design-system/color-tokens.md`

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Token snapshot test: Verify all CSS custom properties exist in computed styles
- [ ] [AI-Test] Color contrast audit: Verify all text combinations meet WCAG 2.1 AA (4.5:1 minimum, 7:1+ for AAA)
- [ ] [AI-Test] Typography scale visual regression: Capture all 7 type sizes at 3 weights
- [ ] [AI-Test] Reduced motion test: Verify `prefers-reduced-motion` media query is respected

---

### Story 5.2: Component Library — shadcn/ui Integration

As a UI developer,
I want a reusable component library themed to Midnight Stadium tokens,
So that building new features is fast and consistent.

**Reference:** `.bmad/midnight-stadium-design.md` — Component quick specs (MicButton, ControlsTray, Teleprompter, TriviaCard)

**Acceptance Criteria:**

**Given** the `frontend/src/components/ui/` directory
**When** shadcn/ui components are installed and themed
**Then** the following 10 components are available:

| Component | Usage | Themed Variants |
|-----------|-------|-----------------|
| Button | Mic base, language toggle, CTAs | default, narrative, ghost, outline, danger |
| Slider | Bias/excitement/knowledge sliders | with tooltip, discrete steps |
| Card | Trivia container, teleprompter panel | elevated, flat, bordered |
| Badge | Confidence, source, LIVE, agent status | default, success, warning, danger, mono |
| Progress | Agent pipeline completion bar | gradient, animated |
| Toggle | Fan/Commentator view switch | pressed/unpressed |
| Tooltip | Control hover labels | auto-positioning, arrow |
| Dialog | Notes generation progress modal | with backdrop, Escape handling |
| Tabs | Teleprompter section tabs | underlined, pills |
| ScrollArea | Teleprompter long-sheet | custom scrollbar, auto-hide |

**And** all components support keyboard navigation (Tab, Space, Enter, Arrow keys, Escape)
**And** all components have proper ARIA labels via Radix primitives
**And** all components respect `prefers-reduced-motion`
**And** components are exported from `frontend/src/components/ui/index.ts`

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Component snapshot: Capture all 10 components in all variants (dark surface #1A1A1A, border #353535)
- [ ] [AI-Test] Keyboard navigation audit: Tab through all components, verify focus rings (Cyan 400, 2px)
- [ ] [AI-Test] ARIA validation: Verify all Radix primitives expose correct aria-* attributes
- [ ] [AI-Test] Reduced motion test: Verify animations disabled when `prefers-reduced-motion: reduce`

---

### Story 5.3: Landing Page — Hero Experience Redesign

As a community visitor arriving at PitchAI,
I want to immediately understand what PitchAI does and feel excited to try it,
So that I engage with the demo within 10 seconds.

**Acceptance Criteria:**

**Given** the landing page at `/`
**When** it renders
**Then** the layout follows this structure:

```
┌─────────────────────────────────────────────┐
│                                             │
│           ⚽ PitchAI                        │
│         (Inter Bold, 3xl, Amber 400)        │
│                                             │
│    Your AI Broadcast Companion              │
│         (text-secondary, xl)                │
│                                             │
│         [ Start Watching ▶ ]                │
│         (Amber pill CTA, narrative)         │
│                                             │
│    ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│    │ Live     │ │ Context- │ │ Cross-   │  │
│    │Commentary│ │ ual Q&A  │ │Language  │  │
│    │  Notes   │ │          │ │Translation│  │
│    └──────────┘ └──────────┘ └──────────┘  │
│         (Feature pills, Badge secondary)    │
│                                             │
│  ═══════════════════════════════════════    │
│  (Green pitch line accent, success/30%)     │
└─────────────────────────────────────────────┘
```

**And** the CTA button navigates to `/watch`
**And** feature pills have subtle hover animations (scale 1.02, Cyan ring)
**And** the green pitch line accent spans the full width at bottom
**And** the page is responsive down to 1280px minimum viewport
**And** first-visit overlay appears for 4 seconds (localStorage gated)

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Hero rendering: Verify title, tagline, CTA visible within 3s of page load
- [ ] [AI-Test] CTA navigation: Click "Start Watching" → verify navigation to `/watch`
- [ ] [AI-Test] Feature pills hover: Hover each pill → verify scale 1.02 + Cyan 400 ring
- [ ] [AI-Test] First-visit overlay: Clear localStorage → verify overlay appears for 4s
- [ ] [AI-Test] Responsive layout: Test at 1440px, 1280px, 1024px → verify no horizontal scroll

---

### Story 5.4: Video Page Layout — Fan Lens Redesign

As a fan watching the match,
I want the video to be immersive with trivia cards and controls that feel polished,
So that I'm engaged in the experience without distraction.

**Acceptance Criteria:**

**Given** the video page at `/watch`
**When** it renders in Fan Lens mode
**Then** the layout is:

```
┌─────────────────────────────────────────────────────┐
│  ● (Connection status dot, top-right)               │
│                                                     │
│                                                     │
│         ┌─────────────────────────┐                 │
│         │                         │                 │
│         │     VIDEO CANVAS        │                 │
│         │     (16:9, centered)    │                 │
│         │                         │                 │
│         └─────────────────────────┘                 │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ [EN|ES] [Bias] [Excitement] [Knowledge]     │   │
│  │                                              │   │
│  │ [Fan Lens ▼]                                │   │
│  └─────────────────────────────────────────────┘   │
│         (ControlsTray, always visible)              │
│                                                     │
│  ┌─────────────┐                    🎤             │
│  │ Trivia Card │                  (MicButton)      │
│  │ Did you know?                                   │
│  │ Osimhen has 15 goals...                         │
│  │ StatsBomb · 2023/24                             │
│  └─────────────┘                                   │
│                                                     │
│  ┌──────┐ ┌──────┐ ┌──────┐                        │
│  │ Why   │ │ Who   │ │ What  │                     │
│  │ red   │ │ is    │ │ forma-│                     │
│  │ card? │ │ #10?  │ │ tion? │                     │
│  └──────┘ └──────┘ └──────┘                        │
│  (Suggested question chips, appear on first card)   │
└─────────────────────────────────────────────────────┘
```

**And** trivia cards fade in 400ms, display 5s, fade out 400ms
**And** priority queue (max depth 3) with goal/red card bypass
**And** MicButton is 48×48px, bottom-right, 16px inset
**And** ControlsTray auto-hides after 3s idle (Community Visitor mode)
**And** tooltips appear on first hover for every control

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Fan Lens layout: Verify video 16:9 centered, trivia card bottom-left, MicButton bottom-right
- [ ] [AI-Test] Trivia card animation: Verify fade-in 400ms, 5s display, fade-out 400ms
- [ ] [AI-Test] Priority queue: Trigger goal event → verify immediate card display (bypass queue)
- [ ] [AI-Test] ControlsTray auto-hide: Wait 3s idle → verify tray hidden; move mouse → verify reappear
- [ ] [AI-Test] First-hover tooltips: Hover each control → verify tooltip appears once (localStorage gated)

---

### Story 5.5: Video Page Layout — Commentator Dashboard Redesign

As a commentator using PitchAI,
I want a split view with video and teleprompter that feels like a professional broadcast tool,
So that I can deliver commentary while having my notes synced to the match.

**Acceptance Criteria:**

**Given** the video page at `/watch` in Commentator Dashboard mode
**When** it renders
**Then** the layout is:

```
┌─────────────────────────────────────────────────────────────────┐
│  ● (Connection)                                                  │
│                                                                  │
│  ┌───────────────────────┐ ┌─────────────────────────────────┐  │
│  │                       │ │  Commentary Notes               │  │
│  │                       │ │  ─────────────────────          │  │
│  │      VIDEO CANVAS     │ │  [Match Info] [Home] [Away]     │  │
│  │      (60% width)      │ │  [Tactical] [Historical]        │  │
│  │                       │ │                                 │  │
│  │                       │ │  ▶ Roma have risen from their   │  │
│  │                       │ │    ruins...                     │  │
│  │                       │ │    (Amber 15% bg, 3px left)     │  │
│  │                       │ │                                 │  │
│  │                       │ │    Victor Osimhen has...        │  │
│  │                       │ │    (Next 3 lines, slate-400)    │  │
│  └───────────────────────┘ │                                 │  │
│                            │    StatsBomb · 0.87             │  │
│  [ControlsTray below       │ │    (Mono, text-xs)            │  │
│   video, full width]       │ └─────────────────────────────────┘  │
│                            │     (Teleprompter, 40% width)        │
└─────────────────────────────────────────────────────────────────┘
```

**And** the 60/40 split is enforced with CSS grid
**And** current beat highlighting: Amber 400 at 15% bg, 3px left border, ▶ marker
**And** auto-scroll keeps current beat at ~30% from top (300ms smooth scroll)
**And** manual scroll within 500ms of auto-scroll → Hold Mode with "Back to live" button
**And** Tabbed Mode for pre-match (5 sections), Long-Sheet Mode for live
**And** View Toggle button switches between Fan Lens and Commentator Dashboard

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] 60/40 split: Verify CSS grid enforces 60% video, 40% teleprompter at 1440px
- [ ] [AI-Test] Beat highlighting: Verify Amber 400 15% bg, 3px left border, ▶ marker on current beat
- [ ] [AI-Test] Auto-scroll: Verify current beat positioned at ~30% from top
- [ ] [AI-Test] Hold mode: Manual scroll → verify "Back to live" button appears
- [ ] [AI-Test] View toggle: Click Fan Lens → verify trivia card appears; Click Commentator → verify teleprompter appears

---

### Story 5.6: Teleprompter Component — Static + Auto-Highlight Modes

As a commentator,
I want the teleprompter to show my notes with auto-highlighting synced to vision events,
So that I can scan the right line in under a second during live play.

**Acceptance Criteria:**

**Given** the Teleprompter component
**When** in Static Mode (pre-match or manual)
**Then**:
- 5 tabs: Match Info, Home Team, Away Team, Tactical, Historical
- Each tab shows raw_markdown for that section
- User can scroll manually through notes

**When** in Long-Sheet Mode (live with vision sync)
**Then**:
- Continuous scroll of all narrative beats
- Current beat highlighted: Amber 400 15% bg, 3px left border, ▶ marker
- Next 3 lines visible below (text-sm, slate-400, fading opacity)
- Previous line above (text-xs, slate-600)
- Auto-scroll animation 300ms, current beat at ~30% from top

**Given** user manually scrolls
**When** scroll occurs within 500ms of auto-scroll
**Then**:
- Auto-scroll animation cancelled
- Hold Mode entered
- Contextual button appears: "Back to live" (scrolled up) or "Catch up" (scrolled past)
- Tapping button resumes auto-scroll to current beat

**And** each line shows metadata badges: source (StatsBomb/Firecrawl/FBref) + confidence (JetBrains Mono, text-xs)
**And** beats with confidence < 0.6 are NOT highlighted (safety gate)

---

### Story 5.7: MicButton Component — Hold-to-Record Redesign

As a fan asking questions,
I want a microphone button that clearly communicates its state and responds to my interaction,
So that I know when I'm recording and when my question is submitted.

**Acceptance Criteria:**

**Given** the MicButton component
**When** in each of 7 states
**Then** it renders:

| State | Visual | Behavior |
|-------|--------|----------|
| Idle | Slate 900 85% opacity, Slate 800 ring, slate-400 mic icon | Tooltip on first hover: "Hold to ask a question" |
| Hover | Cyan 400 ring (2px), white icon, glow effect | Tooltip appears (first hover only, localStorage gated) |
| Recording | Red 500 ring, pulses 48→52px, Snapchat progress arc | Ghost text below (50% opacity, Web Speech API interim results) |
| Processing | Amber 400 rotating gradient ring | Video vignette 5%, hidden during active Q&A |
| Disabled (Model Warming) | 50% opacity | Tooltip: "AI warming up... ready in ~20s" |
| Disabled (No Mic) | 50% opacity | Tooltip: "Microphone not available" |
| Hidden | display: none | During active Q&A split-screen |

**And** hold ≥ 300ms required (clicks ignored)
**And** 15s max recording timeout (auto-submit if interim results, auto-cancel if empty)
**And** Space key hold triggers same behavior (keyboard accessible)
**And** Escape cancels recording or dismisses active Q&A
**And** aria-label updates with state: "Hold to ask a question" → "Recording..." → "Processing your question"

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] State transitions: Test all 7 states (Idle, Hover, Recording, Processing, Disabled-Warming, Disabled-NoMic, Hidden)
- [ ] [AI-Test] Hold-to-record: Hold 300ms → verify Recording state; Click <300ms → verify ignored
- [ ] [AI-Test] 15s timeout: Simulate 15s hold → verify auto-submit with interim results OR auto-cancel if empty
- [ ] [AI-Test] Keyboard accessibility: Hold Space → verify Recording; Release → verify submit; Escape → verify cancel
- [ ] [AI-Test] ARIA labels: Verify aria-label updates with each state transition

---

### Story 5.8: SplitScreen Component — Q&A Temporal Navigation

As a fan receiving a Q&A answer,
I want the screen to split and show the exact match moment with AI-drawn overlays,
So that I see the explanation drawn on the moment I asked about.

**Acceptance Criteria:**

**Given** an `answer` WebSocket message with temporal context
**When** SplitScreen activates
**Then**:
- Left panel: Live match at 60% width (continues playing)
- Right panel: Frozen frame at 40% width from relevant timestamp
- Divider: 2px Slate 800, non-draggable
- Slide animation: 300ms ease-out in, 300ms ease-in out

**Given** overlay coordinates in answer payload
**When** SVG overlays render on frozen frame
**Then**:
- stroke-dasharray draw-on animation (200ms per element)
- Elements draw in sequence: circle → arrow → line → label
- High confidence: precise circle around player/zone
- Medium confidence: wider zone highlight + label
- All strokes: White 90% opacity with 1px blur dark dropshadow

**Given** `prefers-reduced-motion: reduce`
**When** SplitScreen activates
**Then**:
- Slide animation is instant (0ms)
- Overlay draw-on animations are instant
- Content still appears correctly

**And** `role="region" aria-label="Question answer: showing the relevant match moment"`
**And** Escape dismisses with 200ms ease-in
**And** Auto-resolves after 5-8 seconds
**And** Content-ready timeout 500ms → loading skeleton if frame not loaded

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Split animation: Verify 300ms slide-in (60/40 split), 300ms slide-out
- [ ] [AI-Test] SVG overlay draw-on: Verify stroke-dasharray animation (200ms per element, sequential)
- [ ] [AI-Test] Reduced motion: Set `prefers-reduced-motion: reduce` → verify instant split + instant overlays
- [ ] [AI-Test] Escape dismiss: Press Escape → verify 200ms ease-out collapse
- [ ] [AI-Test] Auto-resolve: Verify split-screen collapses after 5-8 seconds

---

### Story 5.9: ControlsTray Component — Settings & View Toggle

As a user customizing my experience,
I want all commentary settings in a single accessible tray,
So that I can adjust bias, excitement, knowledge, and language quickly.

**Acceptance Criteria:**

**Given** the ControlsTray component
**When** it renders
**Then** it contains:

| Control | Type | Behavior |
|---------|------|----------|
| Language Toggle | Toggle Button | "EN \| ES" with active language highlighted (Amber 400) |
| Bias Slider | Slider | Team A fan [-1] → Neutral [0] → Team B fan [+1], red-neutral-blue gradient |
| Excitement Slider | Slider | Subdued [0] → Maximum [1], amber gradient |
| Knowledge Depth Slider | Slider | Beginner [0] → Tactical [1], cyan gradient |
| View Toggle | Toggle | Fan Lens \| Commentator Dashboard |

**And** sliders have `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, descriptive `aria-label`
**And** slider changes send WebSocket `{"type": "settings_update", ...}` immediately
**And** no "apply" button — changes apply instantly
**And** preview text updates with setting changes (e.g., bias at +1 shows "Strong Team B perspective")
**And** Tab order: Language → Bias → Excitement → Knowledge → View Toggle
**And** Arrow keys adjust sliders ±10%
**And** Space/Enter toggles buttons

**Given** Community Visitor mode
**When** no mouse movement for 3s
**Then** ControlsTray auto-hides
**When** mouse moves
**Then** ControlsTray reappears

**Given** Narrated Demo mode
**When** active
**Then** ControlsTray is always visible (judge must see features)

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Control rendering: Verify all 5 controls visible (Language, Bias, Excitement, Knowledge, View Toggle)
- [ ] [AI-Test] Slider gradients: Verify red-neutral-blue (Bias), amber (Excitement), cyan (Knowledge)
- [ ] [AI-Test] WebSocket emission: Adjust slider → verify `{"type": "settings_update"}` sent immediately
- [ ] [AI-Test] Auto-hide: Wait 3s idle → verify tray hidden; move mouse → verify reappear
- [ ] [AI-Test] Keyboard navigation: Tab through controls → verify correct order; Arrow keys → verify ±10% adjustment

---

### Story 5.10: TriviaCard Component — Match Insights Display

As a new fan watching football,
I want trivia cards to fade in at key match moments with source attribution,
So that I learn about the match passively without looking away from the action.

**Acceptance Criteria:**

**Given** a trivia-formatted commentary received over WebSocket
**When** MatchInsight component receives the data
**Then** the card renders:
- Anchored bottom-left (8px from edge, max 280px wide)
- Slate 900 at 92% opacity with 3px Amber 400 left border
- Title ("Did you know?") + 1-2 line body (text-sm)
- Source attribution: `StatsBomb · 2023/24 season` (JetBrains Mono, text-xs)

**Given** card animation
**When** entering/Exiting
**Then**:
- Fade in: 400ms ease-out (opacity 0→1, translateY 8px→0)
- Display: 5 seconds
- Fade out: 400ms ease-in
- `prefers-reduced-motion`: instant appear/disappear

**Given** priority queue (max depth 3)
**When** new card arrives
**Then**:
- Goal and Red card bypass queue, immediately dismiss active card (200ms accelerated fade)
- Substitution queued with priority over general trivia
- When queue full, oldest non-priority card dropped
- Minimum 8s gap between consecutive non-priority cards

**Given** card is displayed
**When** active
**Then**:
- `role="status" aria-live="polite"` for screen reader announcement
- Dismiss X button appears on hover
- Card avoids active play zone (ball position tracked by vision model)
- Card never exceeds 5% of screen area

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Card rendering: Verify Slate 900 92% opacity, 3px Amber 400 left border, max 280px wide
- [ ] [AI-Test] Animation timing: Verify fade-in 400ms, 5s display, fade-out 400ms
- [ ] [AI-Test] Priority bypass: Trigger goal event → verify immediate card display (200ms accelerated dismiss of current)
- [ ] [AI-Test] Queue management: Fill queue with 3 cards → verify 4th non-priority card drops oldest
- [ ] [AI-Test] ARIA: Verify `role="status" aria-live="polite"` on card container

---

### Story 5.11: VideoCanvas Component — Connection State & Overlays

As a fan opening PitchAI,
I want the match video to play immediately with AI connection status visible,
So that I'm immersed in the match instantly without waiting for models to load.

**Acceptance Criteria:**

**Given** the VideoCanvas component
**When** page loads
**Then**:
- Video element begins playing within 20 seconds (NFR-3)
- Video is 100% width, 16:9 aspect ratio, centered
- No loading spinner, no "loading model..." message

**Given** canvas overlay synced to video
**When** draw loop runs
**Then**:
- 5 FPS throttled (200ms delta check between frames)
- Dimension guard: skip frame if canvas dimensions don't match video
- API: `drawCircle`, `drawArrow`, `drawLine`, `drawLabel`, `clear`

**Given** WebSocket status dot integrated
**When** connection state changes
**Then**:
- Emerald 500 at 60% opacity = connected
- Amber 500 pulse = reconnecting
- Red 500 = disconnected
- Dot is 6×6px, top-right corner, 12px inset
- After 5s disconnected: "Reconnecting..." text appears

**Given** vision model warming up
**When** status dot renders
**Then**:
- Amber pulse with tooltip: "AI warming up... ready in ~20s"
- Canvas visible but empty
- Video continues playing uninterrupted

**And** `aria-label` updates with state
**And** `role="img"` for canvas with live region for overlay data

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Video playback: Verify video starts within 20s, 16:9 aspect, centered
- [ ] [AI-Test] Connection status dot: Verify 6x6px, top-right 12px inset, color changes with state
- [ ] [AI-Test] Canvas draw loop: Verify 5 FPS throttling (200ms delta check)
- [ ] [AI-Test] Dimension guard: Resize video → verify canvas re-syncs before drawing
- [ ] [AI-Test] Model warming state: Verify Amber pulse + tooltip "AI warming up... ready in ~20s"

---

### Story 5.12: Responsive Layout — Desktop First, Mobile Graceful

As a user accessing PitchAI on different devices,
I want the layout to adapt to my screen size,
So that I can use the product on desktop, tablet, or mobile.

**Acceptance Criteria:**

**Given** desktop viewport (≥ 1440px)
**When** rendering
**Then**:
- Full Fan Lens layout as designed
- Full Commentator Dashboard 60/40 split
- All controls visible

**Given** tablet viewport (1024px - 1439px)
**When** rendering
**Then**:
- Video maintains 16:9, scaled down
- ControlsTray condensed (icons only, tooltips on tap)
- Trivia cards max 240px wide
- Commentator Dashboard: video 100%, teleprompter below (stacked)

**Given** mobile viewport (< 1024px)
**When** rendering
**Then**:
- Video 100% width
- ControlsTray becomes bottom sheet (swipe up)
- Trivia cards full width at bottom
- Commentator Dashboard: video only, teleprompter accessible via "Show Notes" button
- MicButton repositioned to top-right (thumb-friendly)

**And** all touch targets minimum 44×44px (WCAG 2.1 touch target size)
**And** no horizontal scroll at any breakpoint
**And** `prefers-reduced-motion` respected at all breakpoints

**Playwright UI Tests (MCP Server):**
- [ ] [AI-Test] Desktop viewport (1440px): Verify full Fan Lens + Commentator Dashboard layouts
- [ ] [AI-Test] Tablet viewport (1024px): Verify condensed ControlsTray, stacked Commentator layout
- [ ] [AI-Test] Mobile viewport (<1024px): Verify bottom sheet ControlsTray, "Show Notes" button
- [ ] [AI-Test] Touch targets: Verify all interactive elements ≥44×44px at mobile breakpoint
- [ ] [AI-Test] Horizontal scroll: Test all breakpoints → verify no horizontal overflow

---

## Epic 5 Wave Planning

**Wave 1 (Foundation — Week 1):**
- Story 5.1: Design System Foundation
- Story 5.2: Component Library
- Story 5.11: VideoCanvas Component

**Wave 2 (Core Experience — Week 2):**
- Story 5.3: Landing Page
- Story 5.4: Video Page — Fan Lens
- Story 5.5: Video Page — Commentator Dashboard
- Story 5.10: TriviaCard Component

**Wave 3 (Interaction — Week 3):**
- Story 5.6: Teleprompter Component
- Story 5.7: MicButton Component
- Story 5.8: SplitScreen Component
- Story 5.9: ControlsTray Component

**Wave 4 (Polish — Week 4):**
- Story 5.12: Responsive Layout
- Visual regression testing
- Accessibility audit
- Performance optimization

---

## Epic 6: Production Hardening & Deployment Validation

**Status:** backlog  
**Priority:** High  
**Target:** Hackathon Demo Readiness

Epic 6 consolidates all deferred findings, deployment validation, and technical debt from Epics 1-5 into a focused production hardening sprint. This epic ensures PitchAI is deployment-ready and all NFRs are validated with real production metrics.

### Retrospective-Driven Action Items

**From Epic 1 Retrospective:**
- AI-1.1: Document 3-tier confidence gating pattern (apply retroactively to Epic 1)
- AI-1.2: Audit WebSocket message schemas for consistency (gameState inclusion, timestamp format)

**From Epic 2 Retrospective:**
- AI-2.1: Document pre-computed Q&A pair generation process
- AI-2.2: Add calm degradation message for low-confidence player ID
- AI-2.3: Integration test: Q&A end-to-end latency with real STT + LLM

**From Epic 3 Retrospective:**
- AI-3.1: Add localStorage persistence for commentary settings
- AI-3.2: Make teleprompter mode switching more explicit
- AI-3.3: Human review of Spanish translations (native speaker validation)

**From Epic 4 Retrospective:**
- AI-4.2: Create deferred findings tracker (critical vs. nice-to-have) — ✅ Done in technical-debt-tracker.md
- AI-4.3: App-wide accessibility audit — Moved to Epic 5 Wave 4
- AI-4.4: Deploy HF Space and run deployment-dependent validation
- AI-4.5: ✅ Complete (Epic 1-3 retrospectives done)

---

### Story 6.1: HF Space Deployment & Production Validation

As a hackathon judge visiting the PitchAI Space,
I want the demo to work flawlessly within the first 5 minutes,
So that I understand the value proposition and leave a like.

**Acceptance Criteria:**

**Given** the HF Space is deployed via `scripts/deploy_hf.sh`
**When** the Space URL is opened
**Then** video plays within 20 seconds (NFR-3)
**And** vision model attaches within additional 30 seconds
**And** first trivia card fades in within 60 seconds
**And** the Space runs for 5 minutes without crash (SC-09)

**Given** the deployment validation scripts
**When** run against the deployed Space
**Then** memory budgets verified:
- HF Space container < 12GB RAM (NFR-6)
- MI300X VRAM < 60GB (NFR-7)
- KV cache retains ≥ 120 seconds (NFR-8)

**And** latency NFRs pass with real measurements:
- Audio Q&A < 3.5s P95 (NFR-1)
- Language switch < 3s total, < 500ms silence (NFR-2)
- Commentary TTFT < 500ms (NFR-4)
- Vision FPS ≥ 5 on MI300X (NFR-5)

**And** player ID accuracy > 90% on demo video (NFR-11)
**And** chaos tests pass in production:
- 10-event flood → queue managed, no crash
- WebSocket drop mid-Q&A → completes from cache
- Compound failure → single calm message

**And** VALIDATION_REPORT.md is completed with actual production metrics

---

### Story 6.2: Commentary Settings Persistence

As a returning user,
I want my commentary preferences (bias, excitement, knowledge depth, language) to persist across sessions,
So that I don't have to reconfigure them every time I visit.

**Acceptance Criteria:**

**Given** the user adjusts any commentary setting slider
**When** the setting changes
**Then** the value is saved to localStorage immediately
**And** the value persists across page refresh
**And** the value is loaded on app startup

**Given** the user switches commentary language
**When** the toggle is clicked
**Then** the language preference is saved to localStorage
**And** the language is restored on next visit

**Given** localStorage is unavailable (private browsing, disabled)
**When** the app loads
**Then** settings default to neutral/English but don't crash
**And** a subtle indicator suggests enabling localStorage for best experience

---

### Story 6.3: WebSocket Message Schema Audit

As a developer maintaining the WebSocket protocol,
I want all message schemas to be consistent across the codebase,
So that clients can rely on uniform message structure.

**Acceptance Criteria:**

**Given** all WebSocket message types across Epic 1-5
**When** audited for schema consistency
**Then** all messages include:
- `type` field (message type identifier)
- `timestamp` field (ISO8601 format with timezone)
- `gameState` field (where contextually relevant: commentary, trivia, answer)

**And** the following message types are documented:
- `progress` — Agent pipeline progress callbacks
- `notes_ready` — Pre-match notes generation complete
- `commentary` — Live commentary broadcast
- `trivia` — Trivia card data
- `query` — Fan question submitted
- `answer` — Q&A response
- `state_snapshot` — Reconnection state restoration
- `settings_update` — Commentary settings change

**And** a schema document exists at `_bmad-output/websocket-schema.md` with:
- Message type
- Required fields
- Optional fields
- Example payload

---

### Story 6.4: Pre-Computed Q&A Pair Documentation

As a developer extending the Q&A system,
I want to understand how pre-computed Q&A pairs are generated and cached,
So that I can maintain and extend the tap path functionality.

**Acceptance Criteria:**

**Given** the pre-computed Q&A system from Story 2.2
**When** documented
**Then** the document explains:
- When pre-computed pairs are generated (during notes pipeline? on-demand?)
- Where they are stored (in-memory NotesStore? separate cache?)
- How cache invalidation works (new notes → invalidate old Q&A?)
- What the data structure is (question, answer, timestampMs, overlay coordinates)

**And** the document exists at `_bmad-output/docs/precomputed-qa.md` with:
- Architecture diagram
- Data flow description
- Cache key strategy
- Invalidation triggers

---

### Story 6.5: Translation Quality Review (Native Speaker)

As a Spanish-speaking user,
I want the translated commentary to preserve meaning and poetic register,
So that the experience feels authentic, not machine-translated.

**Acceptance Criteria:**

**Given** the Spanish translation templates from Story 3.4
**When** reviewed by a native Spanish speaker
**Then** semantic meaning is preserved exactly
**And** poetic register matches the English original
**And** emotional intensity is equivalent
**And** no cultural stereotype substitutions

**And** a review report exists at `_bmad-output/docs/translation-review-es.md` with:
- Reviewed phrases
- Issues found
- Recommended corrections
- Sign-off from native speaker

---

### Story 6.6: Technical Debt Cleanup — Wave 1 Items

As a developer,
I want to resolve all Critical and High severity deferred findings from Epic 4,
So that the codebase is stable and demo-ready.

**Acceptance Criteria:**

**Given** the technical-debt-tracker.md
**When** reviewing Wave 1 Critical items
**Then** all items marked "Critical" and "High" are resolved:
- 4.2-D4/D5: Accessibility audit (completed in Epic 5 Wave 4)
- 4.3-D1/D2: Confidence badges + graceful degradation (completed in Epic 5)
- 4.4-D1/D2/D4: HF Space deployment validation (Story 6.1)
- 1-D2/6.3: WebSocket schema audit (Story 6.3)
- 2-D3: Q&A integration test (Story 6.1)
- 3-D3: Translation review (Story 6.5)

**And** the tracker is updated with resolution dates and links to PRs
**And** remaining Medium/Low items are scheduled for post-hackathon

---

## Epic 6 Wave Planning

**Wave 1 (Deployment — Before Demo):**
- Story 6.1: HF Space Deployment & Validation
- Story 6.6: Technical Debt Cleanup

**Wave 2 (Documentation — Post-Demo):**
- Story 6.2: Commentary Settings Persistence
- Story 6.3: WebSocket Schema Audit
- Story 6.4: Pre-Computed Q&A Documentation
- Story 6.5: Translation Quality Review