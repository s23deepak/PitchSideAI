# Optional Build in Public Posts

Use these for the AMD extra challenge. Tag lablab.ai and AMD on the platform you choose.

## Post 1

Building PitchSideAI for the AMD Developer Hackathon: a football broadcast companion that turns match footage, team research, and tactical context into live commentary support.

The core workflow is a seven-agent pre-match research pipeline: squad context, player profiles, team form, history, weather, current news, and final narrative beats for commentators.

Tags: @lablab, @AIatAMD

## Post 2

PitchSideAI update: the live demo now connects a Fan Lens match view, tactical vision Q&A, and a commentator dashboard through FastAPI, WebSockets, StreamingVLM, and Qwen/vLLM-compatible model serving.

The AMD path is designed around ROCm and high-memory AMD GPU instances so multimodal football analysis can move closer to real-time broadcast workflows.

Tags: @lablab, @AIatAMD

## Short Technical Walkthrough

PitchSideAI has three loops:

1. Prepare: async agents build structured football notes before kickoff.
2. Watch: the Fan Lens UI keeps video full-screen while surfacing only timely context.
3. Explain: a vision-language path analyzes tactical moments and routes Q&A back into the live session.

The architecture uses React, FastAPI, WebSockets, SSE, StreamingVLM, vLLM-compatible Qwen vision-language serving, and a hardware-aware fallback path for AMD GPU deployment.
