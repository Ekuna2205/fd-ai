import { Loader2, LogOut, Moon, Sun, Languages } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { PageHeader } from '@/components/PageHeader'
import { PasswordRules, passwordOk } from '@/components/PasswordRules'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { Field } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { useTheme } from '@/hooks/useTheme'
import { errorMessage, fieldErrors } from '@/services/api'
import { changePassword, updateMe } from '@/services/auth'
import { cn } from '@/utils/cn'
import { formatDateTime } from '@/utils/format'
import { LANGS, useT } from '@/i18n'
import { roleLabel } from '@/i18n/labels'

function ProfileCard() {
  const { t } = useT()
  const { user, setUser } = useAuth()
  const [name, setName] = useState(user?.full_name ?? '')
  const [err, setErr] = useState<string>()
  const [busy, setBusy] = useState(false)
  if (!user) return null
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (name.trim().length < 2) { setErr(t('Enter your full name.')); return }
    setBusy(true); setErr(undefined)
    try { setUser(await updateMe(name.trim())); toast.success(t('Profile updated.')) }
    catch (e2) { setErr(fieldErrors(e2).full_name ?? errorMessage(e2)) } finally { setBusy(false) }
  }
  return (
    <Card>
      <CardHeader title={t('Profile')} description={t('Your role and account status are managed by an administrator.')} />
      <form onSubmit={submit} className="space-y-4 p-5" noValidate>
        <Field label={t('Full name')} value={name} onChange={(e) => setName(e.target.value)} error={err} autoComplete="name" maxLength={100} />
        <Field label={t('Email')} value={user.email} readOnly disabled hint={t('The email address cannot be changed here.')} />
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-xs text-muted">{t('Role')}</dt><dd>{roleLabel(user.role)}</dd></div>
          <div><dt className="text-xs text-muted">{t('Status')}</dt><dd className={user.is_active ? 'text-success' : 'text-danger'}>{user.is_active ? t('Active') : t('Disabled')}</dd></div>
          <div><dt className="text-xs text-muted">{t('Member since')}</dt><dd>{formatDateTime(user.created_at)}</dd></div>
          <div><dt className="text-xs text-muted">{t('Last sign-in')}</dt><dd>{user.last_login_at ? formatDateTime(user.last_login_at) : '—'}</dd></div>
        </dl>
        <Button type="submit" disabled={busy || name.trim() === user.full_name}>{busy && <Loader2 className="size-4 animate-spin" />}{t('Save changes')}</Button>
      </form>
    </Card>
  )
}

function PasswordCard() {
  const { t } = useT()
  const { accept } = useAuth()
  const [f, setF] = useState({ current: '', next: '', confirm: '' })
  const [errs, setErrs] = useState<Record<string, string>>({})
  const [formErr, setFormErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((s) => ({ ...s, [k]: e.target.value }))
  async function submit(e: FormEvent) {
    e.preventDefault()
    const n: Record<string, string> = {}
    if (!f.current) n.current = t('Enter your current password.')
    if (!passwordOk(f.next)) n.next = t('Password does not meet the requirements.')
    if (f.next === f.current && f.next) n.next = t('Choose a password different from the current one.')
    if (f.confirm !== f.next) n.confirm = t('Passwords do not match.')
    setErrs(n); setFormErr(null)
    if (Object.keys(n).length) return
    setBusy(true)
    try {
      accept(await changePassword({ current_password: f.current, new_password: f.next })) // fresh tokens; other sessions end
      setF({ current: '', next: '', confirm: '' }); toast.success(t('Password changed. Your other sessions were signed out.'))
    } catch (e2) {
      const fe = fieldErrors(e2); setErrs({ ...(fe.new_password ? { next: fe.new_password } : {}) }); setFormErr(errorMessage(e2))
    } finally { setBusy(false) }
  }
  return (
    <Card>
      <CardHeader title={t('Change password')} description={t('Changing it signs out every other device.')} />
      <form onSubmit={submit} className="space-y-4 p-5" noValidate>
        {formErr && <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{formErr}</div>}
        <Field label={t('Current password')} type="password" autoComplete="current-password" value={f.current} onChange={set('current')} error={errs.current} />
        <div><Field label={t('New password')} type="password" autoComplete="new-password" value={f.next} onChange={set('next')} error={errs.next} /><PasswordRules value={f.next} /></div>
        <Field label={t('Confirm new password')} type="password" autoComplete="new-password" value={f.confirm} onChange={set('confirm')} error={errs.confirm} />
        <Button type="submit" disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />}{t('Change password')}</Button>
      </form>
    </Card>
  )
}

export default function SettingsPage() {
  const { t } = useT()
  const { theme, setTheme } = useTheme()
  const { lang, setLang } = useT()
  const { logout } = useAuth()
  const navigate = useNavigate()
  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title={t('Profile & settings')} description={t('Manage your account, security and appearance.')} />
      <ProfileCard />
      <PasswordCard />
      <Card>
        <CardHeader title={t('Appearance')} />
        <div className="grid grid-cols-2 gap-3 p-5" role="radiogroup" aria-label={t('Theme')}>
          {([['dark', 'Dark', Moon], ['light', 'Light', Sun]] as const).map(([v, label, Icon]) => (
            <button key={v} role="radio" aria-checked={theme === v} onClick={() => setTheme(v)}
              className={cn('flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-3 text-sm transition-colors', theme === v ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-card-hover')}>
              <Icon className="size-4" />{t(label)}
            </button>))}
        </div>
      </Card>
      <Card>
        <CardHeader title={t('Language')} description={t('Applies to this browser. Messages from the server follow the same choice.')} />
        <div className="grid grid-cols-2 gap-3 p-5" role="radiogroup" aria-label={t('Language')}>
          {LANGS.map((l) => (
            <button key={l.code} role="radio" lang={l.code} aria-checked={lang === l.code} onClick={() => setLang(l.code)}
              className={cn('flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-3 text-sm transition-colors', lang === l.code ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-card-hover')}>
              <Languages className="size-4" />{l.label}
            </button>))}
        </div>
      </Card>
      <Card>
        <CardHeader title={t('Session')} description={t('Signing out revokes this browser\'s refresh token on the server.')} />
        <div className="p-5"><Button variant="outline" onClick={async () => { await logout(); toast.success(t('Signed out.')); navigate('/login', { replace: true }) }}><LogOut className="size-4" />{t('Sign out')}</Button></div>
      </Card>
    </div>
  )
}
