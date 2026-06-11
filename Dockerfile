# ── Stage 1: build React frontend ─────────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime + Node.js (for MCP server) ────────────────────────
FROM python:3.11-slim

# Install Node.js 20 for the GitLab MCP server subprocess
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pin exact version — prevents runtime version drift between builds
RUN npm install -g @zereight/mcp-gitlab@2.1.18

# Frontend build output from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Python source
COPY agent.py api.py worker.py digest.py stale.py score_batch.py ./

ENV PORT=8080
EXPOSE 8080

# Use gunicorn: 1 worker, 8 threads, no timeout (webhook returns 202 instantly)
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 api:app
