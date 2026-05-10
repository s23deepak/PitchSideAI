"""Modal deployment entrypoint for the PitchSideAI FastAPI backend.

Deploy with:
    modal deploy modal_app.py

Before deploying, create the secret used below:
    modal secret create pitchside-secrets \
      ALLOWED_ORIGINS='["https://s23deepak-pitchsideai.hf.space"]' \
      LLM_BACKEND=openai \
      OPENAI_API_KEY=...
"""

import modal


APP_NAME = "pitchside-api"
SECRET_NAME = "pitchside-secrets"
APP_DIR = "/app"
API_PORT = 8080


app = modal.App(APP_NAME)


image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "build-essential",
        "curl",
        "ffmpeg",
        "git",
        "libgl1",
        "libglib2.0-0",
        "libgomp1",
    )
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("agents", remote_path=f"{APP_DIR}/agents")
    .add_local_dir("api", remote_path=f"{APP_DIR}/api")
    .add_local_dir("config", remote_path=f"{APP_DIR}/config")
    .add_local_dir("core", remote_path=f"{APP_DIR}/core")
    .add_local_dir("data", remote_path=f"{APP_DIR}/data")
    .add_local_dir("data_sources", remote_path=f"{APP_DIR}/data_sources")
    .add_local_dir("models", remote_path=f"{APP_DIR}/models")
    .add_local_dir("orchestration", remote_path=f"{APP_DIR}/orchestration")
    .add_local_dir("rag", remote_path=f"{APP_DIR}/rag")
    .add_local_dir("streaming", remote_path=f"{APP_DIR}/streaming")
    .add_local_dir("tools", remote_path=f"{APP_DIR}/tools")
    .add_local_dir("workflows", remote_path=f"{APP_DIR}/workflows")
    .add_local_file("config.py", remote_path=f"{APP_DIR}/config.py")
    .add_local_file("config_amd.py", remote_path=f"{APP_DIR}/config_amd.py")
)


gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "build-essential",
        "curl",
        "ffmpeg",
        "git",
        "libgl1",
        "libglib2.0-0",
        "libgomp1",
    )
    .pip_install(
        "vllm>=0.8.0",
        "aiohttp>=3.9.0",
        "accelerate>=1.2.0",
        "qwen-vl-utils>=0.0.14",
        "decord>=0.6.0",
        "av>=12.0.0",
    )
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("agents", remote_path=f"{APP_DIR}/agents")
    .add_local_dir("api", remote_path=f"{APP_DIR}/api")
    .add_local_dir("config", remote_path=f"{APP_DIR}/config")
    .add_local_dir("core", remote_path=f"{APP_DIR}/core")
    .add_local_dir("data", remote_path=f"{APP_DIR}/data")
    .add_local_dir("data_sources", remote_path=f"{APP_DIR}/data_sources")
    .add_local_dir("models", remote_path=f"{APP_DIR}/models")
    .add_local_dir("orchestration", remote_path=f"{APP_DIR}/orchestration")
    .add_local_dir("rag", remote_path=f"{APP_DIR}/rag")
    .add_local_dir("streaming", remote_path=f"{APP_DIR}/streaming")
    .add_local_dir("streaming-vlm-qwen3-rocm", remote_path=f"{APP_DIR}/streaming-vlm-qwen3-rocm")
    .add_local_dir("tools", remote_path=f"{APP_DIR}/tools")
    .add_local_dir("workflows", remote_path=f"{APP_DIR}/workflows")
    .add_local_dir("scripts", remote_path=f"{APP_DIR}/scripts")
    .add_local_file("config.py", remote_path=f"{APP_DIR}/config.py")
    .add_local_file("config_amd.py", remote_path=f"{APP_DIR}/config_amd.py")
    .run_commands(f"pip install -e {APP_DIR}/streaming-vlm-qwen3-rocm")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=900,
    scaledown_window=300,
)
@modal.concurrent(max_inputs=20, target_inputs=10)
@modal.asgi_app()
def fastapi_app():
    """Return the existing FastAPI application for Modal's ASGI runner."""
    import os
    import sys

    os.chdir(APP_DIR)
    sys.path.insert(0, APP_DIR)

    from api.server import app as pitchside_fastapi_app

    return pitchside_fastapi_app


@app.function(
    image=gpu_image,
    gpu="H100",
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=24 * 60 * 60,
    startup_timeout=20 * 60,
    scaledown_window=15 * 60,
)
@modal.concurrent(max_inputs=8, target_inputs=4)
@modal.web_server(port=API_PORT, startup_timeout=20 * 60, label="gpu-api")
def gpu_api_with_vllm():
    """Serve FastAPI publicly while vLLM runs inside the same GPU container.

    The public endpoint is the FastAPI app on port 8080.
    vLLM is private to the container on 127.0.0.1:8001.
    StreamingVLM loads in the FastAPI process when STREAMING_BACKEND asks for it.
    """
    import subprocess

    subprocess.Popen(
        ["python", "scripts/modal_start_gpu_stack.py"],
        cwd=APP_DIR,
    )
