import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/hooks/useTheme'
import { useT } from '@/i18n'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const { t } = useT()
  const next = theme === 'dark' ? 'light' : 'dark'
  const label = next === 'light' ? t('Switch to light theme') : t('Switch to dark theme')
  return (
    <Button variant="ghost" size="icon" onClick={() => setTheme(next)} aria-label={label} title={label}>
      {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  )
}
