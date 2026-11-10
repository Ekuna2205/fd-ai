import * as Dialog from '@radix-ui/react-dialog'
import { useMutation } from '@tanstack/react-query'
import { Check, Copy, KeyRound, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/services/api'
import { createResetLink, type ResetLink } from '@/services/users'
import type { AuthUser } from '@/types/auth'
import { formatDateTime } from '@/utils/format'
import { useT } from '@/i18n'

/** Administrator creates a one-time reset link for a user who forgot their password. The link is shown once. */
export function ResetLinkDialog({ user, onClose }: { user: AuthUser | null; onClose: () => void }) {
  const { t } = useT()
  const [signOut, setSignOut] = useState(false)
  const [link, setLink] = useState<ResetLink | null>(null)
  const [copied, setCopied] = useState(false)
  const create = useMutation({
    mutationFn: () => createResetLink(user!.id, signOut),
    onSuccess: setLink,
    onError: (e) => toast.error(errorMessage(e)),
  })
  const url = link ? `${window.location.origin}${link.path}` : ''
  function close() { setLink(null); setSignOut(false); setCopied(false); onClose() }
  async function copy() {
    try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { toast.error(t('Copy failed. Select the link manually.')) }
  }
  return (
    <Dialog.Root open={!!user} onOpenChange={(o) => !o && !create.isPending && close()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 shadow-xl">
          <Dialog.Title className="flex items-center gap-2 text-base font-semibold"><KeyRound className="size-4 text-primary" />{t('Password reset link')}</Dialog.Title>
          {!link ? <>
            <Dialog.Description className="mt-2 text-sm text-muted">
              {t('Creates a one-time link for {name} ({email}) to choose a new password. You never see or set their password. Any earlier link stops working.', { name: user?.full_name, email: user?.email })}
            </Dialog.Description>
            <label className="mt-4 flex cursor-pointer items-start gap-2.5 text-sm">
              <input type="checkbox" checked={signOut} onChange={(e) => setSignOut(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-primary)]" />
              <span>{t('Also sign them out on every device')}<span className="block text-xs text-muted">{t('Use this if the account may be compromised.')}</span></span>
            </label>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={close} disabled={create.isPending}>{t('Cancel')}</Button>
              <Button onClick={() => create.mutate()} disabled={create.isPending}>{create.isPending && <Loader2 className="size-4 animate-spin" />}{t('Create link')}</Button>
            </div>
          </> : <>
            <Dialog.Description className="mt-2 text-sm text-muted">
              {t('Send this link to {name} over a channel you trust. It works once and expires {when}.', { name: user?.full_name, when: formatDateTime(link.expires_at) })}{link.signed_out ? ` ${t('Their sessions have been ended.')}` : ''} {t('It will not be shown again.')}
            </Dialog.Description>
            <div className="mt-4 flex gap-2">
              <input readOnly value={url} aria-label={t('Reset link')} onFocus={(e) => e.target.select()} className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 font-mono text-xs" />
              <Button variant="outline" onClick={() => void copy()}>{copied ? <Check className="size-4" /> : <Copy className="size-4" />}{copied ? t('Copied') : t('Copy')}</Button>
            </div>
            <div className="mt-6 flex justify-end"><Button onClick={close}>{t('Done')}</Button></div>
          </>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
