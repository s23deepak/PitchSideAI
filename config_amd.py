"""
AMD MI300X Production Configuration for PitchAI + StreamingVLM.

Usage:
  Set ENVIRONMENT=production_amd
  Set AMD_DEV_CLOUD=true
  Then start with: python -m uvicorn api.server:app --host 0.0.0.0 --port 8080

This config activates:
  - StreamingVLM full backend (not vLLM fallback)
  - MI300X-optimized settings
  - Production logging and monitoring
"""
import os

# ── Environment ────────────────────────────────────────────────────────────────
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production_amd")
AMD_DEV_CLOUD = os.environ.get("AMD_DEV_CLOUD", "false").lower() == "true"

# ── StreamingVLM Configuration ────────────────────────────────────────────────
STREAMING_BACKEND = "streaming_vlm"  # Use full StreamingVLM backend on MI300X
STREAMING_VLM_MODEL_PATH = os.environ.get(
    "STREAMING_VLM_MODEL_PATH",
    "Qwen/Qwen3-VL-2B-Instruct"
)
STREAMING_WINDOW_SIZE = int(os.environ.get("STREAMING_WINDOW_SIZE", "16"))
STREAMING_CHUNK_DURATION = int(os.environ.get("STREAMING_CHUNK_DURATION", "1"))
STREAMING_TEXT_SINK = int(os.environ.get("STREAMING_TEXT_SINK", "512"))
STREAMING_TEXT_SLIDING_WINDOW = int(os.environ.get("STREAMING_TEXT_SLIDING_WINDOW", "512"))

# ── AMD ROCm Optimizations ───────────────────────────────────────────────────
# MI300X has 192GB HBM3 — use large KV-cache for better streaming
VLLM_GPU_MEMORY_UTILIZATION = float(os.environ.get("VLLM_GPU_MEMORY_UTILIZATION", "0.85"))
VLLM_MAX_MODEL_LEN = int(os.environ.get("VLLM_MAX_MODEL_LEN", "32768"))
VLLM_MAX_NUM_SEQS = int(os.environ.get("VLLM_MAX_NUM_SEQS", "64"))

# MI300X-specific: Enable tensor parallelism across CDNA3 compute units
VLLM_TENSOR_PARALLEL_SIZE = int(os.environ.get("VLLM_TENSOR_PARALLEL_SIZE", "1"))

# ── Model Configuration ───────────────────────────────────────────────────────
LLM_BACKEND = "vllm"
VISION_LLM_BACKEND = "vllm"
COMMENTARY_NOTES_LLM_BACKEND = "vllm"

# For MI300X/RTX 5060, use Qwen3-VL-2B-Instruct
VLLM_VISION_MODEL = os.environ.get(
    "VLLM_VISION_MODEL",
    "Qwen/Qwen3-VL-2B-Instruct"
)
VLLM_MODEL = os.environ.get(
    "VLLM_MODEL",
    "Qwen/Qwen3-VL-2B-Instruct"
)
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8001")

# ── API Server ────────────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", "8080"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info")

# ── Multi-Agent Coordination (Track 1) ────────────────────────────────────────
AGENT_COORDINATOR_ENABLED = True
AGENT_PARALLEL_EXECUTION = True
AGENT_TIMEOUT_SECONDS = 45.0  # Longer timeout for larger model on MI300X

# ── Vision Processing (Track 3) ───────────────────────────────────────────────
# MI300X can handle higher FPS due to 192GB bandwidth
STREAMING_TARGET_FPS = float(os.environ.get("STREAMING_TARGET_FPS", "8.0"))
STREAMING_MAX_CHUNK_FRAMES = int(os.environ.get("STREAMING_MAX_CHUNK_FRAMES", "48"))
STREAMING_CHUNK_INTERVAL = int(os.environ.get("STREAMING_CHUNK_INTERVAL", "5"))

# ── SFT Configuration (Track 2) ───────────────────────────────────────────────
SFT_MODEL_PATH = os.environ.get("SFT_MODEL_PATH", "Qwen/Qwen3-VL-2B-Instruct")
SFT_DATASET_PATH = os.environ.get("SFT_DATASET_PATH", "/mnt/data/sft/commentary_sft.jsonl")
SFT_OUTPUT_DIR = os.environ.get("SFT_OUTPUT_DIR", "/mnt/data/checkpoints/pitchai-qwen3-rocm")
SFT_WINDOW_SIZE = 16
SFT_CHUNK_DURATION = 1
SFT_NUM_EPOCHS = 3
SFT_LEARNING_RATE = 2e-5
SFT_BATCH_SIZE = 1
SFT_GRADIENT_ACCUMULATION = 8