import { useMutation } from '@tanstack/react-query'
import { Check, Copy, Link2, QrCode, RefreshCw } from 'lucide-react'
import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useT } from '@/i18n'
import { errorMessage } from '@/services/api'
import { setCollection } from '@/services/collect'
import type { DatasetSummary } from '@/types/datasets'

/** Public collection link (collect.ekyc.mn-style): participants record themselves or a spoof attempt, no account. */
export function CollectLinkCard({ dataset, onChange }: { dataset: DatasetSummary; onChange: () => void }) {
  const { t } = useT()
  const col = dataset.collect
  const url = col?.enabled && col.token ? `${window.location.origin}/collect/${col.token}` : null
  const [qr, setQr] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [confirmRotate, setConfirmRotate] = useState(false)
  const m = useMutation({
    mutationFn: (v: { enabled: boolean; rotate?: boolean }) => setCollection(dataset.id, v.enabled, v.rotate),
    onSuccess: (_, v) => { toast.success(v.enabled ? (v.rotate ? t('New link created. The old link no longer works.') : t('Collection link is on.')) : t('Collection link is off.')); setConfirmRotate(false); onChange() },
    onError: (e) => toast.error(errorMessage(e)),
  })
  useEffect(() => {
    if (!url) { setQr(null); return }
    QRCode.toDataURL(url, { margin: 1, width: 220 }).then(setQr).catch(() => setQr(null))
  }, [url])
  async function copy() {
    if (!url) return
    try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { toast.error(t('Copy failed. Select the link manually.')) }
  }
  return (
    <Card>
      <CardHeader title={t('Collection link')}
        description={t('Share this link: participants choose Real or Fake and record themselves with their phone camera, without an account. Frames are added here with the label, a pseudonymous person ID and the attack type.')} />
      <div className="space-y-4 p-5">
        {!url ? (
          <Button onClick={() => m.mutate({ enabled: true })} disabled={m.isPending}><Link2 className="size-4" />{t('Turn on collection link')}</Button>
        ) : (
          <div className="flex flex-col gap-4 sm:flex-row">
            {qr ? <img src={qr} alt={t('QR code for the collection link')} className="size-36 shrink-0 rounded-lg border border-border bg-white p-1" />
              : <div className="grid size-36 place-items-center rounded-lg border border-border"><QrCode className="size-6 text-muted" /></div>}
            <div className="min-w-0 flex-1 space-y-3">
              <div className="flex gap-2">
                <input readOnly value={url} aria-label={t('Collection link')} onFocus={(e) => e.target.select()} className="h-9 min-w-0 flex-1 rounded-lg border border-border bg-bg px-2.5 font-mono text-xs" />
                <Button variant="outline" size="sm" onClick={() => void copy()}>{copied ? <Check className="size-4" /> : <Copy className="size-4" />}{copied ? t('Copied') : t('Copy')}</Button>
              </div>
              <p className="text-xs text-muted">{t('{n} participants so far. Scan the QR code with a phone to open the link.', { n: col?.participants ?? 0 })}</p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => setConfirmRotate(true)} disabled={m.isPending}><RefreshCw className="size-4" />{t('New link')}</Button>
                <Button variant="ghost" size="sm" onClick={() => m.mutate({ enabled: false })} disabled={m.isPending}>{t('Turn off')}</Button>
              </div>
            </div>
          </div>
        )}
        <p className="text-xs text-muted">{t('Anyone with the link can add recordings to this dataset (nothing else). Turn it off when you have enough data. The camera only works over HTTPS.')}</p>
      </div>
      <ConfirmDialog open={confirmRotate} onOpenChange={setConfirmRotate} title={t('Create a new link?')}
        description={t('The current link stops working immediately. Recordings already collected are kept.')} confirmLabel={t('New link')}
        busy={m.isPending} onConfirm={() => m.mutate({ enabled: true, rotate: true })} />
    </Card>
  )
}
