# PitchSide AI: Multimodal Agentic Commentary & Tactical Analysis

**PitchSide AI** is an advanced, agentic sports broadcasting platform. By leveraging the **Amazon Nova 2** model family and **AWS Bedrock**, the system provides real-time multi-lingual commentary, autonomous pre-match research, and live multimodal tactical recognition for both Soccer and Cricket.

---

## 🚀 Vision
Sports fans often miss the tactical nuances that professional analysts see. Our goal is to bridge that gap by using **Amazon Nova** to act as a "Digital Assistant Coach" and "Global Commentator," making world-class analysis accessible in any language, in real-time.

## 🛠️ Tech Stack: The Amazon Nova Advantage

We utilize the full spectrum of **Amazon Nova** models via **Amazon Bedrock**:

| Feature | Model | Purpose |
| :--- | :--- | :--- |
| **Real-Time Translation** | `Nova 2 Sonic` | Bidirectional speech-to-speech translation of live commentary (e.g., Peter Drury) with low latency. |
| **Agentic Research** | `Nova 2 Pro` | Autonomous agents that scrape stats, news, and history to build "Match Notes." |
| **Visual Recognition** | `Nova 2 Lite` | Multimodal video analysis to detect player positioning and bowling/fielding changes. |
| **Tactical Deep-Dive** | `Nova 2 Premier` | Long-context reasoning (up to 2M tokens) to analyze full-match dynamics and momentum shifts. |
| **Orchestration** | `Bedrock AgentCore` | Managing tool-use, RAG, and memory for the agentic workflows. |
| **Vector Database** | `Amazon OpenSearch` | Storing the Commentator's Brief with Titan Multimodal Embeddings. |
| **Event Database** | `Amazon DynamoDB` | Fast, scalable storage for live match events and observations. |

---

## 🧠 Key Features

### 1. Global Voice (Nova 2 Sonic)
* **The Problem:** Iconic commentary is often locked to one language.
* **The Solution:** Using **Nova 2 Sonic**, we ingest live English commentary and output natural, emotive speech in Hindi, Spanish, or Portuguese. 
* **Innovation:** We preserve the *cadence* and *excitement* of the original broadcast.

### 2. Autonomous "Commentator’s Brief" (Agentic RAG)
* **The Process:** A **Bedrock Agent** powered by **Nova 2 Pro** automatically researches player form, head-to-head stats, and tactical tendencies.
* **Storage:** These notes are stored in **Amazon OpenSearch Serverless** using Titan Text Embeddings.

### 3. Live Tactical Recognition (Multimodal Vision)
* **Real-time Logic:** The system samples video frames using **Nova 2 Lite**.
* **Contextual Awareness:** If the vision model sees a "High Press" in soccer or a "Leg-side Trap" in cricket, the agent cross-references its "Match Notes" to provide instant commentary: *"The captain is moving a fielder to Square Leg—exactly where this batter has struggled against short-pitched bowling this season."*

### 4. Post-Match "Masterclass"
* **Deep Reasoning:** Using long-context reasoning, the system ingests the metadata of an entire match to identify the exact moment the tactical balance shifted.

### 5. Interactive Audio Q&A for New Fans
* **Voice Interaction:** Users can ask spoken questions while watching, such as "What just happened?" or "Why is that a foul?"
* **Rule Explainer Mode:** The assistant answers in simple language, with sport-specific rule context for beginners.

---

## 🏗️ System Architecture

1.  **Ingestion:** Live video/audio stream + fan voice input from the React dashboard.
2.  **Processing:** 
    * Audio -> **Nova 2 Sonic** via Bedrock ConverseStream.
    * Video -> **Nova 2 Lite** (Multimodal frame analysis via Bedrock Converse).
3.  **Intelligence:** **Bedrock AgentCore** orchestrates tool calls to OpenSearch Serverless (RAG) and DynamoDB (Live Feed).
4.  **Delivery:** A premium React-based dashboard displaying live tactical overlays, a toggleable audio track, and a push-to-talk Q&A assistant.

---

## 🏁 How to Run (Local Dev)

1.  **Prerequisites:**
    * AWS Account with **Amazon Bedrock** access enabled for Nova models.
    * Node 18+ and Python 3.11+
2.  **Installation:**
    ```bash
    git clone https://github.com/your-repo/pitchside-ai
    pip install -r requirements.txt
    cd frontend && npm install && cd ..
    ```
3.  **Environment Setup (`.env`):**
    ```env
    AWS_REGION=us-east-1
    AWS_ACCESS_KEY_ID=your-key
    AWS_SECRET_ACCESS_KEY=your-secret
    OPENSEARCH_ENDPOINT=your-opensearch.amazonaws.com
    DYNAMODB_TABLE_NAME=PitchSideMatchEvents
    ```
4.  **Launch Backend:**
    ```bash
    uvicorn api.server:app --reload --port 8080
    ```
5.  **Launch React Frontend:**
    ```bash
    cd frontend && npm run dev
    ```