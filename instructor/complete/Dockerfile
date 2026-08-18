FROM node:22.16.0-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
RUN npm run check

FROM python:3.14.5-slim-trixie AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app/ ./backend/app/
COPY backend/mcp_server.py ./backend/mcp_server.py
COPY input/day-1/ ./input/day-1/
COPY output/day-2/working-paper.json ./output/day-2/working-paper.json
RUN mkdir -p backend/data && chown -R nobody:nogroup /app

USER nobody
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).read()"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM nginx:1.28.0-alpine AS frontend

COPY --from=frontend-build /app/frontend/dist/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
  CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1/healthz"]
