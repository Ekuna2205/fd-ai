import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/ui/state'
import { ResultPanel } from '@/components/verify/ResultPanel'
import { errorMessage } from '@/services/api'
import { getVerification } from '@/services/face'
import { useT } from '@/i18n'

export default function VerificationDetailPage() {
  const { t } = useT()
  const { id = '' } = useParams()
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ['verification', id], queryFn: () => getVerification(id), retry: false })
  return (
    <div className="max-w-3xl space-y-6">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="size-4" />{t('Dashboard')}</Link>
      <h1 className="text-2xl font-semibold tracking-tight">{t('Verification record')}</h1>
      {isLoading && <Skeleton className="h-96" />}
      {isError && <ErrorState title={t('Record unavailable')} message={errorMessage(error)} onRetry={() => void refetch()} />}
      {data && <ResultPanel result={data} />}
    </div>
  )
}
