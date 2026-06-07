import type { HTMLAttributes } from 'react'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Add hover elevation + pointer affordance (for cards that act as links). */
  interactive?: boolean
}

/**
 * Padded surface card — rounded-xl, soft warm border, subtle shadow on white.
 * Pass `interactive` for clickable cards (lift on hover). To make the whole card
 * a link, wrap it in <Link> and set `interactive`, or pass an onClick.
 * Padding/spacing can be overridden via className.
 */
export default function Card({
  interactive = false,
  className = '',
  ...props
}: CardProps) {
  return (
    <div
      className={[
        'rounded-xl border border-surface-border bg-surface-card p-6 shadow-card transition-all',
        interactive ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-lift' : '',
        className,
      ].join(' ')}
      {...props}
    />
  )
}
