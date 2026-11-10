import { EyeOff, ShieldCheck, UserCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Logo } from '@/components/Logo'
import { useT } from '@/i18n'
import { LanguageSwitch } from '@/components/LanguageSwitch'

const points = [
  { icon: ShieldCheck, title: 'Liveness is its own check', text: 'Face detection, identity and liveness are separate modules. A detected face is never treated as proof of a live person.' },
  { icon: EyeOff, title: 'Metadata, not faces', text: 'Raw images and videos are not kept by default, and no biometric templates are stored.' },
  { icon: UserCheck, title: 'Built for human review', text: 'Results support a reviewer. They are not a basis for high-impact decisions on their own.' },
]

export function AuthShell({ title, subtitle, children, footer }:
  { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  const { t } = useT()
  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <aside className="relative hidden overflow-hidden border-r border-border bg-sidebar p-12 lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="pointer-events-none absolute -left-24 -top-24 size-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex items-center justify-between"><Logo /><LanguageSwitch /></div>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">{t('Know whether a real person is in front of the camera.')}</h2>
          <ul className="mt-10 space-y-6">
            {points.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <div className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-card text-primary"><Icon className="size-4" /></div>
                <div><p className="text-sm font-medium">{t(title)}</p><p className="mt-0.5 text-sm leading-relaxed text-muted">{t(text)}</p></div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-muted/70">{t('FaceGuard AI · Presentation attack detection platform')}</p>
      </aside>
      <main className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center justify-between lg:hidden"><Logo /><LanguageSwitch /></div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1.5 text-sm text-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 text-center text-sm text-muted">{footer}</p>
        </div>
      </main>
    </div>
  )
}
