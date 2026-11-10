import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 cursor-pointer',
  {
    variants: {
      variant: {
        default: 'bg-primary text-bg hover:bg-primary/85',
        outline: 'border border-border bg-transparent text-fg hover:bg-card-hover',
        ghost: 'text-muted hover:bg-card-hover hover:text-fg',
        danger: 'bg-danger text-white hover:bg-danger/85',
      },
      size: { sm: 'h-8 px-3', md: 'h-10 px-4', icon: 'size-9' },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  },
)

interface Props extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({ className, variant, size, asChild, ...props }: Props) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
