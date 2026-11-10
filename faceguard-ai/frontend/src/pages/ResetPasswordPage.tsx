import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AuthShell } from '@/components/AuthShell'
import { PasswordRules, passwordOk } from '@/components/PasswordRules'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/input'
import { errorMessage, fieldErrors } from '@/services/api'
import { resetPassword } from '@/services/auth'
import { useT } from '@/i18n'

export default function ResetPasswordPage() {
  const token = useSearchParams()[0].get('token') ?? ''
  const [pw, setPw] = useState('')
  const { t } = useT()
  const [confirm, setConfirm] = useState('')
  const [errs, setErrs] = useState<Record<string, string>>({})
  const [formErr, setFormErr] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const n: Record<string, string> = {}
    if (!passwordOk(pw)) n.pw = t('Password does not meet the requirements.')
    if (confirm !== pw) n.confirm = t('Passwords do not match.')
    setErrs(n); setFormErr(null)
    if (Object.keys(n).length) return
    setBusy(true)
    try { await resetPassword(token, pw); setDone(true) }
    catch (e2) { const fe = fieldErrors(e2); setErrs(fe.new_password ? { pw: fe.new_password } : {}); setFormErr(errorMessage(e2)) } finally { setBusy(false) }
  }

  return (
    <AuthShell title={t('Choose a new password')} subtitle={t('The link works once and expires soon.')}
      footer={<Link to="/login" className="font-medium text-primary hover:underline">{t('Back to sign in')}</Link>}>
      {!token ? <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{t('This reset link is incomplete. Request a new one from the sign-in page.')}</div>
        : done ? <div role="status" className="space-y-3 rounded-lg border border-success/30 bg-success/10 p-4 text-sm text-success"><p>{t('Your password has been changed.')}</p><Button asChild><Link to="/login">{t('Sign in')}</Link></Button></div>
        : (
          <form onSubmit={submit} noValidate className="space-y-4">
            {formErr && <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{formErr}</div>}
            <div><Field label={t('New password')} type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} error={errs.pw} autoFocus /><PasswordRules value={pw} /></div>
            <Field label={t('Confirm new password')} type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} error={errs.confirm} />
            <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />}{t('Change password')}</Button>
          </form>)}
    </AuthShell>
  )
}
