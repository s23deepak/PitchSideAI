#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — PitchSide AI: Automated Cloud Run + Firebase Hosting Deployment
# Usage: ./deploy.sh
# Requirements: gcloud CLI authenticated, firebase CLI installed
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Load project config
source .env 2>/dev/null || true

PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project)}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="pitchside-ai"
IMAGE="gcr.io/${PROJECT}/${SERVICE_NAME}"

echo "🏟️  PitchSide AI — Deploying to Google Cloud"
echo "   Project : ${PROJECT}"
echo "   Region  : ${REGION}"
echo "   Image   : ${IMAGE}"
echo ""

# ── 1. Build & push Docker image ──────────────────────────────────────────────
echo "📦 Building Docker image..."
gcloud builds submit --tag "${IMAGE}" .

# ── 2. Deploy to Cloud Run ────────────────────────────────────────────────────
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION}" \
  --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest" \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5

BACKEND_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --format "value(status.url)")

echo ""
echo "✅ Backend deployed: ${BACKEND_URL}"

# ── 3. Build React Frontend ───────────────────────────────────────────────────
echo ""
echo "⚛️  Building React frontend..."
cd frontend

# Inject backend URL for the frontend
echo "VITE_BACKEND_URL=${BACKEND_URL}" > .env.production

npm install --silent
npm run build --silent

cd ..

# ── 4. Deploy Frontend to Firebase Hosting ────────────────────────────────────
echo "🔥 Deploying to Firebase Hosting..."
firebase deploy --only hosting --project "${PROJECT}"

FRONTEND_URL="https://${PROJECT}.web.app"

echo ""
echo "────────────────────────────────────────────────────────────────────────"
echo "🎉 PitchSide AI is live!"
echo "   Frontend : ${FRONTEND_URL}"
echo "   Backend  : ${BACKEND_URL}"
echo "   Health   : ${BACKEND_URL}/health"
echo "────────────────────────────────────────────────────────────────────────"
