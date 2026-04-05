# 🏟️ PitchSide AI — Agentic Multimodal Sports Assistant

> **Real-time multimodal sports AI powered by Amazon Nova, OpenAI, Ollama, or vLLM.**

PitchSide AI provides real-time multilingual commentary, tactical vision recognition, live analyst notes, and interactive spoken Q&A for live sports broadcasts. The current UI centers on commentary-note preparation, a Tactical Brief tab, and live tactical analysis flowing into the commentary feed.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

| Feature | Technology |
|---|---|
| 🎙️ **Multilingual Speech Pipeline** | **Nova 2 Sonic** / OpenAI / Ollama |
| 🔬 **Agentic "Commentator's Brief"** | **Nova 2 Pro** + **Bedrock AgentCore** + **OpenSearch** RAG |
| 👁️ **Live Tactical Vision** | **Nova 2 Lite** / GPT-4o / llama3.2-vision multimodal |
| 🎯 **Tactical Brief + Analyst Notes** | 7-agent notes workflow + `/ws/live` tactical detection broadcasts |
| 📋 **Live Event Feed** | **DynamoDB** tracking real-time tactical events |
| 🧠 **Post-Match Masterclass** | **Nova 2 Pro** (long context) for deep tactical reasoning |

---

## 🏗️ Architecture

```text
Fan Browser (mic + video) [React Frontend]
      │
      ├─[WebSocket / HTTP]──► FastAPI Backend Server
                                 │
                     ┌───────────┼───────────┐
                     │           │           │
             LLM Backend    Data Factory   boto3 SDK
              ┌──────┼       ┌───┼───┐       │
           Bedrock Ollama   ESPN Goal Cric   DynamoDB
```

---

## 📊 Sport-Specific Data Retrievers
PitchSide utilizes a central **DataRetrieverFactory** to dynamically pull statistics from the deepest available domain sources based on the context:
- `CricbuzzRetriever` – Engaged automatically for Cricket context (strike rates, innings)
- `GoalComRetriever` – Engaged automatically for Soccer context (xG, formations)
- `ESPNDataRetriever` – Acts as the robust fallback for Basketball, Hockey, Baseball, and Rugby.

---

## 🔌 LLM Backend Options

Set `LLM_BACKEND` in your `.env` to switch between providers:

| Backend | Use Case | Models | Cost |
|---|---|---|---|
| `bedrock` | Production (default) | Nova Pro/Lite/Sonic, Titan Embed | Pay-per-token |
| `ollama` | Local dev/testing | gemma2:9b, nomic-embed-text | Free |
| `openai` | Cloud alternative | gpt-4o-mini, text-embedding-3-small | Pay-per-token |
| `vllm` | Self-hosted inference | Any HuggingFace model | Self-hosted |

All non-Bedrock backends use the OpenAI-compatible API, so agents are backend-agnostic.

### Recommended Deployment Split

If you want one opinionated setup instead of mixing and matching models:

- Cloud: `LLM_BACKEND=bedrock`
- Self-hosted: `LLM_BACKEND=vllm` with `VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct`
- Lightweight local: `LLM_BACKEND=ollama` with `OLLAMA_MODEL=qwen2.5:3b` and `OLLAMA_VISION_MODEL=qwen2.5vl:3b`

If you want a mixed local setup, the repo also supports routing commentary-note agents to Ollama while keeping all vision analysis on vLLM:

- `COMMENTARY_NOTES_LLM_BACKEND=ollama`
- `VISION_LLM_BACKEND=vllm`
- `OLLAMA_MODEL=qwen2.5:3b`
- `VLLM_BASE_URL=http://localhost:8000`
- `VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-3B-Instruct-AWQ`

That keeps Bedrock as the highest-confidence production path, gives self-hosted deployments a stronger 7B video-capable model, and preserves a low-VRAM 3B local profile for development on smaller machines.

---

## 🚀 Quick Start (Local Dev)

### Prerequisites
- Python 3.11+, Node.js 18+
- **One** of the following LLM backends:
  - AWS Account with Bedrock model access (default)
  - [Ollama](https://ollama.com) installed locally (free, recommended for dev)
  - OpenAI API key
  - vLLM server running

### 1. Install Dependencies
```bash
# Python Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# React Frontend
cd frontend
npm install
cd ..
```

### 2. Configure Environment
```bash
cp .env.example .env
```

**Option A: AWS Bedrock (default)**
```env
LLM_BACKEND=bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
```

**Option B: Ollama (free local)**
```bash
# Install and pull models
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b
ollama pull qwen2.5vl:3b
ollama pull gemma2:9b
ollama pull llama3.2-vision
ollama pull nomic-embed-text
```
```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_VISION_MODEL=qwen2.5vl:3b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

The recommended lightweight local profile uses 3B Qwen models to keep memory requirements down. If you want a stronger local text-only model, you can still swap `OLLAMA_MODEL` back to `gemma2:9b`.

`qwen2.5vl:3b` and `llama3.2-vision` should still be treated as fallback local vision paths in this repo. True clip-level video understanding is available on the Bedrock path and on the vLLM path when the served vision model accepts video input. When a full native clip is too large for the active vLLM context window, the backend now retries the upload as overlapping native-video windows before falling back to sampled-frame analysis.

Ollama still follows the sampled-frame fallback path. For true local clip-level video understanding, use `LLM_BACKEND=vllm` with a video-capable `VLLM_VISION_MODEL`; the backend sends the uploaded clip natively as a `video_url` content block and can break larger clips into overlapping native windows when needed.

If you want local notes on Ollama but video on vLLM, keep `LLM_BACKEND=ollama` and add:

```env
COMMENTARY_NOTES_LLM_BACKEND=ollama
VISION_LLM_BACKEND=vllm
OLLAMA_MODEL=qwen2.5:3b
VLLM_BASE_URL=http://localhost:8000
VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-3B-Instruct-AWQ
NATIVE_VIDEO_WINDOW_SECONDS=3.0
NATIVE_VIDEO_WINDOW_OVERLAP_SECONDS=0.75
NATIVE_VIDEO_MAX_WINDOWS=6
```

**Option C: OpenAI**
```env
LLM_BACKEND=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
```

**Option D: vLLM**
```env
LLM_BACKEND=vllm
VLLM_BASE_URL=http://localhost:8000
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
VLLM_EMBED_MODEL=your-embed-model
```

### 3. Run Backend (FastAPI)
```bash
python3 -m uvicorn api.server:app --reload --port 8080
```

### 4. Run Frontend (React/Vite)
```bash
cd frontend
npm run dev
# → http://localhost:5173
```

### 5. Validate the Tactical Workflow
1. Generate commentary notes for any match.
2. Open the `Tactical Brief` tab in the notes viewer.
3. Upload a frame or short video in TacticalOverlay.
4. On Bedrock or on vLLM with a video-capable `VLLM_VISION_MODEL`, confirm the clip produces timestamped commentary from native video analysis. Larger vLLM uploads now retry as overlapping native-video windows before the backend falls back to the TacticalOverlay sampled-frame payload.
5. Confirm the sidebar shows an `Analyst Note` entry followed by generated `Tactical Commentary`.
6. In Bedrock-backed environments, confirm the DynamoDB event feed updates only for the current match session.
