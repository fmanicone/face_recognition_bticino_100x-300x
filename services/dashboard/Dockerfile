# ── Stage 1: build frontend ────────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY dashboard/frontend/package*.json ./
RUN npm install --legacy-peer-deps
COPY dashboard/frontend/ ./
RUN npx vite build --outDir /frontend/dist

# ── Stage 2: Python runtime ────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY dashboard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/backend/ ./
COPY --from=frontend /frontend/dist ./static/dist

EXPOSE 5000
CMD ["python", "app.py"]
