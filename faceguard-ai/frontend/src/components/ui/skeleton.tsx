import { cn } from '@/utils/cn'

export const Skeleton = ({ className }: { className?: string }) => (
  <div aria-hidden className={cn('animate-pulse rounded-md bg-border/70', className)} />
)
