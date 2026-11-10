import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Logo } from '@/components/Logo'
import { useAuth } from '@/hooks/useAuth'
import type { Role } from '@/types/auth'
import { useT } from '@/i18n'

function FullScreenLoader() {
  const { t } = useT()
  return (
    <div className="grid h-full place-items-center" role="status" aria-label={t('Loading')}>
      <div className="flex animate-pulse flex-col items-center gap-3"><Logo /><p className="text-xs text-muted">{t('Restoring your session…')}</p></div>
    </div>
  )
}

/** Renders child routes only for signed-in users, optionally restricted to certain roles. */
export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { status, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <FullScreenLoader />
  if (status === 'anonymous' || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <Outlet />
}

/** Login/register pages: signed-in users are sent to the dashboard. */
export function GuestRoute() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <FullScreenLoader />
  if (status === 'authenticated') {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from && from !== '/login' ? from : '/'} replace />
  }
  return <Outlet />
}
