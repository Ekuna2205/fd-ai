import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { AuthShell } from '@/components/AuthShell'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { errorMessage, fieldErrors } from '@/services/api'
import { useT } from '@/i18n'

export default function LoginPage() {
  const { login } = useAuth()
  const { t } = useT()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) next.email = t('Enter a valid email address.')
    if (!password) next.password = t('Enter your password.')
    setErrors(next); setFormError(null)
    if (Object.keys(next).length) return
    setBusy(true)
    try {
      const user = await login({ email: email.trim(), password })
      toast.success(t('Welcome back, {name}.', { name: user.full_name.split(' ')[0] }))
      // GuestRoute redirects to the dashboard (or the page the user came from) once authenticated.
    } catch (err) {
      setErrors(fieldErrors(err)); setFormError(errorMessage(err))
    } finally { setBusy(false) }
  }

  return (
    <AuthShell title={t('Sign in')} subtitle={t('Use your FaceGuard AI account.')}
      footer={<>{t('No account yet?')} <Link to="/register" className="font-medium text-primary hover:underline">{t('Create one')}</Link><span className="mt-3 block"><Link to="/start" className="font-medium text-primary hover:underline">{t('Record with camera without an account')} →</Link></span></>}>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError && <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{formError}</div>}
        <Field label={t('Email')} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email} autoFocus />
        <Field label={t('Password')} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} error={errors.password} />
        <div className="-mt-2 text-right"><Link to="/forgot-password" className="text-xs text-muted hover:text-primary hover:underline">{t('Forgot password?')}</Link></div>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 className="size-4 animate-spin" />}{busy ? t('Signing in…') : t('Sign in')}
        </Button>
      </form>
    </AuthShell>
  )
}
