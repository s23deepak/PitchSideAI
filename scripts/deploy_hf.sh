#!/bin/bash
set -e

# =============================================================================
# PitchAI - Hugging Face Spaces Deployment Script
# =============================================================================
# Usage: HF_SPACE_REPO=username/PitchAI ./deploy_hf.sh
#
# Prerequisites:
#   1. HF Space created at https://huggingface.co/new-space (SDK: Docker)
#   2. Space secret VLLM_BASE_URL configured in Settings → Space secrets
#   3. Git remote 'hf' configured: git remote add hf https://huggingface.co/spaces/$HF_SPACE_REPO
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "🎙️  PitchAI HF Space Deployment"
echo "========================================"

# Validate environment
if [ -z "$HF_SPACE_REPO" ]; then
    echo -e "${RED}Error: HF_SPACE_REPO not set${NC}"
    echo ""
    echo "Usage: HF_SPACE_REPO=username/PitchAI ./deploy_hf.sh"
    echo ""
    echo "Example:"
    echo "  export HF_SPACE_REPO=deepu/PitchAI"
    echo "  ./scripts/deploy_hf.sh"
    exit 1
fi

# Check for HF git remote
if ! git remote | grep -q "^hf$"; then
    echo -e "${YELLOW}⚠️  Git remote 'hf' not found. Setting it up...${NC}"
    git remote add hf "https://huggingface.co/spaces/${HF_SPACE_REPO}"
fi

# Validate VLLM_BASE_URL secret warning
echo ""
echo -e "${YELLOW}⚠️  Ensure VLLM_BASE_URL is configured in HF Space settings:${NC}"
echo "   1. Go to https://huggingface.co/spaces/${HF_SPACE_REPO}/settings"
echo "   2. Add Space secret: VLLM_BASE_URL = http://your-gpu-endpoint:8000"
echo ""

# Confirm before push
read -p "Ready to deploy to https://huggingface.co/spaces/${HF_SPACE_REPO}. Continue? [y/N] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled.${NC}"
    exit 0
fi

# Build verification (optional local test)
echo ""
echo -e "${GREEN}🔨 Building Docker image locally for verification...${NC}"
if command -v docker &> /dev/null; then
    docker build -t pitchai:hf-test . || {
        echo -e "${RED}❌ Docker build failed. Fix errors before deploying.${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ Docker build succeeded${NC}"
else
    echo -e "${YELLOW}⚠️  Docker not found - skipping local build verification${NC}"
fi

# Push to HF Space
echo ""
echo -e "${GREEN}🚀 Deploying to Hugging Face Spaces...${NC}"
git push -f hf main

echo ""
echo -e "${GREEN}✅ Deployment initiated!${NC}"
echo ""
echo "📊 Monitor deployment:"
echo "   https://huggingface.co/spaces/${HF_SPACE_REPO}/logs"
echo ""
echo "🌐 View Space:"
echo "   https://huggingface.co/spaces/${HF_SPACE_REPO}"
echo ""
echo -e "${YELLOW}⏱️  Deployment typically takes 2-5 minutes. Check the logs for progress.${NC}"
