import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Link, Navigate } from 'react-router-dom'
import { useT } from '@/i18n'
import { getDefaultCollect } from '@/services/collect'

/** /start: public shortcut to the site's main camera page (no account), like collect.ekyc.mn. */
export default function StartPage() {
  const { t } = useT()
  const link = useQuery({ queryKey: ['collect-default-public'], queryFn: getDefaultCollect, retry: false })
  if (link.data) return <Navigate to={`/collect/${link.data.token}`} replace />
  return (
    <div className="grid min-h-dvh place-items-center bg-bg p-6 text-center text-fg">
      {link.isLoading ? <Loader2 className="size-6 animate-spin text-primary" /> : (
        <div className="max-w-sm">
          <p className="font-medium">{t('No collection link is open yet.')}</p>
          <p className="mt-1 text-sm text-muted">{t('An administrator opens one under Datasets → Collection link, or by visiting “Record with camera”.')}</p>
          <Link to="/login" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">{t('Sign in')}</Link>
        </div>
      )}
    </div>
  )
}
