import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { SeriesPoint, Period } from '@/types/history'
import { useChartColors } from './chartTheme'
import { useT } from '@/i18n'
import { formatDay, formatMonth } from '@/utils/format'

const label = (iso: string, period: Period) => (period === 'month' ? formatMonth(iso) : formatDay(iso))

export function SeriesChart({ data, period }: { data: SeriesPoint[]; period: Period }) {
  const { t } = useT()
  const c = useChartColors()
  return (
    <div className="h-72 w-full" role="img" aria-label={t('Verification outcomes over time')}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={c.grid} />
          <XAxis dataKey="bucket" tickFormatter={(v) => label(String(v), period)} stroke={c.axis} fontSize={12} tickLine={false} axisLine={false} minTickGap={16} />
          <YAxis allowDecimals={false} stroke={c.axis} fontSize={12} tickLine={false} axisLine={false} />
          <Tooltip {...c.tooltip} labelFormatter={(v) => label(String(v), period)} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="real" name={t('Real')} stackId="a" fill={c.real} />
          <Bar dataKey="fake" name={t('Fake')} stackId="a" fill={c.fake} />
          <Bar dataKey="uncertain" name={t('Uncertain')} stackId="a" fill={c.uncertain} />
          <Bar dataKey="failed" name={t('Failed')} stackId="a" fill={c.failed} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
