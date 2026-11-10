import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { useT } from '@/i18n'
import { roleLabel } from '@/i18n/labels'

export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { t } = useT()
  if (!user) return null
  const initials = user.full_name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()

  async function onLogout() {
    await logout()
    toast.success(t('Signed out.'))
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-2.5">
        <div aria-hidden className="grid size-8 place-items-center rounded-full bg-primary/15 text-xs font-semibold text-primary">{initials}</div>
        <div className="hidden leading-tight sm:block">
          <p className="text-sm font-medium">{user.full_name}</p>
          <p className="text-xs text-muted">{roleLabel(user.role)}</p>
        </div>
      </div>
      <Button variant="ghost" size="icon" onClick={onLogout} aria-label={t('Sign out')} title={t('Sign out')}><LogOut className="size-4" /></Button>
    </div>
  )
}
