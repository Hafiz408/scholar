---
phase: 16-real-ragas-benchmark
plan: 01
subsystem: eval
tags: [ragas, argparse, benchmark, cli, ascii-table]

# Dependency graph
requires:
  - phase: 07-evaluation
    provides: run_ragas.py baseline benchmark script with golden_qa.json
  - phase: 15-github-actions-ci
    provides: CI workflow that invokes eval scripts
provides:
  - --output-dir CLI argument wired into all three result JSON write paths
  - ASCII summary table printed to stdout after benchmark completes (both real and dry-run)
affects:
  - CI/CD pipelines invoking run_ragas.py with configurable output directories
  - Any automation parsing stdout for benchmark results

# Tech tracking
tech-stack:
  added: []
  patterns:
    - argparse --output-dir with default=None resolved against RESULTS_DIR constant (fallback pattern)
    - output_dir.mkdir(parents=True, exist_ok=True) before timestamp creation (eager mkdir)
    - Step 10 ASCII table using f-strings only — no tabulate dependency

key-files:
  created: []
  modified:
    - backend/eval/run_ragas.py

key-decisions:
  - "--output-dir defaults to None (not RESULTS_DIR) so args namespace is clean; resolution happens immediately after parse_args() via ternary"
  - "output_dir.mkdir(parents=True, exist_ok=True) called before timestamp setup to avoid race between mkdir and first write"
  - "Step 5 RESULTS_DIR.mkdir() removed entirely — superseded by the earlier output_dir.mkdir(parents=True)"
  - "ASCII table uses f-string column formatting only — no tabulate import — to keep zero new dependencies"
  - "Step 9 label updated to 'Benchmark Comparison (JSON)' to distinguish from new Step 10 human-readable table"

patterns-established:
  - "CLI output-dir pattern: default=None + post-parse ternary + early mkdir with parents=True"

requirements-completed: [EVAL-01]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 16 Plan 01: Real RAGAS Benchmark CLI Enhancements Summary

**`--output-dir` argparse flag wired into all three JSON result write paths plus f-string ASCII summary table printed to stdout after benchmark runs**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-21T23:19:05Z
- **Completed:** 2026-03-21T23:22:48Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added `--output-dir` CLI argument with backward-compatible default (`RESULTS_DIR`) so existing invocations continue working unchanged
- Wired `output_dir` into all three result write paths (`pi_path`, `vec_path`, `cmp_path`) — no hardcoded `RESULTS_DIR` left in path construction
- Added Step 10 ASCII summary table to stdout with column headers (Strategy, Faithfulness, Answer Rel., Ctx Prec., Avg Latency) and two data rows formatted to 3 decimal places
- Updated module docstring to document `--output-dir` usage example

## Task Commits

Each task was committed atomically:

1. **Task 1: Add --output-dir argument and wire into all write paths** - `f4a1def` (feat)
2. **Task 2: Add ASCII summary table printed to stdout after Step 9** - `2cdb84b` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/eval/run_ragas.py` - Added `--output-dir` argparse arg, resolved `output_dir` variable, removed old `RESULTS_DIR.mkdir()`, updated all three result write paths, added Step 10 ASCII table, updated module docstring

## Decisions Made
- `--output-dir` defaults to `None` in argparse (not `RESULTS_DIR` directly) so resolution happens in one ternary after `parse_args()` — keeps argparse namespace clean
- `output_dir.mkdir(parents=True, exist_ok=True)` called before timestamp setup (not inside Step 5) to guarantee directory exists before any write
- Step 5's original `RESULTS_DIR.mkdir(exist_ok=True)` removed — superseded by the earlier `output_dir.mkdir(parents=True, exist_ok=True)`
- ASCII table uses f-strings only — no `tabulate` import — preserving zero new pip dependencies per plan requirement

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `run_ragas.py` is now CI/CD-ready: can write results to any directory via `--output-dir` and prints a human-readable summary table for easy log inspection
- EVAL-01 requirement satisfied
- EVAL-02/EVAL-03 (real RAGAS run with ingested PDF) remain deferred — require an actual ingested PDF with a PageIndex tree before running

---
*Phase: 16-real-ragas-benchmark*
*Completed: 2026-03-22*
