---
stepsCompleted: ["step-01-init", "step-02-discovery", "step-02b-vision", "step-02c-executive-summary", "step-e-01-discovery", "step-e-02-review", "step-e-03-edit"]
inputDocuments:
  - "_bmad-output/brainstorming/brainstorming-session-2026-05-03.md"
  - ".context/streaming-vlm-research.md"
  - ".context/module_registry.md"
  - ".context/structure.md"
  - ".context/conventions.md"
  - "amd hackathon.md"
  - "lablab_ai-tutorial.md"
workflowType: 'prd'
lastEdited: '2026-05-04'
editHistory:
  - date: '2026-05-04'
    changes: 'Added Success Criteria, Product Scope, User Journeys, Functional Requirements (20 FRs), Non-Functional Requirements (10 NFRs). Content sourced from Party Mode architectural review, brainstorming session, and validation parity check.'
classification:
  projectType: "Proactive AI Broadcast Companion"
  domain: "Sports Broadcasting × Real-Time AI × Interactive Education"
  complexity: "Cascading dependency risk — vision backbone SPOF across all three pillars"
  projectContext: "6-day greenfield hackathon, demo-first, every feature demonstrable in under 90 seconds"
  primaryLens: "Hackathon judge experience (HF Prize + Reachy Mini)"
  dualModeUX: "Ambient intelligence (passive trivia, auto-surfacing notes) + Active (fan Q&A, commentator search — stretch)"
  architectureChain: "SGLang+StreamingVLM → SGLang+Custom KV Window → Pre-computed Embeddings+vLLM → vLLM+Frame-by-Frame"
  failureModes: "GPU SPOF, SGLang+ROCm time-boxed at 1.5 days, HF Space memory ceiling"
  demoProvocation: "Auto-triggered trivia at key moments, pre-seeded suggested questions, visible language toggle prompts"
---

# Product Requirements Document - PitchAI

**Author:** Deepu
**Date:** 2026-05-03
**Last Edited:** 2026-05-04

## Executive Summary

PitchAI is a **Proactive AI Broadcast Companion** that transforms football viewing into an intelligent, personalized experience. Built as a single Hugging Face Space running on one AMD MI300X GPU, it combines real-time vision understanding, multi-agent commentary intelligence, and style-preserving translation into one unified system.

The product serves two audiences simultaneously through one engine:
- **Fans** receive ambient trivia that surfaces at key match moments without prompting, plus the ability to ask questions ("Why is that a red card?") and receive AI-generated explanations with visual overlays on the exact match moment via split-screen temporal navigation.
- **Commentators** receive a narrative-intelligent dashboard where ~5 pages of pre-generated notes highlight in sync with the match — not by timestamp, but by narrative significance. Vision detects the event, agents decide which note matters most.

**Three pillars, one shared vision backbone:**

1. **Commentary Notes Engine** — Before the match, a multi-agent pipeline fetches player data, team form, historical context, and head-to-head records from the internet, scrapes and organizes the raw data, then refines it into ~5 pages of Peter Drury-style narrative notes (50 players, 1v1 matchups, live lineup adjustment). During the match, vision-triggered narrative selection highlights the right note at the right moment — a player's debut, a 300th appearance, a transfer rivalry — like Spotify lyrics for football.

2. **Contextual Stream Q&A** — Fans ask questions grounded in what's happening on screen *right now* via audio input (hold microphone button, speak, release). The screen splits to show the exact match moment with AI-drawn overlays (offside lines, player highlights, movement arrows), explained by the same commentator voice.

3. **Cross-Language Commentary** — Meaning-preserving translation that maps Peter Drury's poetic English to equally poetic Spanish, preserving emotional register rather than defaulting to cultural stereotypes.

### What Makes This Special

The differentiation is **narrative intelligence at the infrastructure level**. Vision doesn't just label frames — it triggers the right story at the right moment. A substitution isn't just "player X on, player Y off." The agent cross-references the player's history and surfaces what matters narratively: debut, milestone, rivalry, redemption arc.

The three pillars converge because they share one vision backbone with a unified KV cache (SGLang RadixAttention). When a fan asks a question, the system already has the relevant frames cached — no additional inference cost for temporal grounding. The translation reads from the same context that drives commentary, preserving meaning across languages without losing the emotional register of the moment.

### Hackathon Context

**Prize Targets:** Hugging Face Special Prize (most likes on Space) + Reachy Mini Wireless.
**Demo Principle:** The product IS the demo. No landing page — the Space URL opens directly into a streaming page with the match already playing. Zero friction between judge and experience.
**5-Minute Narrative Arc:** Minute 0-1: dual-view visible (trivia cards + commentary highlights), commentary playing with pre-set style. Minute 1-3: audio Q&A with split-screen temporal navigation. Minute 3-4: language switch + bias toggle demo. Minute 4-5: notes generation with visible progress + full settings panel.

Technically, the system is architected with a ranked fallback chain to manage ROCm risk: SGLang + StreamingVLM 7B → SGLang + Custom KV Sliding Window → Pre-computed Vision Embeddings + vLLM → vLLM Frame-by-Frame (last resort). The primary bet is time-boxed at 1.5 days with an explicit backup that preserves the demo experience at each degradation level.

## Project Classification

- **Project Type:** Proactive AI Broadcast Companion
- **Domain:** Sports Broadcasting × Real-Time AI × Interactive Education
- **Complexity:** Cascading dependency risk — vision backbone is single point of failure across all three pillars; mixed workload orchestration (real-time prefill + on-demand decode + background batch)
- **Project Context:** 6-day greenfield hackathon build (AMD Hackathon May 4–10, 2026), demo-first, every feature demonstrable live in under 90 seconds
- **Primary Target:** Hackathon judge experience — Hugging Face Special Prize + Reachy Mini Wireless
- **Dual-Mode UX:** Ambient intelligence (passive trivia, auto-surfacing commentary highlights) + Active intelligence (fan Q&A with temporal grounding, commentator note search — stretch)
- **Technical Architecture:** Single MI300X GPU (192GB HBM3), Qwen2.5-VL-7B-AWQ, ranked fallback from SGLang+StreamingVLM to vLLM+frame-by-frame. Docker+React HF Space frontend, GPU inference on separate AMD droplet.
- **Key Risks:** SGLang+ROCm unproven (mitigated by 1.5-day time-box and fallback chain), Hugging Face Space memory ceiling, judge failing to trigger features (mitigated by demo provocation design)

## Success Criteria

The hackathon demo is successful when all of the following are true:

### Demo Flow

- **SC-01:** Judge completes the 5-minute escalating narrative without external intervention — stream loads within 20s, trivia surfaces at match events, Q&A responds within 3.5s, language switch completes within 3s
- **SC-02:** Judge voluntarily interacts with at least one feature (audio Q&A, language toggle, or bias slider) without being prompted — the UI invitations are sufficient
- **SC-03:** All three pillars fire during the demo: notes highlight during a match event, Q&A answers with split-screen temporal navigation, and translation preserves meaning across language switch

### Latency

- **SC-04:** Audio Q&A responds in under 3.5 seconds end-to-end (speech → STT → LLM → text response), measured as P95
- **SC-05:** Language switch completes in under 3 seconds with less than 500ms audio gap
- **SC-06:** Cold start: Space loads and begins playing video within 20 seconds of page open
- **SC-07:** Commentary text generation begins within 500ms of a match event detection (confidence > 0.6)

### Hugging Face Prize

- **SC-08:** Space is publicly accessible, tagged `amd-hackathon-2026`, and includes a self-guided mode with sample video for community visitors
- **SC-09:** Space serves the demo without crashing or exceeding memory limits for the full 5-minute judge session

### Fallback Resilience

- **SC-10:** If StreamingVLM fails on ROCm, the system degrades to the next fallback level within 30 seconds and the demo continues with documented capability loss at each level

## Product Scope

### MVP (6-Day Hackathon)

**In Scope:**
- StreamingVLM + SGLang serving stack on MI300X (primary path)
- Custom KV Sliding Window as first fallback (no external dependencies)
- Audio Q&A via browser Web Speech API (zero server latency)
- Dual-view UI: Fan Lens (5% trivia overlay) + Commentator Dashboard (40% teleprompter)
- Trivia cards triggered by vision detections (confidence > 0.6) matching pre-computed notes
- 7-agent commentary notes pipeline (pre-match generation with progress callbacks)
- Note highlighting synced to match via vision-triggered narrative selection
- Cross-language commentary translation (English → Spanish, meaning-preserving)
- Commentary settings: bias, excitement, knowledge depth (pre-configured for demo)
- Docker + React HF Space frontend, GPU inference on AMD droplet
- Space secrets: VLLM_BASE_URL for endpoint configuration
- Pre-recorded match video with simulated "live" streaming

**Out of Scope (MVP):**
- LiveVLM or StreamMem integration (StreamingVLM only; combining frameworks is a research task)
- Gradio rewrite (React is retained for overlay animations, WebSocket state, split-screen)
- TTS for spoken Q&A answers (text response is sufficient for demo)
- Voice clone for translation
- Actual live broadcast stream ingestion
- Multi-language beyond English/Spanish
- Reachy Mini integration (slide-only for demo)
- Whisper STT fallback (browser Speech API only for MVP)

### Growth (Post-Hackathon)

- Whisper-based STT fallback for browsers without Speech API
- Reachy Mini physical integration (robot arm gestures during commentary)
- Live match stream ingestion (real broadcast input)
- Additional languages (Arabic, French, Portuguese)
- TTS for spoken commentary output
- Commentary notes auto-refresh during match (live data updates)
- Multi-sport support via existing `config/sports.py` infrastructure

### Vision (World Cup 2026)

- Real broadcast integration with production-grade latency
- Full multi-language commentary with voice preservation
- Interactive fan experiences (polling, predictions, social sharing)
- Professional commentator tooling (custom notes, team collaboration)
- Multi-match simultaneous processing
- Production deployment beyond single GPU

## User Journeys

### Persona 1: The New Fan

Maria is watching football for the first time. She's heard about a big match but doesn't understand the rules. She opens the PitchAI Space on her phone.

1. **Match loads** — The stream starts playing immediately. No landing page, no sign-up. Within 3 seconds, a small trivia card fades in at the bottom-left: "Did you know? This is El Clásico — Barcelona vs Real Madrid. They've played each other 254 times."
2. **Passive learning** — As the match progresses, trivia cards surface at key moments. A player gets a yellow card. A card appears: "A yellow card is a warning. Two yellows = sent off." Maria learns without looking away from the action.
3. **Active question** — A controversial tackle happens. The ref shows a red card. Maria holds the microphone button: "Why is that a red card?" She releases. The screen edges darken briefly. The screen splits — left half stays live, right half scrubs back 5 seconds to the tackle, freezes, and draws a red circle around the studs-up contact. The commentator voice explains: "That's a straight red for serious foul play — the studs made contact above the ankle."
4. **Language switch** — Maria's father only speaks Spanish. She taps the language toggle. The commentary mutes for 2 seconds, then resumes in Spanish — same meaning, same excitement, just in español. The trivia card also translates.
5. **Bias toggle** — Maria is secretly rooting for Barcelona. She slides the bias setting toward "Team A." The next time Barcelona scores, the commentary voice lifts with joy. When Madrid scores, the tone is respectful but subdued. Maria grins — the AI is on her side.

### Persona 2: The Professional Commentator

Carlos is preparing to call a Premier League match. He opens the PitchAI Space on his laptop.

1. **Generate notes** — He enters the fixture (Arsenal vs Chelsea), clicks "Generate Commentary Notes." A progress panel appears: "Researching player profiles... ✓ 22/25", "Analyzing team form... ✓", "Building head-to-head history... ✓", "Compiling match narratives..." Each agent's status updates in real time.
2. **Review notes** — The 5-page Peter Drury-style notes appear. Organized across four sections: Match Info + Lineups, Home Team Analysis, Away Team Analysis, Tactical/Historical/Weather. Key stats are bolded. Narrative arcs are pre-written.
3. **Toggle to Commentator Dashboard** — Carlos clicks "🎙️ Commentator View." The screen reflows — match video at 60%, teleprompter at 40%. The notes scroll in sync with the match, highlighting the current narrative beat in gold. The next three lines are visible. Like Spotify lyrics for football commentary.
4. **Vision-triggered highlighting** — A free kick is awarded in a dangerous position. The vision model detects the situation. The dashboard pulses a note about the player's set-piece conversion rate. Carlos didn't have to look it up — it surfaced at the right moment.
5. **Deliver commentary** — Carlos reads from the teleprompter, adding his own flair. The AI-generated lines give him Peter Drury-quality material; his delivery makes it his own.

## Functional Requirements

### Pillar 1: Commentary Notes Engine

**FR-01: Multi-Agent Pipeline Execution**
The system shall execute the 7-agent commentary notes pipeline (PlayerResearch, TeamForm, HistoricalContext, Weather, Matchup, News, NoteOrganizer) in three phases: Phase 1 (parallel — PlayerResearch, TeamForm, Historical, Weather, News), Phase 2 (Matchup — depends on player data), Phase 3 (NoteOrganizer — final synthesis). Each agent shall fetch live data from the internet via the 3-layer fallback chain (StatsBomb → Firecrawl → FBref).

**FR-02: Progress Callbacks**
The system shall emit progress updates as each agent completes, including agent name, status (running/complete/failed), and items processed (e.g., "22/25 players researched"). Progress shall be broadcast over WebSocket for real-time UI rendering.

**FR-03: Dual-View Rendering**
The system shall produce commentary notes in two formats from the same engine: (a) Full Markdown document with narrative arcs, player profiles, tactical previews for the Commentator Dashboard; (b) Individual trivia facts (2-line max) keyed to match event types (goal, card, substitution, free kick) for the Fan Lens overlay.

**FR-04: Vision-Triggered Note Highlighting**
During live streaming, the system shall detect match events via the vision model (confidence > 0.6) and broadcast which pre-generated notes are relevant to the current moment. The Commentator Dashboard shall highlight the current narrative beat and show the next 3 upcoming lines.

**FR-05: Pre-Match Generation**
The system shall support generating commentary notes before the match begins by accepting a fixture (home team, away team, venue, sport) and running the full 7-agent pipeline. Generated notes shall persist for the duration of the WebSocket session.

**FR-06: Player Identification**
The system shall identify players on screen using visual cues (jersey number, position on pitch, movement pattern, build) fused with contextual information (lineup, recent touches). When uncertain, the system shall indicate ambiguity rather than misidentify.

### Pillar 2: Contextual Stream Q&A

**FR-07: Audio Input for Questions**
The system shall accept fan questions via browser Web Speech API (primary) with PushToTalk.jsx + WebSocket binary audio as fallback. The microphone button shall be a floating, semi-transparent element in the bottom-right corner of the video. Hold to record (button turns red), release to submit.

**FR-08: STT Confirmation Display**
Before answering, the system shall display the recognized question text for 1.5 seconds with a dismiss (X) button. If the user dismisses, the question is cancelled and no answer is generated.

**FR-09: Split-Screen Temporal Navigation**
When a question is submitted, the system shall split the screen vertically: left half continues showing the live match, right half scrubs to the most relevant timestamp based on the question's semantic content. The system shall render AI-drawn overlays (circles, arrows, offside lines) on the relevant frame using canvas rendering.

**FR-10: KV Cache Retention for Temporal Context**
The system shall retain a minimum of 120 seconds of visual context in the KV cache to enable temporal navigation for Q&A. When sufficient context is unavailable for a specific question, the system shall answer with available context and indicate the temporal limitation.

**FR-11: Graceful Fallback for Q&A**
When temporal navigation is unavailable (fallback level 3 or 4), the system shall degrade to static contextual answers using pre-computed embeddings or general football knowledge, clearly indicating the degraded mode.

**FR-12: Trivia Card Triggering**
The system shall automatically surface trivia cards in the Fan Lens when a vision detection (confidence > 0.6) matches a pre-computed note. Cards shall fade in over 400ms, display for 5 seconds, and fade out. Cards shall never exceed 2 lines of text and shall not obstruct the match ball or active play area.

**FR-13: Same-Commentator Voice for Answers**
Q&A responses shall use the same commentator voice and style as live commentary. If commentary settings (bias, excitement, knowledge depth) are configured, Q&A responses shall respect those settings.

### Pillar 3: Cross-Language Commentary

**FR-14: Language Toggle**
The system shall provide a visible language toggle button. When activated, the system shall mute commentary audio for a maximum of 3 seconds, then resume commentary in the selected language with preserved meaning and emotional register.

**FR-15: Meaning-Preserving Translation**
Translation shall preserve semantic meaning and poetic register across languages. "Roma have risen from their ruins" shall carry the same historical allusion and dramatic weight in Spanish — not be replaced with culturally-stereotyped excitement patterns.

**FR-16: Trivia Card Translation**
When the commentary language is switched, trivia cards shall also display in the selected language.

### Shared / Platform

**FR-17: Commentary Settings**
The system shall expose three live-configurable commentary settings via sliders: (a) Bias — from Team A fan (-1) through Neutral (0) to Team B fan (+1), affecting emotional tone during goals, cards, and key moments; (b) Excitement — from subdued (0) to maximum (1), affecting vocabulary and energy level; (c) Knowledge Depth — from beginner explanations (0) to tactical deep-dive (1), affecting terminology and detail. Settings shall be sent via WebSocket `{"type": "settings_update"}` and injected into every subsequent commentary prompt.

**FR-18: HF Space Deployment**
The system shall deploy as a Docker container on Hugging Face Spaces with the React frontend served as static files and FastAPI handling WebSocket connections. The GPU inference endpoint URL shall be configurable via a single Space secret (`VLLM_BASE_URL`) without requiring a Space rebuild.

**FR-19: README YAML Frontmatter**
The Space README.md shall include YAML frontmatter with `sdk: docker`, `tags: [amd, amd-hackathon-2026, vllm, gradio]`, and clear setup instructions for Space secrets.

**FR-20: Self-Guided Demo Mode**
The Space shall include a self-guided experience for community visitors who arrive outside the live demo window. This includes a sample match video, pre-generated commentary notes, and a "Try It" button that triggers the full demo flow with pre-seeded settings.

## Non-Functional Requirements

### Latency

**NFR-01: Audio Q&A Response Time**
The system shall respond to audio questions in under 3.5 seconds end-to-end (speech end → STT → LLM → first text token), measured at P95 under single-user load.

**NFR-02: Language Switch Latency**
The system shall complete a language switch in under 3 seconds with less than 500ms of audio silence, measured from toggle click to first word in the new language.

**NFR-03: Cold Start Time**
The HF Space shall load and begin playing video within 20 seconds of page open, with vision model attaching to the stream within an additional 30 seconds (background warm-up).

**NFR-04: Commentary TTFT**
Time-to-first-token for commentary generation following a match event detection (confidence > 0.6) shall be under 500ms.

**NFR-05: Vision Frame Processing**
The system shall process video frames at a minimum of 5 FPS on MI300X for Qwen2.5-VL-7B-AWQ under StreamingVLM, sufficient for real-time match event detection.

### Memory

**NFR-06: HF Space Container Memory**
The HF Space Docker container shall consume under 12GB RAM before model loading (frontend serving + FastAPI + WebSocket connections only). GPU models shall run exclusively on the AMD droplet, not in the Space container.

**NFR-07: MI300X VRAM Budget**
Total GPU memory consumption on MI300X shall not exceed 60GB: Qwen2.5-VL-7B-AWQ (~7-9GB) + KV cache buffer (~20-30GB) + agent LLM context (~5-10GB) + TTS (if used, ~2GB) + framework overhead (~10GB). Remaining 132GB+ headroom available for KV cache expansion.

**NFR-08: KV Cache Temporal Retention**
The system shall retain a minimum of 120 seconds of visual context in the KV cache, supporting temporal navigation for split-screen Q&A.

### Availability & Resilience

**NFR-09: Fallback Chain Activation**
When the primary streaming path (SGLang + StreamingVLM) fails to initialize, the system shall activate the next fallback level within 30 seconds. Each fallback level shall document which capabilities are degraded: Level 2 (custom KV window — loses StreamingVLM optimizations but retains temporal continuity), Level 3 (pre-computed embeddings + vLLM — loses temporal scrub, QA degrades to static context), Level 4 (frame-by-frame — current baseline, no temporal continuity).

**NFR-10: Configuration Agility**
The GPU inference endpoint URL shall be changeable via a single environment variable (`VLLM_BASE_URL`) without requiring a Space rebuild or code change. The system shall reconnect to the new endpoint within 10 seconds of variable change and Space restart.

### Accuracy

**NFR-11: Player Identification Accuracy**
Player identification shall exceed 90% accuracy on known players in the demo video under normal camera angles and lighting conditions. Misidentifications shall be indicated with uncertainty qualifiers in commentary output.

### Deployment

**NFR-12: Single Command Deployment**
The Space shall be deployable with a single `git push` to the HF Space repository. No manual SSH, no droplet-side configuration beyond the initial vLLM/SGLang endpoint startup.