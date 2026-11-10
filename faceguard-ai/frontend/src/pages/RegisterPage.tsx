import { Check, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { AuthShell } from '@/components/AuthShell'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { errorMessage, fieldErrors } from '@/services/api'
import { cn } from '@/utils/cn'
import { useT } from '@/i18n'

// Keep in sync with backend schemas/auth.py::validate_password_strength.
const rules = [
  { label: 'At least 10 characters', test: (p: string) => p.length >= 10 },
  { label: 'A letter', test: (p: string) => /[A-Za-z]/.test(p) },
  { label: 'A number', test: (p: string) => /\d/.test(p) },
]

export default function RegisterPage() {
  const { register } = useAuth()
  const { t } = useT()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (form.full_name.trim().length < 2) next.full_name = t('Enter your full name.')
    if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) next.email = t('Enter a valid email address.')
    if (!rules.every((r) => r.test(form.password))) next.password = t('Password does not meet the requirements.')
    if (form.confirm !== form.password) next.confirm = t('Passwords do not match.')
    setErrors(next); setFormError(null)
    if (Object.keys(next).length) return
    setBusy(true)
    try {
      const user = await register({ full_name: form.full_name.trim(), email: form.email.trim(), password: form.password })
      toast.success(user.role === 'administrator' ? t('Account created. You are the first user, so you are the administrator.') : t('Account created.'))
    } catch (err) {
      setErrors(fieldErrors(err)); setFormError(errorMessage(err))
    } finally { setBusy(false) }
  }

  return (
    <AuthShell title={t('Create your account')} subtitle={t('New accounts start with read-only Viewer access unless this is the first account on the system.')}
      footer={<>{t('Already registered?')} <Link to="/login" className="font-medium text-primary hover:underline">{t('Sign in')}</Link></>}>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError && <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{formError}</div>}
        <Field label={t('Full name')} autoComplete="name" value={form.full_name} onChange={set('full_name')} error={errors.full_name} autoFocus />
        <Field label={t('Email')} type="email" autoComplete="email" value={form.email} onChange={set('email')} error={errors.email} />
        <div>
          <Field label={t('Password')} type="password" autoComplete="new-password" value={form.password} onChange={set('password')} error={errors.password} />
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label={t('Password requirements')}>
            {rules.map((r) => {
              const ok = r.test(form.password)
              return <li key={r.label} className={cn('flex items-center gap-1', ok ? 'text-success' : 'text-muted')}><Check className={cn('size-3', !ok && 'opacity-30')} />{t(r.label)}</li>
            })}
          </ul>
        </div>
        <Field label={t('Confirm password')} type="password" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} error={errors.confirm} />
        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 className="size-4 animate-spin" />}{busy ? t('Creating account…') : t('Create account')}
        </Button>
      </form>
    </AuthShell>
  )
}
