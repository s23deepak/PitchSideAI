# Deploy PitchSideAI: Hugging Face UI + AMD Droplet API

This guide deploys the app as two services:

- **Frontend UI:** Dockerized Vite/React app on Hugging Face Spaces
- **Backend API:** FastAPI app on an AMD Droplet, exposed over HTTPS

The browser opens the Hugging Face Space, and the frontend calls the API on the Droplet through `VITE_BACKEND_URL`.

```text
Browser
  |
  | opens
  v
Hugging Face Space UI
  |
  | HTTP / WebSocket calls
  v
https://api.yourdomain.com
  |
  v
AMD Droplet FastAPI backend
```

## 1. Choose URLs

Pick the final URLs before building the frontend.

Example:

```text
Frontend Space URL: https://s23deepak-pitchsideai.hf.space
Backend API URL:   https://api.yourdomain.com
```

The important environment values are:

```env
VITE_BACKEND_URL=https://api.yourdomain.com
ALLOWED_ORIGINS=["https://s23deepak-pitchsideai.hf.space"]
```

`VITE_BACKEND_URL` goes into the frontend build.

`ALLOWED_ORIGINS` goes into the backend API environment.

## 2. Create the Hugging Face Space

Create a new Space at:

```text
https://huggingface.co/new-space
```

Use:

```text
Space SDK: Docker
Space name: PitchSideAI
Visibility: Public or Private
```

The Space URL will look like:

```text
https://s23deepak-pitchsideai.hf.space
```

## 3. Add a Frontend Dockerfile

Create or update a frontend Dockerfile that builds from the repo root and serves the Vite app on port `7860`.

Save this as:

```text
Dockerfile.frontend.hf
```

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/frontend/dist /usr/share/nginx/html

RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
  listen 7860;

  location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
  }
}
EOF

EXPOSE 7860
CMD ["nginx", "-g", "daemon off;"]
```

## 4. Create the Space README

In the files pushed to the Hugging Face Space, include a `README.md` with this frontmatter:

```md
---
title: PitchSideAI UI
emoji: 🎙️
colorFrom: amber
colorTo: slate
sdk: docker
app_port: 7860
---
```

## 5. Deploy the UI to Hugging Face Spaces

Clone the Space repository:

```bash
git clone https://huggingface.co/spaces/s23deepak/PitchSideAI hf-pitchside-ui
cd hf-pitchside-ui
```

Copy the frontend deployment files from this repo into the Space repo:

```bash
cp /home/deepu/PitchAI/Dockerfile.frontend.hf ./Dockerfile
cp /home/deepu/PitchAI/README.md ./README.project.md
```

Create the Space `README.md`:

```bash
cat > README.md <<'EOF'
---
title: PitchSideAI UI
emoji: 🎙️
colorFrom: amber
colorTo: slate
sdk: docker
app_port: 7860
---

# PitchSideAI UI
EOF
```

Copy the frontend source:

```bash
mkdir -p frontend
cp -r /home/deepu/PitchAI/frontend/* ./frontend/
```

Commit and push:

```bash
git add .
git commit -m "Deploy PitchSideAI frontend"
git push
```

## 6. Set the Frontend Build Variable

In the Hugging Face Space settings, add this variable:

```env
VITE_BACKEND_URL=https://api.yourdomain.com
```

If Hugging Face treats it as a runtime variable instead of a Docker build arg, add this near the top of the Dockerfile before `RUN npm run build`:

```dockerfile
ARG VITE_BACKEND_URL=https://api.yourdomain.com
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
```

Then push again so the Space rebuilds.

## 7. Prepare the AMD Droplet

SSH into the Droplet:

```bash
ssh root@YOUR_DROPLET_IP
```

Install dependencies:

```bash
apt update
apt install -y git docker.io docker-compose-plugin nginx certbot python3-certbot-nginx
systemctl enable --now docker
```

Clone the repo:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/PitchAI.git
cd PitchAI
```

Create the backend environment file:

```bash
cp .env.example .env
nano .env
```

At minimum, set:

```env
PORT=8080
LLM_BACKEND=vllm
VISION_LLM_BACKEND=vllm
VLLM_BASE_URL=http://127.0.0.1:8001
VLLM_GPU_MEMORY_UTILIZATION=0.45
ALLOWED_ORIGINS=["https://s23deepak-pitchsideai.hf.space"]
```

Add any provider keys your deployment uses, such as:

```env
OPENAI_API_KEY=...
FOOTBALL_DATA_API_KEY=...
ONEVERSUSONE_API_KEY=...
FIRECRAWL_API_KEY=...
```

## 8. Run the API Container

Build the backend image:

```bash
docker build -f Dockerfile.prod -t pitchside-api .
```

Run it:

```bash
docker run -d \
  --name pitchside-api \
  --restart unless-stopped \
  --env-file .env \
  -p 127.0.0.1:8080:8080 \
  pitchside-api
```

Check health locally:

```bash
curl http://127.0.0.1:8080/health
```

## 9. Configure Nginx for HTTPS

Create an Nginx config:

```bash
nano /etc/nginx/sites-available/pitchside-api
```

Paste:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:

```bash
ln -s /etc/nginx/sites-available/pitchside-api /etc/nginx/sites-enabled/pitchside-api
nginx -t
systemctl reload nginx
```

Point your DNS record:

```text
api.yourdomain.com -> YOUR_DROPLET_IP
```

Create the HTTPS certificate:

```bash
certbot --nginx -d api.yourdomain.com
```

Test the public API:

```bash
curl https://api.yourdomain.com/health
```

## 10. Optional: Run vLLM on the Droplet

If the API uses a local vLLM server, run vLLM on the Droplet separately.

Example:

```bash
vllm serve Qwen/Qwen2.5-VL-3B-Instruct-AWQ \
  --host 127.0.0.1 \
  --port 8001 \
  --trust-remote-code \
  --gpu-memory-utilization 0.45
```

Keep this internal. The browser should call only the FastAPI backend, not vLLM directly. The `0.45` cap leaves the rest of the GPU memory available for StreamingVLM in the API process.

## 11. Verify End to End

Open the frontend:

```text
https://s23deepak-pitchsideai.hf.space
```

Open browser devtools and verify:

```text
API calls go to https://api.yourdomain.com
WebSocket calls go to wss://api.yourdomain.com/ws/...
No CORS errors appear
```

Check backend logs:

```bash
docker logs -f pitchside-api
```

Check Space logs from the Hugging Face Space page:

```text
https://huggingface.co/spaces/s23deepak/PitchSideAI/logs
```

## 12. Updating the Deployment

To update the API:

```bash
cd /root/PitchAI
git pull
docker build -f Dockerfile.prod -t pitchside-api .
docker rm -f pitchside-api
docker run -d \
  --name pitchside-api \
  --restart unless-stopped \
  --env-file .env \
  -p 127.0.0.1:8080:8080 \
  pitchside-api
```

To update the UI:

```bash
cd hf-pitchside-ui
cp -r /home/deepu/PitchAI/frontend/* ./frontend/
cp /home/deepu/PitchAI/Dockerfile.frontend.hf ./Dockerfile
git add .
git commit -m "Update frontend"
git push
```

## Common Issues

### CORS error

Set backend `.env`:

```env
ALLOWED_ORIGINS=["https://s23deepak-pitchsideai.hf.space"]
```

Then restart the API container.

### Frontend still calls localhost

The Vite build did not receive the production backend URL.

Set:

```env
VITE_BACKEND_URL=https://api.yourdomain.com
```

Then rebuild and redeploy the Hugging Face Space.

### WebSocket fails

Make sure Nginx has:

```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

Also make sure the frontend is using HTTPS so WebSockets use `wss://`.

### API works by IP but not domain

Check DNS and certificate:

```bash
dig api.yourdomain.com
certbot certificates
nginx -t
```

### Hugging Face Space starts but shows a blank page

Check that the container listens on `7860`, and the Space README has:

```md
sdk: docker
app_port: 7860
```
