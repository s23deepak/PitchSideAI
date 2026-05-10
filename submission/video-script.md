# PitchSideAI Video Presentation Script

Target length: 4:30 to 5:00. Export as MP4.

## Recording Checklist

- Browser open to the deployed Space.
- Have a sample football clip ready.
- Keep terminal windows closed unless showing deployment is important.
- Use the generated deck PDF for the first 60-75 seconds.
- End with the live app, not the slides.

## Timeline

### 0:00-0:20 - Introduction

"Hi, I am presenting PitchSideAI, a football broadcast companion built for the AMD Developer Hackathon. PitchSideAI helps fans and commentators understand live football faster by combining agent-generated research notes, tactical vision Q&A, and a cinematic Fan Lens viewing mode."

### 0:20-0:55 - Problem

"Live football has too much context moving at once: form, injuries, tactical patterns, player history, weather, and the actual footage. Commentators need useful notes before the moment passes, and fans want answers without leaving the match."

### 0:55-1:25 - Solution

"PitchSideAI creates a real-time companion around the match. Before kickoff, a seven-agent workflow builds structured commentary notes. During the match, vision analysis detects tactical moments and surfaces relevant trivia. Viewers can hold the mic and ask natural questions about the play, the players, or the match context."

### 1:25-2:00 - Technology

"The backend is FastAPI with async agents, WebSockets, and server-sent events. The frontend is React and Vite. The model layer uses StreamingVLM for streaming video understanding and vLLM for Qwen vision-language inference. The deployment path is Docker on Hugging Face Spaces, and the high-performance path is designed for AMD Developer Cloud, ROCm, and AMD Instinct MI300X."

### 2:00-3:40 - Live Demo

Show:

1. Notes Generation Hub: enter two teams and show generated commentary notes or cached output.
2. Fan Lens: show full-screen match video, scoreboard, trivia card, and broadcast controls.
3. Q&A: ask a question such as "What tactical pattern is developing here?" or "Who is the key player in this matchup?"
4. Commentator Dashboard: show the teleprompter and tactical/narrative beats.

Narration:

"This is the preparation flow. Agents collect and synthesize match context into broadcast-ready beats. Now in Fan Lens, the viewer stays inside the match while the AI surfaces context only when it is useful. The same backend feeds a commentator dashboard, so the product works both for fans and production teams."

### 3:40-4:25 - Business Value

"The first audience is football creators and small broadcast teams that need a research desk without hiring one. From there, PitchSideAI can become an engagement layer for clubs, leagues, fantasy communities, and streaming platforms. It creates more watch time, more informed fans, and faster production workflows."

### 4:25-4:55 - Closing

"PitchSideAI is original because it connects agentic research, live video understanding, and broadcast UI into one end-to-end product. With AMD GPUs and ROCm, the expensive multimodal path becomes practical for live sports workloads. Thank you."

## Backup Demo Flow

If the live deployment is cold or a model endpoint is unavailable, use the local validation report and cached demo screens:

- Show `VALIDATION_REPORT.md` for readiness metrics.
- Show `README.md` architecture diagram.
- Show the frontend views with demo data.
- Explain the backend path from StreamingVLM streaming analysis to vLLM frame analysis.
