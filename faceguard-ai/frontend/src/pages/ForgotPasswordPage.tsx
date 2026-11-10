import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthShell } from '@/components/AuthShell'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/input'
import { errorMessage } from '@/services/api'
import { forgotPassword, resetStatus } from '@/services/auth'
import { translateServer, useT } from '@/i18n'

export default function ForgotPasswordPage() {
  const status = useQuery({ queryKey: ['reset-status'], queryFn: resetStatus, retry: false })
  const [email, setEmail] = useState('')
  const { t } = useT()
  const [err, setErr] = useState<string>()
  const [done, setDone] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) { setErr(t('Enter a valid email address.')); return }
    setBusy(true); setErr(undefined)
    try { setDone(translateServer((await forgotPassword(email.trim())).detail)) } catch (e2) { setErr(errorMessage(e2)) } finally { setBusy(false) }
  }

  return (
    <AuthShell title={t('Reset your password')} subtitle={t('We will e-mail you a single-use link.')}
      footer={<Link to="/login" className="font-medium text-primary hover:underline">{t('Back to sign in')}</Link>}>
      {status.isLoading ? <Loader2 className="mx-auto size-5 animate-spin text-primary" aria-label={t('Loading')} />
        : status.data?.email_reset_available === false ? (
          <div role="status" className="rounded-lg border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
            {t('E-mail password reset is not set up on this server (it needs SMTP settings). Ask an administrator for a reset link: they can create one on the Administration page.')}
          </div>
        ) : done ? <div role="status" className="rounded-lg border border-success/30 bg-success/10 p-4 text-sm text-success">{done}</div>
        : (
          <form onSubmit={submit} noValidate className="space-y-4">
            {status.isError && <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{errorMessage(status.error)}</div>}
            <Field label={t('Email')} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={err} autoFocus />
            <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />}{t('Send reset link')}</Button>
          </form>)}
    </AuthShell>
  )
}
