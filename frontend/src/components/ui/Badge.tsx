import type { HTMLAttributes } from 'react'

export type BadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
}

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-subtle text-ink-soft ring-surface-ring',
  info: 'bg-info-50 text-info-700 ring-info-500/20',
  success: 'bg-success-50 text-success-700 ring-success-500/20',
  warning: 'bg-warning-50 text-warning-700 ring-warning-500/20',
  danger: 'bg-danger-50 text-danger-700 ring-danger-500/20',
}

/**
 * Small status pill. `tone` maps to the semantic palette.
 */
export default function Badge({
  tone = 'neutral',
  className = '',
  ...props
}: BadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        TONES[tone],
        className,
      ].join(' ')}
      {...props}
    />
  )
}
