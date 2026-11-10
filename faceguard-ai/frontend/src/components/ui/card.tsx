import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/utils/cn'

export const Card = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('rounded-xl border border-border bg-card', className)} {...p} />
)

export const CardHeader = ({ title, description, action }: { title: string; description?: string; action?: ReactNode }) => (
  <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
    </div>
    {action}
  </div>
)
