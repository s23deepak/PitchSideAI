import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-interactive focus-visible:ring-offset-2 focus-visible:ring-offset-background-primary disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-interactive text-background-primary hover:opacity-90',
        primary: 'bg-gradient-to-r from-blue-500 to-purple-500 text-white hover:opacity-90',
        secondary: 'bg-background-card border border-border text-text-primary hover:bg-background-card-hover',
        ghost: 'hover:bg-background-card-hover hover:text-text-primary',
        outline: 'border border-border bg-transparent hover:bg-background-card-hover',
        danger: 'bg-danger/15 border border-danger/30 text-danger hover:bg-danger/25',
        narrative: 'bg-narrative/15 border border-narrative/30 text-narrative hover:bg-narrative/25',
      },
      size: {
        default: 'h-10 px-4 py-2 text-sm',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-12 rounded-md px-8 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
