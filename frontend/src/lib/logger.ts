// ─── Log levels ───────────────────────────────────────────────────────────────

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

// Severity order. A message emits only when its level is >= the active level.
const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
}

const PREFIX = '[scholar]'

// ─── Active level resolution ────────────────────────────────────────────────

/**
 * Resolves the active log level.
 *
 * Source: NEXT_PUBLIC_LOG_LEVEL (case-insensitive). NEXT_PUBLIC_ vars are
 * inlined at build time, so direct access is safe in the browser.
 *
 * Default: 'debug' outside production, 'info' in production. An invalid env
 * value falls back to the default without throwing.
 */
export function getLogLevel(): LogLevel {
  const fallback: LogLevel =
    process.env.NODE_ENV === 'production' ? 'info' : 'debug'

  const raw = process.env.NEXT_PUBLIC_LOG_LEVEL
  if (!raw) return fallback

  const normalized = raw.trim().toLowerCase()
  if (normalized in LEVEL_ORDER) {
    return normalized as LogLevel
  }
  return fallback
}

// Resolved once at module load — env is fixed for the lifetime of the bundle.
const activeLevel = getLogLevel()

function shouldLog(level: LogLevel): boolean {
  return LEVEL_ORDER[level] >= LEVEL_ORDER[activeLevel]
}

// ─── Logger ─────────────────────────────────────────────────────────────────

/**
 * Level-gated console wrapper. Each method prefixes messages with `[scholar]`
 * and only emits when its level is at or above the active level.
 */
export const logger = {
  debug(...args: unknown[]): void {
    if (shouldLog('debug')) console.debug(PREFIX, ...args)
  },
  info(...args: unknown[]): void {
    if (shouldLog('info')) console.info(PREFIX, ...args)
  },
  warn(...args: unknown[]): void {
    if (shouldLog('warn')) console.warn(PREFIX, ...args)
  },
  error(...args: unknown[]): void {
    if (shouldLog('error')) console.error(PREFIX, ...args)
  },
}
