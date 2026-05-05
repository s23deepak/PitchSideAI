# Multi-stage Docker build for Hugging Face Spaces
# Stage 1: Frontend build
FROM node:20-alpine AS frontend

WORKDIR /app/frontend

# Copy package files first for better caching
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build production bundle
RUN npm run build

# Stage 2: Backend production
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend from Stage 1
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Copy backend directories
COPY agents/ ./agents/
COPY api/ ./api/
COPY config/ ./config/
COPY core/ ./core/
COPY data_sources/ ./data_sources/
COPY models/ ./models/
COPY orchestration/ ./orchestration/
COPY rag/ ./rag/
COPY streaming/ ./streaming/
COPY tools/ ./tools/
COPY workflows/ ./workflows/
COPY config.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check (60s start-period for model warm-up)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run FastAPI server
CMD ["python", "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8080"]
