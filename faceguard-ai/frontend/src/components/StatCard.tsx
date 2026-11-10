import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/utils/cn'

export function StatCard({ label, value, icon: Icon, tone = 'text-primary', loading }:
  { label: string; value: string; icon: LucideIcon; tone?: string; loading?: boolean }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-muted">
        <span className="text-xs">{label}</span>
        <Icon className={cn('size-4', tone)} />
      </div>
      {loading ? <Skeleton className="mt-3 h-7 w-20" /> : <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>}
    </Card>
  )
}
