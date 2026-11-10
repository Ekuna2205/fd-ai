import { cn } from '@/utils/cn'
import type { VerificationStatus } from '@/types/dashboard'
import { statusLabel } from '@/i18n/labels'

const tone: Record<VerificationStatus, string> = {
  REAL: 'bg-success/15 text-success',
  FAKE: 'bg-danger/15 text-danger',
  UNCERTAIN: 'bg-warning/15 text-warning',
  NO_FACE: 'bg-muted/15 text-muted',
  MULTIPLE_FACES: 'bg-muted/15 text-muted',
  PROCESSING: 'bg-secondary/15 text-secondary',
  ERROR: 'bg-danger/15 text-danger',
}

export const StatusBadge = ({ status }: { status: VerificationStatus }) => (
  <span className={cn('rounded-md px-2 py-0.5 text-xs font-medium', tone[status])}>
    {statusLabel(status)}
  </span>
)
