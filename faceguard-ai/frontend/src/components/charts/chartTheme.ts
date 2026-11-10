import { useTheme } from '@/hooks/useTheme'

const css = (name: string, fallback: string) =>
  (typeof document !== 'undefined' && getComputedStyle(document.documentElement).getPropertyValue(name).trim()) || fallback

/** Chart colours that follow the active theme. Semantic colours (real/fake/uncertain) stay fixed on purpose. */
export function useChartColors() {
  useTheme() // re-render charts when the theme changes
  return {
    real: '#10B981', fake: '#EF4444', uncertain: '#F59E0B', failed: '#94A3B8',
    primary: css('--color-primary', '#22D3EE'), secondary: css('--color-secondary', '#3B82F6'),
    grid: css('--color-border', '#1E2B44'), axis: css('--color-muted', '#94A3B8'),
    tooltip: {
      contentStyle: { background: css('--color-card', '#111B2D'), border: `1px solid ${css('--color-border', '#1E2B44')}`, borderRadius: 8, fontSize: 12, color: css('--color-fg', '#F8FAFC') },
      labelStyle: { color: css('--color-muted', '#94A3B8') }, itemStyle: { color: css('--color-fg', '#F8FAFC') },
      cursor: { fill: 'rgba(148,163,184,0.12)' },
    },
  }
}
