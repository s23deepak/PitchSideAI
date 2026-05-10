# lablab.ai Submission Content

## Project Title

PitchSideAI - Football Broadcast Companion

## Short Description

Real-time football intelligence for fans and broadcast teams, powered by agentic match research, tactical vision Q&A, and AMD-ready ROCm/vLLM infrastructure.

## Long Description

PitchSideAI is an AI broadcast companion for football fans, commentators, and sports media teams. The product solves a common live-sports problem: audiences and commentators are flooded with match footage, stats, news, tactical context, and player history, but the most useful insight rarely arrives at the exact moment it matters. PitchSideAI turns that fragmented context into an interactive match companion. Before a match, a seven-agent research workflow gathers squad information, form, head-to-head history, player profiles, weather context, and current news, then synthesizes the results into structured commentary notes and narrative beats. During a match, the Fan Lens interface combines full-screen video, scoreboard state, automatically surfaced trivia, tactical overlays, and hold-to-ask Q&A. The vision path is designed for AMD GPU deployment with ROCm, StreamingVLM, vLLM-compatible Qwen vision-language model serving, and a fallback path that keeps the demo usable across hardware tiers. The result is a practical, end-to-end AI agent workflow that helps fans understand the game faster and gives commentators production-ready context without breaking the flow of live coverage.

## Technology and Category Tags

- AMD Developer Cloud
- ROCm
- AMD Instinct MI300X
- AI Agents
- Agentic Workflows
- Vision and Multimodal AI
- Qwen
- vLLM
- Hugging Face Spaces
- FastAPI
- React
- Vite
- WebSocket
- Sports Tech
- Football
- Real-Time AI

## Hackathon Track

Primary: AI Agents and Agentic Workflows

Secondary: Vision and Multimodal AI

## Demo Application Platform

Hugging Face Spaces using Docker SDK.

## Application URL

https://huggingface.co/spaces/deepu/PitchSideAI

If Hugging Face exposes the direct app endpoint, submit that direct endpoint as the application URL as well.

## Public GitHub Repository

https://github.com/s23deepak/PitchSideAI

## Cover Image

Upload `submission/cover.png`.

## Video Presentation

Record using `submission/video-script.md`. Export MP4, maximum 5 minutes.

## Slide Presentation

Upload `submission/pitchsideai-deck.pdf`.

## Product Summary for Judges

PitchSideAI is a working multimodal sports AI app with three connected experiences: a Fan Lens broadcast view for viewers, a commentator dashboard for live production, and a notes hub for pre-match preparation. It uses agentic research workflows, live game state, WebSocket updates, tactical vision analysis, and Qwen/vLLM-compatible model serving. The AMD relevance is strongest in the vision and serving layer: the architecture is prepared for ROCm and AMD Instinct MI300X deployment while preserving a practical fallback path for demos.

## Business Value

Sports creators, streamers, broadcasters, fantasy communities, and clubs all need faster ways to turn match data into timely analysis. PitchSideAI can be offered as a SaaS tool for small broadcast teams, a fan engagement layer for clubs and leagues, or an embedded companion for sports streaming platforms. The first commercial wedge is football creator tooling: generate pre-match notes, live tactical prompts, and viewer Q&A without a full research desk.

## Differentiation

Most sports AI demos are either static stat search tools or generic chatbots. PitchSideAI combines pre-match agent research, in-match multimodal perception, live game state, and broadcast-specific UI. The system is designed around actual match workflows: prepare, watch, detect, narrate, ask, and answer.

## AMD / Qwen Highlight

PitchSideAI is built to run video understanding through StreamingVLM and Qwen vision-language inference through vLLM on ROCm-capable AMD GPU infrastructure. The streaming fallback path lets the app target high-memory AMD Instinct instances while still supporting smaller demo environments.
