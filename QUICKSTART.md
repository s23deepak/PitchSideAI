# Quick Start Guide — PitchSide AI v2.0

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (optional)
- AWS Account with Bedrock access

Recommended backend split:
- Cloud: Bedrock
- Self-hosted: vLLM with `Qwen/Qwen2.5-VL-7B-Instruct`
- Lightweight local: Ollama with `qwen2.5:3b` and `qwen2.5vl:3b`
- Mixed local: commentary notes on Ollama with `qwen2.5:3b`, video on vLLM with `Qwen/Qwen2.5-VL-3B-Instruct-AWQ`

### Option 1: Local Development (Fastest)

```bash
# 1. Clone and setup
git clone <repo> && cd PitchAI
cp .env.example .env

# 2. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..

# 3. Configure AWS credentials in .env
# Edit: AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# Optional local/self-hosted profiles:
# - Self-hosted vLLM: set LLM_BACKEND=vllm, VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct,
#   VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
# - Lightweight Ollama: set LLM_BACKEND=ollama, OLLAMA_MODEL=qwen2.5:3b,
#   OLLAMA_VISION_MODEL=qwen2.5vl:3b
# - Mixed local: set COMMENTARY_NOTES_LLM_BACKEND=ollama, VISION_LLM_BACKEND=vllm,
#   OLLAMA_MODEL=qwen2.5:3b, VLLM_BASE_URL=http://localhost:8000,
#   VLLM_VISION_MODEL=Qwen/Qwen2.5-VL-3B-Instruct-AWQ

# 4. Run backend
python3 -m uvicorn api.server:app --reload --port 8080

# 5. Run frontend (new terminal)
cd frontend && npm run dev
```

**Access**: http://localhost:5173

### Tactical Notes Smoke Test
1. Generate commentary notes from the setup banner.
2. Open the `Tactical Brief` tab in the notes panel.
3. Upload a frame or short clip.
4. With `LLM_BACKEND=bedrock`, or with `LLM_BACKEND=vllm` plus a video-capable `VLLM_VISION_MODEL`, the uploaded clip is analyzed as native video. If a full clip exceeds the active vLLM context window, the backend retries it as overlapping native-video windows before falling back to the sampled frames already sent by TacticalOverlay.
5. Check the commentary sidebar for a live `Analyst Note` followed by generated tactical commentary.

### Option 2: Docker Compose (Recommended for Testing)

```bash
# 1. Setup
cp .env.example .env
# Edit .env with AWS credentials

# 2. Run
docker-compose up -d

# 3. Verify
curl http://localhost:8080/health

# 4. Access
# Frontend: http://localhost:5173
# Backend Health: http://localhost:8080/health
# API Status: http://localhost:8080/status
```

### Option 3: Kubernetes (Production)

```bash
# 1. Create namespace
kubectl create namespace pitchside

# 2. Create secrets
kubectl -n pitchside create secret generic pitchside-aws-creds \
  --from-literal=access_key_id=YOUR_KEY \
  --from-literal=secret_access_key=YOUR_SECRET

# 3. Deploy
kubectl apply -f k8s/config.yaml
kubectl apply -f k8s/backend-deployment.yaml

# 4. Monitor
kubectl -n pitchside get pods
kubectl -n pitchside logs -f deployment/pitchside-backend
kubectl -n pitchside port-forward svc/pitchside-backend 8080:80

# 5. Access
curl http://localhost:8080/health
```

---

## 📡 API Quick Test

### Health Check
```bash
curl http://localhost:8080/health
```

### Pre-Match Research
```bash
curl -X POST http://localhost:8080/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{
    "home_team": "Manchester City",
    "away_team": "Liverpool",
    "sport": "soccer"
  }'
```

### Advanced Query
```bash
curl -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is their pressing strategy?",
    "home_team": "Manchester City",
    "away_team": "Liverpool",
    "rag_strategy": "hybrid"
  }'
```

### Get Recent Events
```bash
curl http://localhost:8080/api/v1/events?n=10
```

### Prepare Commentary Notes
```bash
curl -X POST http://localhost:8080/api/v1/commentary/prepare-notes \
  -H "Content-Type: application/json" \
  -d '{
    "home_team": "Manchester United",
    "away_team": "Liverpool",
    "sport": "soccer"
  }'
```

---

## 🔧 Configuration

### Essential Environment Variables

```bash
# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret

# OpenSearch (for RAG)
OPENSEARCH_ENDPOINT=your-endpoint.aoss.amazonaws.com

# Concurrency
MAX_CONCURRENT_TASKS=20  # 1-50 recommended
RATE_LIMIT_RPM=100       # Requests per minute

# Models
RESEARCH_MODEL=amazon.nova-pro-v2:0
VISION_MODEL=amazon.nova-lite-v2:0
LIVE_AUDIO_MODEL=amazon.nova-sonic-v2:0
```

**Full list**: See `.env.example` file

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `PRODUCTION_README.md` | Complete product guide |
| `DEPLOYMENT.md` | Deployment instructions |
| `ARCHITECTURE.md` | Technical architecture |
| `IMPLEMENTATION_SUMMARY.md` | What was built |
| `.env.example` | Configuration reference |

---

## ✅ Verify Installation

After starting, verify everything works:

```bash
# 1. Backend health
curl http://localhost:8080/health
# Expected: {"status": "healthy", ...}

# 2. System status
curl http://localhost:8080/status
# Expected: {"status": "operational", ...}

# 3. Frontend loads
open http://localhost:5173
# Expected: Professional dashboard UI

# 4. Can submit research
curl -X POST http://localhost:8080/api/v1/research \
  -H "Content-Type: application/json" \
  -d '{"home_team":"Test","away_team":"Test","sport":"soccer"}'
# Expected: {"status": "success", ...}
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find what's using port 8080
lsof -i :8080

# Kill it or use different port
python3 -m uvicorn api.server:app --port 9000
```

### AWS Credentials Error
```bash
# Test AWS connectivity
aws sts get-caller-identity

# If fails, check credentials in .env
cat .env | grep AWS
```

### OpenSearch Connection Failed
```bash
# This is OK for development - will use local storage
# Configure OPENSEARCH_ENDPOINT when ready

# Verify in logs - look for:
# "OpenSearch disabled - using local storage"
```

### Docker Issues
```bash
# Clean start
docker-compose down -v
docker-compose up --build

# Check logs
docker-compose logs backend
```

---

## 🚢 Deployment Checklist

Before going to production:

- [ ] AWS credentials in Secrets Manager (not .env)
- [ ] OpenSearch cluster configured
- [ ] DynamoDB table created
- [ ] CORS origins updated
- [ ] Rate limiting adjusted for expected traffic
- [ ] Monitoring/logging configured
- [ ] SSL certificates installed
- [ ] Health checks working
- [ ] Load tests passed
- [ ] Security audit completed

---

## 📊 Performance Info

Expected performance on single instance:
- **Throughput**: 500+ requests/second
- **Latency**: 200-500ms average
- **Max Concurrent Workflows**: 20
- **Max Concurrent Clients**: 100+ (with rate limiting)

---

## 🆘 Need Help?

### Logs
```bash
# Docker Compose
docker-compose logs -f backend

# Kubernetes
kubectl -n pitchside logs -f deployment/pitchside-backend

# Local development
# Check console output
```

### Check Status
```bash
curl http://localhost:8080/status | python -m json.tool
```

### Example Response
```json
{
  "status": "operational",
  "active_workflows": 3,
  "active_tasks": 8,
  "max_concurrent_tasks": 20
}
```

---

## 🎯 Next Steps

1. Run the quick tests above
2. Read `PRODUCTION_README.md` for full features
3. Check `ARCHITECTURE.md` for technical details
4. Deploy to production following `DEPLOYMENT.md`

---

**Happy deploying! 🎉**

For more info, see `PRODUCTION_README.md`
