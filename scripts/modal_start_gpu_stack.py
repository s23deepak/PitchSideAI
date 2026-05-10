"""Start vLLM and the PitchSideAI API in one Modal GPU container."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from urllib.request import urlopen


APP_DIR = os.getenv("APP_DIR", "/app")
API_PORT = int(os.getenv("API_PORT", "8080"))
VLLM_PORT = int(os.getenv("VLLM_PORT", "8001"))
VLLM_HOST = os.getenv("VLLM_HOST", "127.0.0.1")
VLLM_BIND_HOST = os.getenv("VLLM_BIND_HOST", "127.0.0.1")
VLLM_MODEL = os.getenv("VLLM_MODEL") or os.getenv(
    "VLLM_VISION_MODEL",
    "Qwen/Qwen2.5-VL-3B-Instruct-AWQ",
)


def wait_for_vllm(timeout_seconds: int = 900) -> None:
    deadline = time.time() + timeout_seconds
    url = f"http://{VLLM_HOST}:{VLLM_PORT}/v1/models"

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                if response.status == 200:
                    print(f"vLLM ready at {url}", flush=True)
                    return
        except Exception as exc:
            print(f"Waiting for vLLM: {exc}", flush=True)
            time.sleep(5)

    raise TimeoutError(f"vLLM did not become ready within {timeout_seconds}s")


def start_vllm() -> subprocess.Popen:
    cmd = [
        "vllm",
        "serve",
        VLLM_MODEL,
        "--host",
        VLLM_BIND_HOST,
        "--port",
        str(VLLM_PORT),
        "--trust-remote-code",
        "--gpu-memory-utilization",
        os.getenv("VLLM_GPU_MEMORY_UTILIZATION", "0.45"),
        "--max-model-len",
        os.getenv("VLLM_MAX_MODEL_LEN", "8192"),
        "--served-model-name",
        VLLM_MODEL,
    ]

    quantization = os.getenv("VLLM_QUANTIZATION")
    if quantization:
        cmd.extend(["--quantization", quantization])

    extra_args = os.getenv("VLLM_EXTRA_ARGS")
    if extra_args:
        cmd.extend(extra_args.split())

    print("Starting vLLM:", " ".join(cmd), flush=True)
    return subprocess.Popen(cmd, cwd=APP_DIR)


def start_api() -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("APP_DIR", APP_DIR)
    env.setdefault("VLLM_BASE_URL", f"http://{VLLM_HOST}:{VLLM_PORT}")
    env.setdefault("AUDIO_VLLM_BASE_URL", f"http://{VLLM_HOST}:{VLLM_PORT}")
    env.setdefault("STREAMING_BACKEND", "auto")
    env.setdefault("LLM_BACKEND", "vllm")
    env.setdefault("VISION_LLM_BACKEND", "vllm")
    env.setdefault("VLLM_VISION_MODEL", VLLM_MODEL)
    env.setdefault("VISION_MODEL", VLLM_MODEL)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.server:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(API_PORT),
    ]

    print("Starting API:", " ".join(cmd), flush=True)
    return subprocess.Popen(cmd, cwd=APP_DIR, env=env)


def main() -> None:
    os.chdir(APP_DIR)
    sys.path.insert(0, APP_DIR)

    vllm_proc = start_vllm()
    wait_for_vllm()
    api_proc = start_api()

    while True:
        if vllm_proc.poll() is not None:
            raise RuntimeError(f"vLLM exited with code {vllm_proc.returncode}")
        if api_proc.poll() is not None:
            raise RuntimeError(f"API exited with code {api_proc.returncode}")
        time.sleep(5)


if __name__ == "__main__":
    main()
