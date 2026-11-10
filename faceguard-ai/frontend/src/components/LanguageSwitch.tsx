import { Languages } from 'lucide-react'
import { LANGS, useT } from '@/i18n'
import { cn } from '@/utils/cn'

/** Two-option segmented switch (МН / EN). The choice is remembered in this browser. */
export function LanguageSwitch({ className }: { className?: string }) {
  const { lang, setLang, t } = useT()
  return (
    <div role="group" aria-label={t('Language')} className={cn('flex items-center gap-0.5 rounded-full border border-border bg-card p-0.5 text-xs', className)}>
      <Languages className="ml-1.5 mr-0.5 hidden size-3.5 text-muted sm:block" aria-hidden />
      {LANGS.map((l) => (
        <button key={l.code} type="button" lang={l.code} title={l.label} aria-pressed={lang === l.code} onClick={() => setLang(l.code)}
          className={cn('rounded-full px-2 py-1 font-medium transition-colors', lang === l.code ? 'bg-primary text-bg' : 'text-muted hover:text-fg')}>
          {l.short}
        </button>
      ))}
    </div>
  )
}
