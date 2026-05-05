import * as React from 'react'
import { cn } from '@/lib/utils'
import { getSliderAriaProps } from '@/lib/accessibility'

export interface SliderProps {
  min?: number
  max?: number
  step?: number
  value?: number
  defaultValue?: number
  onValueChange?: (value: number) => void
  disabled?: boolean
  className?: string
  ariaLabel?: string
  showTooltip?: boolean
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  (
    {
      min = 0,
      max = 100,
      step = 1,
      value,
      defaultValue = 50,
      onValueChange,
      disabled = false,
      className,
      ariaLabel,
      showTooltip = false,
    },
    ref
  ) => {
    const [localValue, setLocalValue] = React.useState(value ?? defaultValue)
    const [isDragging, setIsDragging] = React.useState(false)

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = Number(e.target.value)
      setLocalValue(newValue)
      onValueChange?.(newValue)
    }

    const percentage = ((localValue - min) / (max - min)) * 100

    return (
      <div className={cn('relative flex w-full touch-none select-none items-center', className)}>
        {/* Track */}
        <div className="relative h-4 w-full grow overflow-hidden rounded-full bg-background-card">
          <div
            className="absolute h-full bg-interactive transition-all"
            style={{ width: `${percentage}%` }}
          />
        </div>

        {/* Thumb */}
        <input
          type="range"
          ref={ref}
          min={min}
          max={max}
          step={step}
          value={localValue}
          disabled={disabled}
          onChange={handleChange}
          onPointerDown={() => setIsDragging(true)}
          onPointerUp={() => setIsDragging(false)}
          aria-label={ariaLabel}
          {...getSliderAriaProps(min, max, localValue, ariaLabel)}
          className={cn(
            'absolute h-4 w-full appearance-none bg-transparent',
            'disabled:pointer-events-none disabled:opacity-50',
            '[&::-webkit-slider-thumb]:-webkit-appearance-none',
            '[&::-webkit-slider-thumb]:h-4',
            '[&::-webkit-slider-thumb]:w-4',
            '[&::-webkit-slider-thumb]:rounded-full',
            '[&::-webkit-slider-thumb]:bg-text-primary',
            '[&::-webkit-slider-thumb]:shadow-md',
            '[&::-webkit-slider-thumb]:transition-all',
            '[&::-webkit-slider-thumb]:hover:scale-110',
            '[&::-webkit-slider-thumb]:focus:outline-none',
            '[&::-webkit-slider-thumb]:focus:ring-2',
            '[&::-webkit-slider-thumb]:focus:ring-interactive',
            '[&::-webkit-slider-thumb]:focus:ring-offset-2',
            '[&::-webkit-slider-thumb]:focus:ring-offset-background-primary'
          )}
        />

        {/* Tooltip */}
        {showTooltip && isDragging && (
          <div
            className="absolute -top-8 rounded-md bg-background-elevated px-2 py-1 text-xs font-medium text-text-primary border border-border"
            style={{ left: `${percentage}%`, transform: 'translateX(-50%)' }}
          >
            {localValue}
          </div>
        )}
      </div>
    )
  }
)
Slider.displayName = 'Slider'

export { Slider }
