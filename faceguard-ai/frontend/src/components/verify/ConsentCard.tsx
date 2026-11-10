import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useT } from '@/i18n'

/** Explicit, informed consent. Nothing is captured or sent until the user ticks the box and confirms. */
export function ConsentCard({ action, onConsent, disabled }: { action: string; onConsent: () => void; disabled?: boolean }) {
  const { t } = useT()
  const [checked, setChecked] = useState(false)
  return (
    <Card className="p-5">
      <div className="flex gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"><ShieldCheck className="size-5" /></div>
        <div className="space-y-3">
          <p className="text-sm font-medium">{t('Before we analyse your face')}</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            <li>{t('Images are analysed on the server to find a face and check quality. They are not saved.')}</li>
            <li>{t('Only the result is stored: status, quality measurements, time and your user account.')}</li>
            <li>{t('No biometric template or face embedding is created or kept.')}</li>
            <li>{t('Results support human review and are not a standalone decision.')}</li>
          </ul>
          <label className="flex cursor-pointer items-start gap-2.5 text-sm">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} className="mt-0.5 size-4 accent-[#22D3EE]" />
            <span>{t('I consent to this analysis of my face image or video.')}</span>
          </label>
          <Button disabled={!checked || disabled} onClick={onConsent}>{action}</Button>
        </div>
      </div>
    </Card>
  )
}
