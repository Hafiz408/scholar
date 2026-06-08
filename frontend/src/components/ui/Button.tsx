import type { ButtonHTMLAttributes } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-50'

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-primary-600 text-white shadow-soft hover:bg-primary-700 active:bg-primary-700',
  secondary:
    'border border-surface-border bg-surface-card text-ink-soft shadow-soft hover:bg-surface-subtle hover:text-ink',
  ghost: 'text-ink-soft hover:bg-surface-subtle hover:text-ink',
  danger: 'bg-danger-600 text-white shadow-soft hover:bg-danger-700 active:bg-danger-700',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2.5 text-sm',
}

/**
 * Base button. For navigation, wrap with next/link's <Link> (or pass legacyBehavior)
 * — this component renders a native <button>. Variants: primary | secondary |
 * ghost | danger. Sizes: sm | md.
 */
export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={[BASE, VARIANTS[variant], SIZES[size], className].join(' ')}
      {...props}
    />
  )
}
