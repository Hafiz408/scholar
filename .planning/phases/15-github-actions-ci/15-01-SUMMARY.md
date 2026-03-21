---
phase: 15-github-actions-ci
plan: "01"
subsystem: infra
tags: [github-actions, ci, ruff, pytest, pgvector, postgresql, python]

# Dependency graph
requires:
  - phase: 03-retrieval-engine
    provides: test_router.py with @pytest.mark.integration on accuracy gate test
  - phase: 01-infrastructure
    provides: backend/requirements.txt, database.py with init_pgvector_schema()
provides:
  - GitHub Actions CI workflow triggering on PRs to feature/v2 and main
  - Automated ruff linting with inline PR annotations via astral-sh/ruff-action@v3
  - Automated pytest run excluding live-LLM gate via -m "not integration"
  - pgvector/pg16 service container with health check for DB-dependent tests
affects:
  - 16-evaluation (any future PRs will run CI automatically)

# Tech tracking
tech-stack:
  added: [github-actions, astral-sh/ruff-action@v3, pgvector/pgvector:pg16]
  patterns:
    - pytest marker exclusion (-m "not integration") to skip live-API tests in CI
    - service container health checks (pg_isready) before test steps execute
    - PYTHONPATH env var injection for non-installed local packages (PageIndex)

key-files:
  created:
    - .github/workflows/ci.yml
  modified: []

key-decisions:
  - "pgvector/pgvector:pg16 image (not postgres:16) — pgvector extension compiled in, no separate CREATE EXTENSION psql step needed"
  - "astral-sh/ruff-action@v3 (not pip install ruff) — provides inline PR annotations"
  - "-m 'not integration' (not --ignore=tests/test_router.py) — preserves 2 mocked tests in that file while excluding accuracy gate"
  - "working-directory: backend for pytest — pytest.ini is in backend/, without this app imports fail with ModuleNotFoundError"
  - "PYTHONPATH: /opt/pageindex on pytest step only — PageIndex cloned at /opt/pageindex; ruff does not need it"
  - "SQLITE_PATH: /tmp/scholar_ci.db — avoids ./data/ directory-not-found errors in CI"
  - "DATABASE_URL only on pytest step env (not job-level) — keeps job env clean"

patterns-established:
  - "CI exclusion pattern: use pytest markers (-m 'not integration') rather than path ignores for selective test execution"

requirements-completed: [CI-01, CI-02, CI-03]

# Metrics
duration: 2min
completed: 2026-03-22
---

# Phase 15 Plan 01: GitHub Actions CI Summary

**GitHub Actions workflow with pgvector/pg16 service container, ruff linting, and pytest excluding live-LLM gate via -m "not integration"**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-21T22:54:07Z
- **Completed:** 2026-03-21T22:56:49Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Created `.github/workflows/ci.yml` triggering on PRs to `feature/v2` and `main`
- Configured pgvector/pgvector:pg16 service container with pg_isready health check ensuring DB ready before tests
- Established marker-based test exclusion: `test_router_accuracy_gate` is `@pytest.mark.integration` (confirmed), excluded cleanly via `-m "not integration"` without affecting the 2 mocked tests in the same file

## Task Commits

Each task was committed atomically:

1. **Task 1: Create .github/workflows/ci.yml** - `855b258` (feat)
2. **Task 2: Validate marker exclusion and confirm no broken imports** - no commit (verification-only, no files modified)

**Plan metadata:** *(pending docs commit)*

## Files Created/Modified

- `.github/workflows/ci.yml` — Complete CI workflow: trigger on PRs, pgvector service, Python 3.12 setup, PageIndex clone, pip install, ruff lint, pytest with env vars

## Decisions Made

- Used `pgvector/pgvector:pg16` (not `postgres:16`) — pgvector extension must be compiled in; `init_pgvector_schema()` in database.py already runs `CREATE EXTENSION IF NOT EXISTS vector` at line 118, so no separate psql step is needed
- Used `astral-sh/ruff-action@v3` (not `pip install ruff && ruff`) — gives inline PR annotations
- Used `-m "not integration"` (not `--ignore=tests/test_router.py`) — preserves `test_retr02_fallback_no_pageindex_docs` and `test_retr02_fallback_empty_source_ids` (both mocked, no live API) while excluding only `test_router_accuracy_gate`
- `working-directory: backend` for pytest — pytest.ini lives in `backend/`; without this `from app.xxx import` fails with ModuleNotFoundError
- `PYTHONPATH: /opt/pageindex` on pytest step env — PageIndex cloned from GitHub, not an installed package
- `SQLITE_PATH: /tmp/scholar_ci.db` — CI runner has no `./data/` directory pre-created

## Deviations from Plan

None — plan executed exactly as written.

## Task 2 Verification Findings

- **Marker registered:** `conftest.py` line 5 — `config.addinivalue_line("markers", "integration: marks tests as integration tests (require live APIs)")` — CONFIRMED
- **Accuracy gate marked:** `test_router.py` line 24 — `@pytest.mark.integration` on `test_router_accuracy_gate` — CONFIRMED
- **CREATE EXTENSION:** `database.py` line 118 — `cur.execute("CREATE EXTENSION IF NOT EXISTS vector")` — CONFIRMED; no separate psql step needed
- **conftest.py:** No changes required

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. The workflow will activate automatically when a PR is opened targeting `feature/v2` or `main` on GitHub.

## Next Phase Readiness

- CI workflow is complete and ready for Phase 16 (Evaluation)
- Any PR to `feature/v2` or `main` will automatically run ruff + pytest
- EVAL-02/EVAL-03 (real RAGAS run) remains deferred — requires ingested PDF with PageIndex tree

---
*Phase: 15-github-actions-ci*
*Completed: 2026-03-22*
