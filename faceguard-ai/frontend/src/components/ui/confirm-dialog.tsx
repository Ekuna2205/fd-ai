import * as Dialog from '@radix-ui/react-dialog'
import { Loader2 } from 'lucide-react'
import { Button } from './button'
import { useT } from '@/i18n'

/** Accessible confirmation for destructive actions (focus trap, Esc to close, labelled by title). */
export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel, busy, onConfirm }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description: string
  confirmLabel?: string; busy?: boolean; onConfirm: () => void
}) {
  const { t } = useT()
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 shadow-xl">
          <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
          <Dialog.Description className="mt-2 text-sm text-muted">{description}</Dialog.Description>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>{t('Cancel')}</Button>
            <Button variant="danger" onClick={onConfirm} disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />}{confirmLabel ?? t('Delete')}</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
