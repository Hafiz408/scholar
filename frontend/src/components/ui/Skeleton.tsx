import type { HTMLAttributes } from 'react'

export type SkeletonProps = HTMLAttributes<HTMLDivElement>

/**
 * Pulsing loading placeholder. Size it via className (e.g. "h-4 w-32").
 * Defaults to a single text-line height / full width.
 */
export default function Skeleton({ className = '', ...props }: SkeletonProps) {
  return (
    <div
      aria-hidden
      className={[
        'animate-pulse rounded-md bg-surface-subtle',
        className || 'h-4 w-full',
      ].join(' ')}
      {...props}
    />
  )
}
