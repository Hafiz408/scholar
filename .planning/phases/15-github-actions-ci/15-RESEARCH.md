# Phase 15: GitHub Actions CI - Research

**Researched:** 2026-03-22
**Domain:** GitHub Actions, pytest, ruff, pgvector service containers
**Confidence:** HIGH

## Summary

Phase 15 creates `.github/workflows/ci.yml` to run pytest and ruff on every PR targeting `feature/v2` and `main`. The project uses Python 3.12 (per Dockerfile), pytest with asyncio_mode=auto (per pytest.ini), and connects to PostgreSQL+pgvector for vector storage. Most tests are fully mocked (unit tests) — `test_api_integration.py` uses aiosqlite (SQLite) not PostgreSQL, so it does NOT require a real PG service container. PostgreSQL is only needed for tests that call `init_pgvector_schema()` or `psycopg2.connect()` at runtime, which in CI means the `app` startup path.

The critical exclusion is `test_router_accuracy_gate.py` (inside `test_router.py`, marked `@pytest.mark.integration`). The cleanest way to exclude it is `--ignore=tests/test_router.py` OR using `-m "not integration"` since `conftest.py` already registers the `integration` marker. The `-m "not integration"` approach is preferable: it excludes only the `test_router_accuracy_gate` function while still running `test_retr02_fallback_*` tests in that same file.

The Dockerfile clones `pgvector/PageIndex` from GitHub and puts it on `PYTHONPATH`. CI must replicate this — either by running the same git clone step or by running tests inside the backend Docker image. Running tests natively on the GitHub runner (not in a container) is simpler and matches how local dev works: clone PageIndex, set `PYTHONPATH`, run pytest. The pgvector/pgvector Docker image should be used as a service container so the `init_pgvector_schema()` lifespan call succeeds during `test_api_integration.py`.

**Primary recommendation:** Use a single job with `runs-on: ubuntu-latest`, a `pgvector/pgvector:pg16` service container, git-clone PageIndex to set PYTHONPATH, install `requirements.txt`, run `ruff check backend/` then `pytest backend/tests/ -m "not integration"`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CI-01 | `.github/workflows/ci.yml` runs pytest + ruff on PRs to `feature/v2` and `main` | GitHub Actions `on.pull_request.branches` trigger; `astral-sh/ruff-action@v3` for ruff; `pytest` run via pip install |
| CI-02 | `test_router_accuracy_gate.py` excluded from CI (requires live LLM) | Use `-m "not integration"` — the gate test is already marked `@pytest.mark.integration` in `test_router.py`; `conftest.py` already registers the marker |
| CI-03 | CI uses PostgreSQL service container for integration tests | `pgvector/pgvector:pg16` (matches docker-compose.yml) as a `services:` block; job runs on runner (not in container) so port 5432 is exposed to localhost; `DATABASE_URL` env var set to `postgresql://scholar:scholar@localhost:5432/scholar` |
</phase_requirements>

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| `actions/checkout` | v4 | Checkout source code | GitHub-maintained standard action |
| `actions/setup-python` | v5 | Install Python runtime | GitHub-maintained standard action |
| `astral-sh/ruff-action` | v3 | Run ruff linter | Official ruff action from maintainer (Astral) |
| `pgvector/pgvector` image | pg16 | PostgreSQL with vector extension | Matches docker-compose.yml image |
| `pytest` | 8.3.0 (from requirements.txt) | Test runner | Already in project requirements |
| `ruff` | latest (via ruff-action) | Linter | CI-01 specifies ruff |

### Configuration Files Already in Project
| File | Relevance |
|------|-----------|
| `backend/pytest.ini` | `asyncio_mode = auto`, `pythonpath = .` — CI must `cd backend/` before pytest OR pass `--rootdir` |
| `backend/requirements.txt` | Contains pytest==8.3.0, pytest-asyncio==0.23.0 — all CI needs |
| `backend/tests/conftest.py` | Registers `integration` marker — `-m "not integration"` works out of the box |

### Installation
```bash
pip install -r backend/requirements.txt
```

No separate ruff install needed — `astral-sh/ruff-action@v3` installs it automatically.

## Architecture Patterns

### Recommended Workflow Structure

```
.github/
└── workflows/
    └── ci.yml
```

### Pattern 1: Single Job, Runner-Level (not container-level)

**What:** Tests run directly on `ubuntu-latest` runner. PostgreSQL runs as a service container. PageIndex is cloned to runner filesystem.

**When to use:** Simpler than running the whole job inside a Docker container. Avoids Docker-in-Docker complications. Port mapping (`5432:5432`) exposes PG to `localhost`.

**Why not run the job inside the backend Docker image:** Would require building the image first (slow, complex). Running natively is faster and identical to local dev.

**Example:**
```yaml
# Source: https://docs.github.com/en/actions/use-cases-and-examples/using-containerized-services/creating-postgresql-service-containers
on:
  pull_request:
    branches: [feature/v2, main]

jobs:
  ci:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: scholar
          POSTGRES_PASSWORD: scholar
          POSTGRES_DB: scholar
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    env:
      DATABASE_URL: postgresql://scholar:scholar@localhost:5432/scholar
      PYTHONPATH: /opt/pageindex

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Clone PageIndex
        run: git clone --depth=1 https://github.com/VectifyAI/PageIndex.git /opt/pageindex

      - name: Install dependencies
        run: pip install -r backend/requirements.txt

      - uses: astral-sh/ruff-action@v3
        with:
          src: "./backend"

      - name: Run pytest
        run: pytest backend/tests/ -m "not integration"
        env:
          DATABASE_URL: postgresql://scholar:scholar@localhost:5432/scholar
```

### Pattern 2: Excluding the Live LLM Test

**What:** Use pytest marker filtering, not file ignoring.

**Why `-m "not integration"` over `--ignore=tests/test_router.py`:** The file `test_router.py` contains two mocked tests (`test_retr02_fallback_*`) that do NOT require a live LLM — only `test_router_accuracy_gate` uses `@pytest.mark.integration`. Ignoring the whole file would lose those tests.

**Confirmed:** `conftest.py` already has:
```python
config.addinivalue_line("markers", "integration: marks tests as integration tests (require live APIs)")
```

And `test_router_accuracy_gate` has:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_router_accuracy_gate():
```

So `-m "not integration"` is safe and correct.

### Pattern 3: PostgreSQL Init for pgvector

**What:** `init_pgvector_schema()` calls `psycopg2.connect(settings.database_url)` at FastAPI lifespan. The `test_api_integration.py` uses `TestClient(app)` which triggers the lifespan, which calls `init_pgvector_schema()`. This requires a live PostgreSQL connection.

**The `pgvector/pgvector:pg16` image** has the `vector` extension already compiled — you still need to `CREATE EXTENSION IF NOT EXISTS vector;` in the database. This is done by `backend/init_db/init.sql` in docker-compose but NOT automatically by the pgvector Docker image in service containers.

**Solution:** Either:
1. Add a CI setup step that runs `psql ... -c "CREATE EXTENSION IF NOT EXISTS vector;"` after the PG service is ready, OR
2. Confirm that `init_pgvector_schema()` in `database.py` already runs `CREATE EXTENSION IF NOT EXISTS vector` itself.

Read `backend/app/db/database.py` `init_pgvector_schema()` carefully — if it contains `CREATE EXTENSION IF NOT EXISTS vector`, the SQL file is not needed. If it does not, CI needs an explicit psql step.

### Anti-Patterns to Avoid

- **Running the job inside a Docker container (`container:` key):** Makes port routing to services more complex (use service name as hostname, not `localhost`). Not needed here since tests run natively on the runner.
- **Using `--ignore=tests/test_router.py`:** Throws away two valid mocked tests in that file.
- **Forgetting PYTHONPATH for PageIndex:** The app imports PageIndex at module level; without `/opt/pageindex` on PYTHONPATH, all imports fail immediately.
- **Using `postgres:latest` image:** Must use `pgvector/pgvector:pg16` to match docker-compose.yml and have the vector extension available.
- **Pinning `POSTGRES_PASSWORD` as a secret for CI:** For CI, a hardcoded dummy password is fine since this is a disposable test container.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ruff invocation | Shell `pip install ruff && ruff check` manually | `astral-sh/ruff-action@v3` | Official action handles version pinning, output formatting, GitHub annotations |
| Python setup | Manual apt-get python | `actions/setup-python@v5` | Manages PATH, pip, multiple Python versions cleanly |
| pgvector setup | Building a custom Docker image | `pgvector/pgvector:pg16` service container | Pre-built image with extension already compiled |

**Key insight:** The GitHub Actions marketplace has first-party actions for every step here. Use them to get GitHub PR annotations (inline lint errors) for free.

## Common Pitfalls

### Pitfall 1: PYTHONPATH Not Set for PageIndex
**What goes wrong:** `ModuleNotFoundError` on every test since `PageIndex` is cloned to `/opt/pageindex` in Dockerfile but not installed as a package.
**Why it happens:** `PYTHONPATH` env var only exists in the Docker container runtime, not in CI runner.
**How to avoid:** Add `PYTHONPATH: /opt/pageindex` as a job-level `env:` AND include a `git clone --depth=1 https://github.com/VectifyAI/PageIndex.git /opt/pageindex` step before installing requirements.
**Warning signs:** All pytest tests fail with `ImportError` immediately.

### Pitfall 2: pgvector Extension Not Created
**What goes wrong:** `init_pgvector_schema()` or `health_check()` fails with `psycopg2.errors.UndefinedObject: extension "vector" does not exist`.
**Why it happens:** `pgvector/pgvector` Docker image has the extension *compiled* but `CREATE EXTENSION` must still be run in the database. `init.sql` does this in docker-compose but the service container does not auto-run init scripts.
**How to avoid:** Add a psql step to create the extension, OR verify `init_pgvector_schema()` already runs `CREATE EXTENSION IF NOT EXISTS vector`. Check `backend/app/db/database.py` line ~113.
**Warning signs:** FastAPI lifespan fails on startup during TestClient creation in `test_api_integration.py`.

### Pitfall 3: Working Directory Mismatch with pytest.ini
**What goes wrong:** `pytest` run from repo root doesn't find `pytest.ini` settings; `pythonpath = .` resolves to repo root, not `backend/`, so `from app.xxx import` fails.
**Why it happens:** `pytest.ini` is in `backend/`, not the repo root.
**How to avoid:** Run pytest as `pytest backend/tests/` with `--rootdir=backend` OR `cd backend && pytest tests/`. The recommended form: `pytest backend/tests/ --rootdir=backend`.
**Warning signs:** `ModuleNotFoundError: No module named 'app'` during test collection.

### Pitfall 4: SQLite Path Collision Across Tests
**What goes wrong:** `test_api_integration.py` uses `settings.sqlite_path` (`./data/scholar.db`) which defaults to a relative path. In CI this creates a file at `./data/scholar.db` relative to whatever cwd pytest runs from.
**Why it happens:** The path is not overridden in CI and the `data/` directory may not exist.
**How to avoid:** Set `SQLITE_PATH=/tmp/scholar_ci.db` in the CI job env, or ensure `mkdir -p backend/data` before running tests.
**Warning signs:** `aiosqlite.OperationalError: unable to open database file` on first test.

### Pitfall 5: Service Container Not Ready When Tests Start
**What goes wrong:** psycopg2 connection errors in the first test because PostgreSQL hasn't finished starting.
**Why it happens:** GitHub Actions starts service containers in parallel with steps; without health checks, the service may not be ready.
**How to avoid:** The `options: --health-cmd pg_isready ...` block in the service definition makes GitHub Actions wait until the healthcheck passes before executing steps.
**Warning signs:** `psycopg2.OperationalError: could not connect to server` flakily on first runs.

## Code Examples

### Complete ci.yml (annotated)
```yaml
# Source: GitHub Actions official docs + pgvector/setup-pgvector README
name: CI

on:
  pull_request:
    branches:
      - feature/v2
      - main

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: scholar
          POSTGRES_PASSWORD: scholar
          POSTGRES_DB: scholar
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Clone PageIndex
        run: git clone --depth=1 https://github.com/VectifyAI/PageIndex.git /opt/pageindex

      - name: Install Python dependencies
        run: pip install -r backend/requirements.txt

      - name: Lint with ruff
        uses: astral-sh/ruff-action@v3
        with:
          src: "./backend"

      - name: Run tests (excluding live-LLM gate)
        working-directory: backend
        run: pytest tests/ -m "not integration"
        env:
          DATABASE_URL: postgresql://scholar:scholar@localhost:5432/scholar
          PYTHONPATH: /opt/pageindex
          SQLITE_PATH: /tmp/scholar_ci.db
```

### Confirming the integration marker exclusion
```bash
# These pass (mocked, no LLM):
# test_router.py::test_retr02_fallback_no_pageindex_docs
# test_router.py::test_retr02_fallback_empty_source_ids

# This is skipped by -m "not integration":
# test_router.py::test_router_accuracy_gate  [marked @pytest.mark.integration]
```

### psql step if CREATE EXTENSION is needed
```yaml
- name: Enable pgvector extension
  run: psql postgresql://scholar:scholar@localhost:5432/scholar -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| flake8 + isort + pylint separate | ruff (all-in-one) | ~2023 | Single tool replaces 3; dramatically faster |
| `actions/checkout@v2` | `actions/checkout@v4` | 2023 | v4 is current, uses Node 20 |
| `actions/setup-python@v4` | `actions/setup-python@v5` | 2024 | v5 is current |
| `astral-sh/ruff-action@v1` | `astral-sh/ruff-action@v3` | 2024 | v3 is current stable |

## Open Questions

1. **Does `init_pgvector_schema()` run `CREATE EXTENSION IF NOT EXISTS vector`?**
   - What we know: `init_pgvector_schema()` is in `backend/app/db/database.py` around line 113; it calls `psycopg2.connect` and `cur.execute(_pgvector_schema(...))`.
   - What's unclear: Whether `_pgvector_schema()` includes `CREATE EXTENSION IF NOT EXISTS vector` before the table DDL.
   - Recommendation: Read `database.py` lines 50-130 in the plan phase to confirm. If it does NOT include the extension creation, add a psql step to the workflow. This is a critical path blocker.

2. **Does `test_api_integration.py` actually require PostgreSQL, or is it fully on SQLite?**
   - What we know: The test file connects to `aiosqlite` via `settings.sqlite_path` for all data operations. But `TestClient(app)` triggers `lifespan` which calls `init_pgvector_schema()` which calls `psycopg2.connect(settings.database_url)` (PostgreSQL).
   - What's unclear: Will `init_pgvector_schema()` fail the lifespan if PostgreSQL is unavailable?
   - Recommendation: The PostgreSQL service container IS required in CI for `test_api_integration.py` to pass. All other test files mock at the function level and avoid the lifespan entirely.

3. **SQLITE_PATH data directory**
   - What we know: default is `./data/scholar.db`; in CI the `data/` directory under `backend/` may or may not exist.
   - Recommendation: Either set `SQLITE_PATH=/tmp/scholar_ci.db` in env OR add `mkdir -p backend/data` step. Using `/tmp/` is cleaner.

## Sources

### Primary (HIGH confidence)
- GitHub Actions official docs (PostgreSQL service containers) — service container YAML syntax, health check options, port mapping
- `pgvector/setup-pgvector` README — confirmed `pgvector/pgvector:pg16` image for service containers
- `astral-sh/ruff-action` README — `@v3` version, `src` and `args` parameters
- Project files read directly: `backend/pytest.ini`, `backend/requirements.txt`, `backend/tests/conftest.py`, `backend/tests/test_router.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/Dockerfile`, `docker-compose.yml`

### Secondary (MEDIUM confidence)
- WebSearch results confirming `pgvector/pgvector:pg16` is the canonical CI image for pgvector (multiple community sources)
- WebSearch confirming `astral-sh/ruff-action@v3` is current (2025 articles)

## Metadata

**Confidence breakdown:**
- CI trigger syntax: HIGH — official docs verified
- pgvector service container: HIGH — official pgvector/setup-pgvector repo
- ruff-action: HIGH — official astral-sh action repo
- PYTHONPATH/PageIndex requirement: HIGH — read directly from Dockerfile
- pytest marker exclusion: HIGH — read directly from conftest.py and test_router.py
- `CREATE EXTENSION` requirement: MEDIUM — depends on `database.py` content not fully read (see Open Questions)

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (GitHub Actions action versions are stable; pgvector image tags are pinned)
