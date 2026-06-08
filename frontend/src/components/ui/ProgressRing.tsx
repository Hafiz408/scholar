import type { ReactNode } from 'react'

export interface ProgressRingProps {
  /** Progress 0–100. Clamped. */
  value: number
  /** Diameter in px. Default 72. */
  size?: number
  /** Stroke width in px. Default 6. */
  strokeWidth?: number
  /** Center content. Defaults to the rounded percentage. */
  label?: ReactNode
  className?: string
}

/**
 * SVG circular progress indicator. Track + indigo arc, with centered label.
 * Used by the Goals grid to show session completion.
 */
export default function ProgressRing({
  value,
  size = 72,
  strokeWidth = 6,
  label,
  className = '',
}: ProgressRingProps) {
  const pct = Math.max(0, Math.min(100, value))
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference

  return (
    <div
      className={['relative inline-flex items-center justify-center', className].join(' ')}
      style={{ width: size, height: size }}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-surface-ring"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="stroke-primary-600 transition-[stroke-dashoffset] duration-500 ease-out"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-ink">
        {label ?? `${Math.round(pct)}%`}
      </span>
    </div>
  )
}
