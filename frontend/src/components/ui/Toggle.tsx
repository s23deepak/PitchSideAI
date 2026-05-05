import * as React from 'react'
import { cn } from '@/lib/utils'

interface ToggleProps {
  pressed: boolean
  onPressedChange?: (pressed: boolean) => void
  disabled?: boolean
  className?: string
  ariaLabel?: string
  children?: React.ReactNode
}

const Toggle = React.forwardRef<HTMLButtonElement, ToggleProps>(
  ({ pressed, onPressedChange, disabled = false, className, ariaLabel, children }, ref) => {
    const handleClick = () => {
      if (!disabled) {
        onPressedChange?.(!pressed)
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (disabled) return
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onPressedChange?.(!pressed)
      }
    }

    return (
      <button
        ref={ref}
        type="button"
        disabled={disabled}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        aria-pressed={pressed}
        aria-label={ariaLabel}
        className={cn(
          'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-interactive focus-visible:ring-offset-2 focus-visible:ring-offset-background-primary',
          'disabled:pointer-events-none disabled:opacity-50',
          pressed
            ? 'bg-interactive text-background-primary'
            : 'bg-background-card text-text-secondary hover:bg-background-card-hover hover:text-text-primary',
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)
Toggle.displayName = 'Toggle'

export { Toggle }
