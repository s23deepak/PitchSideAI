import * as React from 'react'
import { cn } from '@/lib/utils'

interface TooltipProps {
  content: React.ReactNode
  children: React.ReactElement
  side?: 'top' | 'bottom' | 'left' | 'right'
  delayDuration?: number
  className?: string
}

const Tooltip = React.forwardRef<HTMLDivElement, TooltipProps>(
  ({ content, children, side = 'top', delayDuration = 200, className }, ref) => {
    const [isVisible, setIsVisible] = React.useState(false)
    const [timeoutId, setTimeoutId] = React.useState<NodeJS.Timeout | null>(null)

    const showTooltip = () => {
      const id = setTimeout(() => setIsVisible(true), delayDuration)
      setTimeoutId(id)
    }

    const hideTooltip = () => {
      if (timeoutId) {
        clearTimeout(timeoutId)
      }
      setIsVisible(false)
    }

    const sideClasses = {
      top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
      bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
      left: 'right-full top-1/2 -translate-y-1/2 mr-2',
      right: 'left-full top-1/2 -translate-y-1/2 ml-2',
    }

    return (
      <div className="relative inline-block" ref={ref}>
        {React.cloneElement(children, {
          onMouseEnter: showTooltip,
          onMouseLeave: hideTooltip,
          onFocus: showTooltip,
          onBlur: hideTooltip,
        })}

        {isVisible && (
          <div
            className={cn(
              'absolute z-50 max-w-[200px] rounded-md bg-background-elevated border border-border px-3 py-1.5 text-xs font-medium text-text-primary shadow-lg animate-fade-in',
              sideClasses[side],
              className
            )}
            role="tooltip"
          >
            {content}
            {/* Arrow */}
            <div
              className={cn(
                'absolute w-2 h-2 bg-background-elevated border-r border-t border-border transform rotate-45',
                side === 'top' && 'left-1/2 -translate-x-1/2 -bottom-1 border-l-0 border-t-0 border-r border-b',
                side === 'bottom' && 'left-1/2 -translate-x-1/2 -top-1 border-r-0 border-b-0 border-l border-t',
                side === 'left' && 'right-1/2 -translate-y-1/2 -mr-1 border-t-0 border-l-0 border-r border-b',
                side === 'right' && 'left-1/2 -translate-y-1/2 -ml-1 border-b-0 border-r-0 border-l border-t'
              )}
            />
          </div>
        )}
      </div>
    )
  }
)
Tooltip.displayName = 'Tooltip'

export { Tooltip }
