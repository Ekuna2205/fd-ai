import { useId, type SelectHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

export function Select({ label, className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs text-muted">{label}</label>
      <select id={id} className={cn('h-9 w-full rounded-lg border border-border bg-bg px-2.5 text-sm hover:border-muted/40', className)} {...props}>{children}</select>
    </div>
  )
}
