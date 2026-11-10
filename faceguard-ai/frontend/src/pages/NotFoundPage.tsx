import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n'

export default function NotFoundPage() {
  const { t } = useT()
  return (
    <div className="flex flex-col items-start gap-3">
      <h1 className="text-2xl font-semibold">{t('Page not found')}</h1>
      <p className="text-sm text-muted">{t('The address you opened does not match any FaceGuard AI page.')}</p>
      <Button asChild><Link to="/">{t('Back to dashboard')}</Link></Button>
    </div>
  )
}
