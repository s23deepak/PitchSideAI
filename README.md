# 🏟️ PitchSide AI — Agentic Multimodal Sports Assistant

> **Real-time multimodal sports AI powered by Amazon Nova, OpenAI, Ollama, or vLLM.**

PitchSide AI provides real-time multilingual commentary, tactical vision recognition, and interactive spoken Q&A for live sports broadcasts (Soccer and Cricket). Supports multiple LLM backends for flexible deployment.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

| Feature | Technology |
|---|---|
| 🎙️ **Multilingual Speech Pipeline** | **Nova 2 Sonic** / OpenAI / Ollama |
| 🔬 **Agentic "Commentator's Brief"** | **Nova 2 Pro** + **Bedrock AgentCore** + **OpenSearch** RAG |
| 👁️ **Live Tactical Vision** | **Nova 2 Lite** / GPT-4o / llama3.2-vision multimodal |
| 📋 **Live Event Feed** | **DynamoDB** tracking real-time tactical events |
| 🧠 **Post-Match Masterclass** | **Nova 2 Pro** (long context) for deep tactical reasoning |

---

## 🏗️ Architecture

```
Fan Browser (mic + video) [React Frontend]
      │
      ├─[WebSocket / HTTP]──► FastAPI Backend Server
                                 │
                     ┌───────────┴───────────┐
                     │                       │
             LLM Backend (configurable)    boto3 SDK
              ┌──────┼──────┬──────┐         │
           Bedrock  Ollama OpenAI vLLM   ┌───┴───┐
                                         │       │
                                      DynamoDB OpenSearch
                                      (Events)  (RAG)
```

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
ollama pull gemma2:9b
ollama pull nomic-embed-text
```
```env
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:9b
OLLAMA_EMBED_MODEL=nomic-embed-text
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
VLLM_MODEL=your-model-name
VLLM_EMBED_MODEL=your-embed-model
```

### 3. Run Backend (FastAPI)
```bash
python -m uvicorn api.server:app --reload --port 8080
```

### 4. Run Frontend (React/Vite)
```bash
cd frontend
npm run dev
# → http://localhost:5173
```
