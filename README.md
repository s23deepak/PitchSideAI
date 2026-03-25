# 🏟️ PitchSide AI — Agentic Multimodal Sports Assistant

> **Real-time multimodal sports AI powered by Amazon Nova and Bedrock.**

PitchSide AI provides real-time multilingual commentary, tactical vision recognition, and interactive spoken Q&A for live sports broadcasts (Soccer and Cricket) using the **Amazon Nova 2** model family.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

| Feature | AWS Technology |
|---|---|
| 🎙️ **Multilingual Speech Pipeline** | **Nova 2 Sonic** preserving original tone and prosody |
| 🔬 **Agentic "Commentator's Brief"** | **Nova 2 Pro** + **Bedrock AgentCore** + **OpenSearch** RAG |
| 👁️ **Live Tactical Vision** | **Nova 2 Lite** multimodal video frame analysis |
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
               AWS Bedrock API            boto3 SDK
               (Converse / AgentCore)        │
                 │   │   │               ┌───┴───┐
     Nova Sonic ─┘   │   └─ Nova Pro     │       │
    (Live Audio)     │     (Research)  DynamoDB OpenSearch
                 Nova Lite             (Events)  (RAG)
                 (Vision)
```

---

## 🚀 Quick Start (Local Dev)

### Prerequisites
- Python 3.11+, Node.js 18+
- AWS Account with Bedrock model access granted for:
  - `amazon.nova-sonic-v2:0`
  - `amazon.nova-lite-v2:0`
  - `amazon.nova-pro-v2:0`
  - `amazon.titan-embed-text-v2:0`

### 1. Install Dependencies
```bash
# Python Backend
pip install -r requirements.txt

# React Frontend
cd frontend
npm install
cd ..
```

### 2. Configure AWS Environment
```bash
cp .env.example .env
```
Edit `.env` to include your AWS credentials and resource names:
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
OPENSEARCH_ENDPOINT=xxx.us-east-1.aoss.amazonaws.com
DYNAMODB_TABLE_NAME=PitchSideEvents
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
