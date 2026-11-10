import { AnimatePresence, motion } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { HealthPill } from '@/components/HealthPill'
import { Logo } from '@/components/Logo'
import { UserMenu } from '@/components/UserMenu'
import { visibleGroups } from '@/components/nav'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'
import { cn } from '@/utils/cn'
import { useT } from '@/i18n'
import { LanguageSwitch } from '@/components/LanguageSwitch'

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth()
  const { t } = useT()
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5"><Logo /></div>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6" aria-label={t('Main')}>
        {visibleGroups(user?.role).map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-1.5 text-xs font-medium text-muted/70">{t(group.label)}</p>
            <ul className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink to={to} end={to === '/'} onClick={onNavigate}
                    className={({ isActive }) => cn(
                      'relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                      isActive ? 'text-fg' : 'text-muted hover:bg-card-hover/60 hover:text-fg',
                    )}>
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <motion.span layoutId="nav-active" className="absolute inset-0 rounded-lg bg-card ring-1 ring-border"
                            transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
                        )}
                        {isActive && <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-primary" />}
                        <Icon className={cn('relative size-4', isActive && 'text-primary')} />
                        <span className="relative flex-1">{t(label)}</span>
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <p className="border-t border-border px-5 py-4 text-xs leading-relaxed text-muted/80">
        {t('Results support human review. They are not a standalone basis for high-impact decisions.')}
      </p>
    </div>
  )
}

export default function AppLayout() {
  const [open, setOpen] = useState(false)
  const { t } = useT()
  const { pathname } = useLocation()
  useEffect(() => setOpen(false), [pathname])

  return (
    <div className="flex h-full">
      <aside className="hidden w-64 shrink-0 border-r border-border bg-sidebar lg:block">
        <SidebarContent />
      </aside>

      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.div className="absolute inset-0 bg-black/60" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} />
            <motion.aside role="dialog" aria-modal="true" aria-label={t('Navigation')}
              className="absolute inset-y-0 left-0 w-72 border-r border-border bg-sidebar"
              initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }} transition={{ type: 'tween', duration: 0.2 }}>
              <Button variant="ghost" size="icon" className="absolute right-3 top-4" onClick={() => setOpen(false)} aria-label={t('Close menu')}>
                <X className="size-4" />
              </Button>
              <SidebarContent onNavigate={() => setOpen(false)} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label={t('Open menu')}>
              <Menu className="size-5" />
            </Button>
            <div className="lg:hidden"><Logo compact /></div>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-3">
            <HealthPill />
            <LanguageSwitch />
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8"><Outlet /></div>
        </main>
      </div>
    </div>
  )
}
