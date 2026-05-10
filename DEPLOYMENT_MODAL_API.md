# Deploy PitchSideAI API to Modal

This deploys the FastAPI backend to Modal. Your UI can stay on Hugging Face Spaces:

```text
UI:  https://s23deepak-pitchsideai.hf.space
API: https://YOUR_MODAL_URL.modal.run
```

The repo includes two Modal entrypoints in `modal_app.py`:

- `fastapi_app`: CPU API wrapper only. Use this when the API calls OpenAI or an external model endpoint.
- `gpu_api_with_vllm`: GPU API stack. This starts vLLM inside the same Modal GPU container and exposes the FastAPI API publicly.

For your full setup, use `gpu_api_with_vllm`.

## 1. Install and Authenticate Modal

From your local machine:

```bash
pip install modal
modal setup
```

## 2. Create the Modal Secret

Create a secret named `pitchside-secrets`.

For an OpenAI-backed CPU API deployment:

```bash
modal secret create pitchside-secrets \
  ALLOWED_ORIGINS='["https://s23deepak-pitchsideai.hf.space"]' \
  LLM_BACKEND=openai \
  VISION_LLM_BACKEND=openai \
  OPENAI_API_KEY='YOUR_OPENAI_KEY'
```

For the full Modal GPU stack that runs both StreamingVLM and vLLM:

```bash
modal secret create pitchside-secrets \
  ALLOWED_ORIGINS='["https://s23deepak-pitchsideai.hf.space"]' \
  LLM_BACKEND=vllm \
  VISION_LLM_BACKEND=vllm \
  STREAMING_BACKEND=auto \
  VLLM_BASE_URL='http://127.0.0.1:8001' \
  AUDIO_VLLM_BASE_URL='http://127.0.0.1:8001' \
  VLLM_MODEL='Qwen/Qwen2.5-VL-3B-Instruct-AWQ' \
  VLLM_VISION_MODEL='Qwen/Qwen2.5-VL-3B-Instruct-AWQ' \
  VISION_MODEL='Qwen/Qwen2.5-VL-3B-Instruct-AWQ' \
  STREAMING_VLM_MODEL='Qwen/Qwen3-VL-4B-Instruct'
```

`STREAMING_BACKEND=auto` means the app tries StreamingVLM first and falls back to vLLM.

If you want to force StreamingVLM:

```bash
modal secret create pitchside-secrets \
  ALLOWED_ORIGINS='["https://s23deepak-pitchsideai.hf.space"]' \
  LLM_BACKEND=vllm \
  VISION_LLM_BACKEND=vllm \
  STREAMING_BACKEND=streaming_vlm \
  VLLM_BASE_URL='http://127.0.0.1:8001' \
  VLLM_MODEL='Qwen/Qwen2.5-VL-3B-Instruct-AWQ' \
  VLLM_VISION_MODEL='Qwen/Qwen2.5-VL-3B-Instruct-AWQ' \
  VISION_MODEL='Qwen/Qwen2.5-VL-3B-Instruct-AWQ' \
  STREAMING_VLM_MODEL='Qwen/Qwen3-VL-4B-Instruct'
```

Add any optional data-source keys the app needs:

```bash
modal secret create pitchside-secrets \
  ALLOWED_ORIGINS='["https://s23deepak-pitchsideai.hf.space"]' \
  LLM_BACKEND=openai \
  VISION_LLM_BACKEND=openai \
  OPENAI_API_KEY='YOUR_OPENAI_KEY' \
  FOOTBALL_DATA_API_KEY='YOUR_KEY' \
  ONEVERSUSONE_API_KEY='YOUR_KEY' \
  FIRECRAWL_API_KEY='YOUR_KEY'
```

## 3. Deploy the API

From the repo root:

```bash
cd /home/deepu/PitchAI
modal deploy modal_app.py
```

Modal will print public URLs for the deployed endpoints. For the GPU stack, use the URL with the `gpu-api` label. It will look similar to:

```text
https://YOUR_WORKSPACE--gpu-api.modal.run
```

That URL is your production API base URL.

## 4. Test the API

Replace the URL with the GPU API URL Modal prints:

```bash
curl https://YOUR_MODAL_URL.modal.run/health
```

Expected result:

```json
{"status":"healthy",...}
```

## 5. Point the Hugging Face UI at Modal

In the Hugging Face Space settings for:

```text
https://huggingface.co/spaces/s23deepak/PitchSideAI
```

set the frontend build variable:

```env
VITE_BACKEND_URL=https://YOUR_WORKSPACE--gpu-api.modal.run
```

Then rebuild the Space.

The live UI should be:

```text
https://s23deepak-pitchsideai.hf.space
```

## 6. Verify Browser Calls

Open the UI and check browser devtools:

```text
HTTP requests should go to https://YOUR_WORKSPACE--gpu-api.modal.run/api/...
WebSockets should go to wss://YOUR_WORKSPACE--gpu-api.modal.run/ws/...
No CORS errors should appear.
```

## 7. Local Development with Modal

To serve the Modal endpoint temporarily during development:

```bash
modal serve modal_app.py
```

Modal will print a temporary dev URL. You can use that as:

```env
VITE_BACKEND_URL=https://YOUR_DEV_MODAL_URL.modal.run
```

## Notes

- Modal currently works well for FastAPI/ASGI hosting and supports WebSockets on ASGI apps. The GPU stack uses `@modal.web_server` because it needs to start vLLM as a subprocess before exposing the API server.
- The GPU stack currently requests one `H100`. Modal lists NVIDIA GPUs, not AMD GPUs. If the deployment must specifically run on AMD/ROCm hardware, use an AMD Droplet or AMD GPU provider instead.
- The backend uses in-memory WebSocket connection state. Modal can run multiple containers, so browser tabs connected to different containers will not share in-memory session state. For demos this is usually fine; for production fan-out across containers, move session/broadcast state to Redis or another shared service.
- Running StreamingVLM and vLLM in one GPU container can be memory-heavy. If the container OOMs, lower `VLLM_GPU_MEMORY_UTILIZATION`, use a smaller vLLM model, or split vLLM and the API/StreamingVLM into separate Modal endpoints.
