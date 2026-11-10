import { Check } from 'lucide-react'
import { cn } from '@/utils/cn'
import { useT } from '@/i18n'

// Keep in sync with backend schemas/auth.py::validate_password_strength.
export const passwordRules = [
  { label: 'At least 10 characters', test: (p: string) => p.length >= 10 },
  { label: 'A letter', test: (p: string) => /[A-Za-z]/.test(p) },
  { label: 'A number', test: (p: string) => /\d/.test(p) },
]
export const passwordOk = (p: string) => passwordRules.every((r) => r.test(p))

export function PasswordRules({ value }: { value: string }) {
  const { t } = useT()
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label={t('Password requirements')}>
      {passwordRules.map((r) => { const ok = r.test(value); return <li key={r.label} className={cn('flex items-center gap-1', ok ? 'text-success' : 'text-muted')}><Check className={cn('size-3', !ok && 'opacity-30')} />{t(r.label)}</li> })}
    </ul>
  )
}
