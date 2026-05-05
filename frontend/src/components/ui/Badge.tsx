import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-interactive focus:ring-offset-2 focus:ring-offset-background-primary',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-interactive text-background-primary',
        secondary: 'border-transparent bg-background-card-hover text-text-secondary',
        outline: 'border-border text-text-secondary',
        success: 'border-success/30 bg-success/15 text-success',
        warning: 'border-warning/30 bg-warning/15 text-warning',
        danger: 'border-danger/30 bg-danger/15 text-danger',
        narrative: 'border-narrative/30 bg-narrative/15 text-narrative',
        source: 'border-blue-500/30 bg-blue-500/15 text-blue-400',
        confidence: 'border-purple-500/30 bg-purple-500/15 text-purple-400',
        live: 'border-red-500/30 bg-red-500/15 text-red-400 animate-pulse',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  children: React.ReactNode
}

function Badge({ className, variant, children, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props}>
      {children}
    </div>
  )
}

export { Badge, badgeVariants }
