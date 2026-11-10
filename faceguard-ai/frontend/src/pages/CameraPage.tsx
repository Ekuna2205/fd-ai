import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { ErrorState } from '@/components/ui/state'
import { useT } from '@/i18n'
import { errorMessage } from '@/services/api'
import { ensureDefaultCollect } from '@/services/collect'
import { CollectFlow } from './CollectPage'

/** "Record with camera": the collect.ekyc.mn-style camera flow for every signed-in user, inside the app. */
export default function CameraPage() {
  const { t } = useT()
  const link = useQuery({ queryKey: ['collect-default'], queryFn: ensureDefaultCollect, retry: false, staleTime: 60_000 })
  return (
    <div className="space-y-4">
      <PageHeader title={t('Record with camera')} description={t('Choose Real or Fake, then follow the instructions in the oval frame. The recording is added to the training data.')} />
      {link.isLoading && <div className="grid h-64 place-items-center"><Loader2 className="size-6 animate-spin text-primary" /></div>}
      {link.isError && <ErrorState title={t('Camera page unavailable')} message={errorMessage(link.error)} onRetry={() => void link.refetch()} />}
      {link.data && <CollectFlow token={link.data.token} embedded />}
    </div>
  )
}
