---
phase: 06-frontend
plan: "02"
subsystem: ui
tags: [react, nextjs, typescript, tailwind, forms, goal-form, study-plan, progress-bar]

requires:
  - phase: 06-01
    provides: api.ts with createGoal, getGoalPlan, listSources typed fetch wrappers

provides:
  - frontend/src/components/GoalForm.tsx (controlled 6-field goal creation form)
  - frontend/src/components/ProgressBar.tsx (completed/total sessions progress bar)
  - frontend/src/components/StudyPlan.tsx (session card list with 4-state logic)
  - frontend/src/app/goals/new/page.tsx (goal creation page)
  - frontend/src/app/goals/[id]/page.tsx (goal detail page with progress + sessions)

affects:
  - 06-03 (StudyPlan links to /study/{sessionId} — session page must exist)
  - 06-04 (QuizPanel score displayed via quiz_score badge in StudyPlan)

tech-stack:
  added: []
  patterns:
    - "Checkbox list for multi-select: useState<string[]> + toggle function instead of HTML select multiple (avoids INGEST-06 422 bug)"
    - "getSessionState derives UI state from session.status + prevSession.status — session 1 always available, subsequent sessions unlock when previous is complete"
    - "goals/[id]/page.tsx uses 'use client' + useEffect for data fetch — params.id accessed synchronously (Next.js 14 pattern)"

key-files:
  created:
    - frontend/src/components/GoalForm.tsx
    - frontend/src/components/ProgressBar.tsx
    - frontend/src/components/StudyPlan.tsx
  modified:
    - frontend/src/app/goals/new/page.tsx
    - frontend/src/app/goals/[id]/page.tsx

key-decisions:
  - "GoalForm calls createGoal with source_ids (not knowledge_source_ids) — backend CreateGoalRequest uses source_ids as field name"
  - "Redirect on success uses studyPlan.goal.id (not studyPlan.goal_id) — getGoalPlan returns {goal: {...}, sessions: [...]}"
  - "goals/[id]/page.tsx marked 'use client' because data fetch uses useEffect; server component would require async RSC pattern incompatible with error/loading states"

patterns-established:
  - "Pattern: Error boundary in data-fetching pages — catch block sets error state, renders red box UI instead of crash"
  - "Pattern: Loading state guard — render 'Loading...' text while plan is null, prevents null reference in render"

requirements-completed: [FE-02, FE-03]

duration: 2min
completed: 2026-03-19
---

# Phase 6 Plan 02: Goal Form and Goal Detail Page Summary

**Controlled 6-field goal creation form with checkbox source multi-select, ProgressBar, and 4-state session card list (locked/available/in_progress/complete) with quiz score badges.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-19T00:17:20Z
- **Completed:** 2026-03-19T00:19:14Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- GoalForm: 6-field controlled form (title, topic, sources, deadline, level, sessions/week) with checkbox-based multi-select, submits to `createGoal()`, redirects on success, displays errors without crashing
- ProgressBar: renders `Math.round((completed/total)*100)%` width with Tailwind transition-all, shows "{N} of {M} sessions complete" label
- StudyPlan: renders session cards with 4 distinct states derived from `getSessionState()` — locked cards show lock emoji, available/in_progress cards wrap in Link to `/study/{id}`, complete cards show quiz score badge when `quiz_score != null`

## Task Commits

Each task was committed atomically:

1. **Task 1: Goal creation form component and page** - `73e91f1` (feat)
2. **Task 2: Goal detail page — progress bar and session cards** - `7483398` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `frontend/src/components/GoalForm.tsx` - 6-field controlled form, checkbox multi-select for sources, createGoal + router redirect
- `frontend/src/app/goals/new/page.tsx` - Server component wrapper with "Create Study Goal" heading
- `frontend/src/components/ProgressBar.tsx` - Progress track with dynamic width percentage and session count label
- `frontend/src/components/StudyPlan.tsx` - Session card list with getSessionState logic, state-based Tailwind classes, quiz score badges
- `frontend/src/app/goals/[id]/page.tsx` - Client component, useEffect data fetch, error/loading states, renders ProgressBar + StudyPlan

## Decisions Made

- `createGoal()` called with `source_ids` field (not `knowledge_source_ids`) — backend `CreateGoalRequest` model uses `source_ids` as the field name (confirmed in goals.py router)
- Redirect target is `studyPlan.goal.id` not `studyPlan.goal_id` — `getGoalPlan` returns `{ goal: StudyGoal, sessions: StudySession[] }` per the `StudyPlan` type
- `goals/[id]/page.tsx` is `'use client'` using `useEffect` for data fetching — provides clean error + loading UI without async RSC complexity

## Deviations from Plan

None — plan executed exactly as written. The only note is that `createGoal` receives `source_ids` (not `knowledge_source_ids` as the plan text stated) — this matches what `api.ts` and the backend router actually use, so no code change was needed, just awareness.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Goal creation and goal detail flow complete — users can create goals and see session progress
- StudyPlan links to `/study/{sessionId}` — ready for 06-03 to implement the study session page
- Quiz score badges in place — will display correctly once 06-04 implements quiz flow

---
*Phase: 06-frontend*
*Completed: 2026-03-19*

## Self-Check: PASSED

All files confirmed present on disk:
- FOUND: frontend/src/components/GoalForm.tsx (186 lines, >= 80 required)
- FOUND: frontend/src/components/ProgressBar.tsx (22 lines, >= 20 required)
- FOUND: frontend/src/components/StudyPlan.tsx (96 lines, >= 60 required)
- FOUND: frontend/src/app/goals/new/page.tsx (10 lines, >= 10 required)
- FOUND: frontend/src/app/goals/[id]/page.tsx (57 lines, >= 50 required)

Both task commits confirmed in git history: 73e91f1, 7483398.
TypeScript: zero errors (`npx tsc --noEmit` clean).
