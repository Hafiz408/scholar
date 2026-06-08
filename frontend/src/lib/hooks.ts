'use client'

import useSWR from 'swr'
import {
  listGoals,
  listSources,
  listSuperThreads,
  getSuperThread,
} from './api'

/**
 * Typed SWR data hooks over the api module.
 *
 * Cache keys are stable strings (or tuples for parameterized fetches) so callers
 * can `mutate('goals')`, `mutate('sources')`, etc. after writes. The fetcher
 * closures defer to the api functions, which carry their own error handling.
 */

export function useGoals() {
  return useSWR('goals', () => listGoals())
}

export function useSources() {
  return useSWR('sources', () => listSources())
}

export function useSuperThreads() {
  return useSWR('super-threads', () => listSuperThreads())
}

/** Pass `null` to skip the request (e.g. before a thread is selected). */
export function useSuperThread(threadId: string | null) {
  return useSWR(
    threadId ? (['super-thread', threadId] as const) : null,
    () => getSuperThread(threadId as string)
  )
}
