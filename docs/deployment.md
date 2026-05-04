# Deployment

There are two supported deployment methods:

1. **Docker Compose** — recommended for most setups
2. **PM2** — for bare-metal Linux without Docker

---

## Option 1: Docker Compose

### Prerequisites
- Docker Engine 24+
- Docker Compose v2+

### Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd tgl-ai-task-divider-feat-enhance

# 2. Configure backend environment
cp backend/.env.example backend/.env
# Edit backend/.env and set DATABASE_URL, SESSION_SECRET_KEY, GEMINI_API_KEY (or OPENAI_API_KEY)

# 3. Configure frontend environment
cp frontend/.env.example frontend/.env
# Edit frontend/.env and set VITE_API_URL if needed

# 4. Start all services
docker compose up -d

# 5. Run database migrations
docker compose exec api alembic upgrade head

# 6. (Optional) Seed demo data
docker compose exec api python scripts/seed.py
```

### Service Ports

| Service | Internal Port | External Port |
|---|---|---|
| `db` (PostgreSQL 16) | 5432 | 5433 |
| `api` (FastAPI) | 8000 | 8000 |
| `frontend` (React SPA) | 80 | 3000 |

### Useful Docker Commands

```bash
# View logs
docker compose logs -f api
docker compose logs -f frontend

# Restart a service
docker compose restart api

# Stop everything
docker compose down

# Stop and remove volumes (deletes database!)
docker compose down -v

# Rebuild images after code changes
docker compose build
docker compose up -d
```

### `compose.yml` Overview

```yaml
services:
  db:
    image: postgres:16
    ports: ["5433:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: tgl_tasks
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres

  api:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db]
    env_file: backend/.env

  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [api]
    env_file: frontend/.env
```

---

## Option 2: PM2 (Bare-Metal Linux)

This method runs the backend with `uvicorn` and serves the frontend as a static SPA via `serve`, both managed by PM2.

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (running locally or accessible remotely)
- PM2: `npm install -g pm2`

### Setup

```bash
# 1. Install backend dependencies
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure backend environment
cp .env.example .env
# Edit .env

# 3. Run database migrations
alembic upgrade head

# 4. Install frontend dependencies and build
cd ../frontend
npm install
npm run build
# Static files are now in frontend/dist/

# 5. Start both services with PM2
cd ..
pm2 start ecosystem.config.cjs

# 6. Save PM2 process list (survives reboots)
pm2 save
pm2 startup   # follow the printed instructions
```

### PM2 Ports

| Process | Port |
|---|---|
| `tgl-api` | 8003 |
| `tgl-frontend` | 3003 |

### PM2 Commands

```bash
# View status
pm2 status

# View logs
pm2 logs tgl-api
pm2 logs tgl-frontend

# Restart
pm2 restart tgl-api
pm2 restart tgl-frontend

# Stop
pm2 stop all

# Delete all processes
pm2 delete all
```

---

## Reverse Proxy (Nginx / IIS)

In production, place a reverse proxy in front of both services.

### Nginx Example

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Frontend SPA
    location / {
        proxy_pass http://localhost:3000;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE (disable buffering for agent event stream)
    location /api/ai/jobs {
        proxy_pass http://localhost:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding on;
    }
}
```

> **Important:** SSE endpoints (`/api/ai/jobs/{id}/events`) require `proxy_buffering off` to stream events in real-time.

### IIS

A `web.config` is provided in the project root for IIS reverse proxy configuration. The rewrite rules proxy `/api/*` to the FastAPI backend and serve the React SPA for all other paths.

---

## Database Migrations

Always run migrations before starting the application after an update:

```bash
# Docker
docker compose exec api alembic upgrade head

# Bare-metal (with venv activated)
cd backend
alembic upgrade head
```

---

## Production Checklist

- [ ] `SESSION_SECRET_KEY` set to a long, random, unique string
- [ ] `DATABASE_URL` points to a production PostgreSQL instance
- [ ] `CORS_ALLOWED_ORIGINS` set to your actual frontend domain(s)
- [ ] `GEMINI_API_KEY` or `OPENAI_API_KEY` configured
- [ ] Migrations applied (`alembic upgrade head`)
- [ ] HTTPS configured on the reverse proxy
- [ ] SSE proxy buffering disabled for `/api/ai/jobs/*`
- [ ] PM2 startup script configured (bare-metal only)
- [ ] Database backups scheduled
