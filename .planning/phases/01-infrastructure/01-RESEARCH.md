# Phase 1: Infrastructure - Research

**Researched:** 2026-03-18
**Domain:** Docker Compose multi-service orchestration — FastAPI + PostgreSQL/pgvector + Next.js 14
**Confidence:** HIGH

## Summary

Phase 1 establishes a fully containerised local development environment with three services — a FastAPI Python backend, a PostgreSQL database with the pgvector extension, and a Next.js 14 frontend. The goal is a single `docker compose up` that starts all services without errors, with a FastAPI health endpoint confirming pgvector is active and secrets never committed to git from the first commit.

The prescribed tech stack is locked in PROJECT.md: FastAPI, PostgreSQL + pgvector, Next.js 14, Tailwind CSS. No alternative stacks should be researched. All three services need working Dockerfiles and a single `docker-compose.yml` at the project root. The PostgreSQL service must run the `CREATE EXTENSION IF NOT EXISTS vector;` SQL on first startup, and FastAPI must not start until the database reports healthy via `pg_isready`.

The two subtlest problems in this phase are (1) ensuring `depends_on` uses `condition: service_healthy` so FastAPI waits for PostgreSQL to actually accept connections — not just be running — and (2) ensuring `.env` is in `.gitignore` before the first `git init` commit so no secrets ever appear in version history. Both are one-time mistakes that are painful to undo.

**Primary recommendation:** Use the official `pgvector/pgvector:0.8.0-pg16` image (not a custom Dockerfile), mount an `init.sql` file with `CREATE EXTENSION IF NOT EXISTS vector;` into `/docker-entrypoint-initdb.d/`, and gate FastAPI startup on `pg_isready` healthcheck.

---

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| `pgvector/pgvector` Docker image | `0.8.0-pg16` or `0.8.0-pg17` | PostgreSQL 16/17 with pgvector pre-installed | Official pgvector project image — no custom Dockerfile needed |
| FastAPI | `0.115+` | Python async web framework | Prescribed in PRD; best async Python API framework |
| Uvicorn | `0.30+` | ASGI server for FastAPI | Standard ASGI runner for FastAPI |
| pydantic-settings | `2.x` | Env var / .env loading for config | Official FastAPI-recommended settings management |
| Next.js | `14.x` | React framework with App Router | Prescribed in PRD |
| Tailwind CSS | `3.x` | Utility-first CSS | Bundled with create-next-app in PRD stack |
| Docker Compose | `v2 CLI (compose v2.x)` | Multi-service orchestration | Standard; `docker compose` not `docker-compose` |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| python-dotenv | (via pydantic-settings) | .env file parsing | Loaded automatically by pydantic-settings |
| SQLAlchemy | `2.x` | ORM for PostgreSQL access | Used later in Phase 2; scaffold in Phase 1 |
| psycopg2-binary | `2.9+` | PostgreSQL driver for Python | Required for SQLAlchemy + PostgreSQL connection |
| WATCHPACK_POLLING | env var (`true`) | Enable Next.js hot reload inside Docker | Required on macOS when running Next.js in a container |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pgvector/pgvector` image | Custom Dockerfile extending `postgres:16` + building pgvector from source | More control, but adds build complexity and maintenance burden — not needed for local dev |
| pydantic-settings | python-decouple, dynaconf | pydantic-settings v2 is the FastAPI-endorsed approach with type safety |
| Uvicorn direct | Gunicorn + Uvicorn workers | Gunicorn makes sense in production — for local dev, single Uvicorn with `--reload` is simpler |

**Backend Python dependencies installation:**
```bash
pip install fastapi uvicorn[standard] pydantic-settings sqlalchemy psycopg2-binary
```

**Frontend scaffold:**
```bash
npx create-next-app@14 frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-git
```

---

## Architecture Patterns

### Recommended Project Structure

This is the PRD-prescribed layout. Phase 1 scaffolds the root skeleton:

```
scholar/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py          # FastAPI app instance, health endpoint
│   │   ├── config.py        # pydantic-settings Settings class
│   │   ├── database.py      # SQLAlchemy engine + session factory
│   │   └── routers/         # Feature routers (empty in Phase 1)
│   └── init_db/
│       └── init.sql         # CREATE EXTENSION IF NOT EXISTS vector;
├── frontend/
│   ├── Dockerfile
│   ├── src/
│   │   └── app/
│   │       ├── layout.tsx
│   │       └── page.tsx
│   ├── tailwind.config.ts
│   └── package.json
├── eval/                    # Empty in Phase 1 (Phase 7 target)
├── .planning/               # Already exists
├── .env                     # GITIGNORED — never committed
├── .env.example             # Committed — documents required vars
├── .gitignore               # Must include .env before first commit
└── docker-compose.yml
```

### Pattern 1: PostgreSQL Healthcheck Gate

**What:** Use `depends_on` with `condition: service_healthy` so FastAPI only starts once PostgreSQL is truly ready to accept connections — not just running.

**When to use:** Anytime a service depends on a database. Without this, FastAPI starts while PostgreSQL is still initialising, causing connection refused errors on startup.

**Example:**
```yaml
# Source: https://docs.docker.com/compose/how-tos/startup-order/
services:
  db:
    image: pgvector/pgvector:0.8.0-pg16
    environment:
      POSTGRES_USER: scholar
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: scholar
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init_db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U scholar -d scholar"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  backend:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://scholar:${POSTGRES_PASSWORD}@db:5432/scholar
    env_file: .env
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Pattern 2: pgvector Extension Auto-Init

**What:** Mount an SQL script into `/docker-entrypoint-initdb.d/` so PostgreSQL automatically creates the `vector` extension on first startup. The `initdb.d` mechanism only runs when the data volume is empty (first run).

**When to use:** Every fresh dev environment setup — no manual psql commands needed.

**Example:**
```sql
-- backend/init_db/init.sql
-- Source: https://github.com/pgvector/pgvector (official README)
CREATE EXTENSION IF NOT EXISTS vector;
```

**Verify it worked:**
```sql
-- Run after container starts:
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
-- Should return: vector | 0.8.0
```

### Pattern 3: FastAPI Health Endpoint with pgvector Verification

**What:** A `/health` endpoint that confirms (1) the app is up and (2) the database connection is live and the `vector` extension is active.

**When to use:** Required by the Phase 1 success criteria. Also used by Docker healthcheck for the `backend` service if needed later.

**Example:**
```python
# Source: FastAPI official docs https://fastapi.tiangolo.com/deployment/docker/
# combined with pg_extension query pattern
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from app.database import get_db

app = FastAPI()

@app.get("/health")
async def health_check():
    try:
        async with get_db() as db:
            result = await db.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="pgvector extension not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    return {"status": "ok", "pgvector": "active"}
```

### Pattern 4: pydantic-settings Config with .env

**What:** Central settings class that reads from environment variables and `.env` file with type validation.

**When to use:** Always — prevents hardcoded config and ensures `.env` values are typed and validated.

**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/settings/
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str
    openai_api_key: str = ""
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Pattern 5: Next.js Docker Dev with Hot Reload

**What:** Docker Compose configuration for Next.js that enables hot module replacement (HMR) inside the container on macOS.

**When to use:** Local development inside Docker on macOS/Windows — file system events don't propagate the same way as Linux.

**Example:**
```yaml
# docker-compose.yml frontend service
  frontend:
    build:
      context: ./frontend
      target: development
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules        # named anonymous volume prevents host override
      - /app/.next               # same for .next build cache
    environment:
      - NODE_ENV=development
      - WATCHPACK_POLLING=true   # Required for file watching in Docker on macOS
    command: npm run dev
```

### Anti-Patterns to Avoid

- **Running `docker-compose` (v1 CLI):** Use `docker compose` (v2, space not hyphen). The old `docker-compose` Python binary is deprecated.
- **Committing `.env` to git:** `.env` must be in `.gitignore` before the first `git init` commit — once a secret is in git history, it requires a full history rewrite.
- **Using `depends_on` without `condition: service_healthy`:** Without `condition: service_healthy`, Docker Compose only waits for the container to be running, not for PostgreSQL to be ready. FastAPI will fail to connect.
- **Not using a named volume for `node_modules` in Next.js Docker:** If you bind-mount `./frontend:/app` without anonymously mounting `/app/node_modules`, the container's `node_modules` gets overridden by the (often empty) host directory.
- **Hardcoding database host as `localhost` in backend config:** Inside Docker Compose, services communicate by service name (e.g., `db`), not `localhost`.
- **Running `initdb.d` scripts on a non-empty volume:** The `docker-entrypoint-initdb.d` scripts only run on first volume init. If the volume already exists (e.g., from a previous run), they are skipped. This is intentional but confusing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PostgreSQL + pgvector install | Custom Dockerfile that builds pgvector from source | `pgvector/pgvector:0.8.0-pg16` official image | Official image is tested, maintained, and avoids build-time failures |
| Service startup ordering | Shell `sleep` loops or custom wait scripts | `depends_on` with `condition: service_healthy` + `pg_isready` | Docker Compose native, no extra dependencies |
| Extension initialization | Manual `psql` commands after first startup | `docker-entrypoint-initdb.d/init.sql` | Runs automatically on first volume init — zero manual steps |
| Environment config | Manual `os.environ.get()` calls | `pydantic-settings BaseSettings` | Type validation, IDE support, `.env` support, lru_cache |
| Next.js hot reload in Docker | Custom file watcher | `WATCHPACK_POLLING=true` env var | Built into webpack/Next.js; one env var fix |

**Key insight:** Docker Compose's health check mechanism plus the official pgvector image handles all the orchestration complexity. The only infrastructure that needs writing from scratch is the project Dockerfiles and the `init.sql` file.

---

## Common Pitfalls

### Pitfall 1: `.env` in Git History

**What goes wrong:** Developer creates `.env`, commits project files with `git add .`, and the `.env` is committed. Even if removed later, the secret exists permanently in git history.

**Why it happens:** `.gitignore` is added after the first commit, or `git add .` is used without checking what's staged.

**How to avoid:** Add `.env` to `.gitignore` in the FIRST commit, before any `.env` file exists. Use `.env.example` (committed) to document required variables.

**Warning signs:** `git status` shows `.env` as a tracked file; `git log --all --full-history -- .env` returns results.

---

### Pitfall 2: FastAPI Starts Before PostgreSQL is Ready

**What goes wrong:** FastAPI container starts (quickly), tries to connect to PostgreSQL (still initialising), fails, and the container crashes or produces confusing errors.

**Why it happens:** `depends_on: db` without `condition: service_healthy` only waits for the container process to start — not for PostgreSQL to be accepting connections.

**How to avoid:** Always use `depends_on: db: condition: service_healthy` paired with a `healthcheck` in the `db` service using `pg_isready`.

**Warning signs:** Backend logs show `connection refused` or `could not connect to server` on startup; restarting the backend manually after a few seconds works fine.

---

### Pitfall 3: pgvector Extension Not Created

**What goes wrong:** The database starts, but `SELECT * FROM pg_extension WHERE extname = 'vector'` returns empty. All vector operations fail with "type vector does not exist".

**Why it happens:** Either (a) the `init.sql` wasn't mounted, (b) the volume already existed from a previous run without the extension, or (c) the SQL file path in the volume mount is wrong.

**How to avoid:** Mount `init.sql` correctly. On a stale environment, run `docker compose down -v` (removes volumes) then `docker compose up` to force re-initialisation.

**Warning signs:** Health endpoint returns pgvector error; `\dx` in psql shows no `vector` extension.

---

### Pitfall 4: Next.js node_modules Overridden by Host

**What goes wrong:** `npm install` runs inside the container correctly, but the `node_modules` directory is empty because the host bind mount overwrites it.

**Why it happens:** Volume mount `./frontend:/app` maps the entire directory including `node_modules`. If the host has no `node_modules`, the container's version is hidden.

**How to avoid:** Add an anonymous volume `/app/node_modules` in Docker Compose to shadow the bind mount specifically for that directory.

**Warning signs:** Container shows "module not found" errors for packages that are in `requirements.txt`/`package.json`; `ls /app/node_modules` inside the container is empty.

---

### Pitfall 5: Using `localhost` as DB Host in Backend

**What goes wrong:** FastAPI cannot connect to PostgreSQL. `DATABASE_URL=postgresql://scholar:pass@localhost:5432/scholar` fails inside Docker Compose.

**Why it happens:** Inside Docker Compose networking, services communicate by service name. `localhost` inside the backend container refers to the backend container itself, not the `db` service.

**How to avoid:** Always use the Compose service name as the host: `DATABASE_URL=postgresql://scholar:${POSTGRES_PASSWORD}@db:5432/scholar`.

**Warning signs:** "could not translate host name 'localhost' to address" or immediate connection refused on any database operation.

---

## Code Examples

Verified patterns from official sources:

### Complete docker-compose.yml Skeleton

```yaml
# Source: https://docs.docker.com/compose/how-tos/startup-order/
# Source: https://hub.docker.com/r/pgvector/pgvector
version: "3.9"

services:
  db:
    image: pgvector/pgvector:0.8.0-pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: scholar
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: scholar
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init_db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U scholar -d scholar"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  backend:
    build:
      context: ./backend
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      DATABASE_URL: postgresql://scholar:${POSTGRES_PASSWORD}@db:5432/scholar
    env_file:
      - .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    environment:
      NODE_ENV: development
      WATCHPACK_POLLING: "true"
      NEXT_PUBLIC_API_URL: http://localhost:8000
    command: npm run dev

volumes:
  postgres_data:
```

### FastAPI Minimal main.py with Health Endpoint

```python
# Source: https://fastapi.tiangolo.com/deployment/docker/
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from app.config import get_settings

app = FastAPI(title="Scholar API")

@app.get("/health")
def health_check():
    settings = get_settings()
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
        pgvector_status = "active" if row else "missing"
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    return {"status": "ok", "pgvector": pgvector_status}
```

### Backend Dockerfile (development)

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### .gitignore Essential Entries

```gitignore
# Secrets — must be present before first commit
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Next.js
frontend/.next/
frontend/node_modules/
frontend/out/

# Docker
.docker/

# OS
.DS_Store
```

### .env.example (committed)

```bash
# .env.example — copy to .env and fill in values
POSTGRES_PASSWORD=changeme
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=ls-...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=scholar
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose` (Python CLI v1) | `docker compose` (Go CLI v2, built into Docker Desktop) | Docker Desktop 3.x+ | Old CLI deprecated; use `docker compose` (space) |
| `wait-for-it.sh` / `dockerize` scripts | `depends_on: condition: service_healthy` + `healthcheck` | Compose v2.1+ | Native healthcheck gate replaces external wait scripts |
| pydantic v1 `BaseSettings` in `pydantic` package | `pydantic-settings` separate package (v2) | pydantic v2 / 2023 | Must `pip install pydantic-settings` separately now |
| `create-next-app --no-git` flag | `create-next-app --disable-git` flag | Next.js 14+ | Flag rename — old `--no-git` may not work |
| pgvector 0.5.x | pgvector 0.8.x (0.8.2 as of 2026) | 2024-2025 | HNSW indexing, improved performance; use 0.8.x |

**Deprecated/outdated:**
- `version: "3.x"` top-level key in docker-compose.yml: Docker Compose v2 ignores this field and may warn; it still works but is optional/obsolete.
- `@app.on_event("startup")` in FastAPI: Deprecated in favor of `lifespan` context manager; for Phase 1 scaffold a basic startup event is fine, but note the deprecation.

---

## Open Questions

1. **Python version pin**
   - What we know: Python 3.12 is the current stable as of 2026
   - What's unclear: Project has no explicit Python version constraint in PRD
   - Recommendation: Use `python:3.12-slim` in the backend Dockerfile; pin it explicitly

2. **PostgreSQL version: pg16 vs pg17**
   - What we know: Both are supported by pgvector 0.8.x; pg16 is the more mature/tested combination
   - What's unclear: No explicit version specified in PRD
   - Recommendation: Use `pgvector/pgvector:0.8.0-pg16` (pg16 is stable LTS-track)

3. **SQLite initialisation approach**
   - What we know: PRD specifies SQLite for LangGraph SqliteSaver checkpointing (Phase 4), not for all data
   - What's unclear: Whether Phase 1 should scaffold SQLite setup or defer to Phase 4
   - Recommendation: Defer SQLite setup to Phase 4 (LangGraph); Phase 1 only needs PostgreSQL

4. **Alembic vs. raw `create_all`**
   - What we know: For Phase 2+ the schema will evolve; Alembic is the standard migration tool
   - What's unclear: Whether to set up Alembic in Phase 1 or Phase 2
   - Recommendation: Scaffold Alembic in Phase 1 (install, init, env.py config) even if no migrations exist yet; avoids retrofitting later

---

## Sources

### Primary (HIGH confidence)
- Docker official docs — https://docs.docker.com/compose/how-tos/startup-order/ — `depends_on` + `condition: service_healthy` pattern
- Docker Hub `pgvector/pgvector` — https://hub.docker.com/r/pgvector/pgvector — official image, version 0.8.x tags confirmed
- GitHub `pgvector/pgvector` — https://github.com/pgvector/pgvector — latest version 0.8.2, Docker install confirmed
- FastAPI official docs — https://fastapi.tiangolo.com/deployment/docker/ — Dockerfile and uvicorn patterns
- FastAPI settings docs — https://fastapi.tiangolo.com/advanced/settings/ — pydantic-settings BaseSettings
- pydantic-settings docs — https://docs.pydantic.dev/latest/concepts/pydantic_settings/ — env_file, SettingsConfigDict
- Next.js official docs — https://nextjs.org/docs/app/api-reference/cli/create-next-app — scaffold flags, project structure

### Secondary (MEDIUM confidence)
- Docker Compose health checks guide — https://last9.io/blog/docker-compose-health-checks/ — verified pg_isready pattern against official docs
- pgvector extension verification — multiple sources agree on `SELECT * FROM pg_extension WHERE extname = 'vector'` pattern
- Next.js Docker hot reload — https://medium.com/@elifront/best-next-js-docker-compose-hot-reload-production-ready-docker-setup-28a9125ba1dc — `WATCHPACK_POLLING=true` pattern verified against multiple sources

### Tertiary (LOW confidence)
- Next.js `--disable-git` flag rename — mentioned in a 2025 search result summary; not verified against official Next.js changelog directly. Recommendation: use `--no-git` first and fall back to `--disable-git` if it errors.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools verified against official images/docs; versions confirmed from Docker Hub and GitHub
- Architecture: HIGH — project structure matches PRD layout; Docker Compose patterns from official docs
- Pitfalls: HIGH — `.env` in git, `depends_on` without healthcheck, and `localhost` vs service name are well-documented, reproducible issues
- pgvector version: MEDIUM — 0.8.2 is the current tag seen on Docker Hub; used 0.8.0 conservatively in examples since 0.8.2 was confirmed 19 days ago and tags differ by minor

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable infrastructure domain; pgvector version tag may update, check Docker Hub before pinning)
