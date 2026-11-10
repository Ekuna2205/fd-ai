import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DashboardOverview } from '@/types/dashboard'
import { formatDay } from '@/utils/format'
import { useChartColors } from './chartTheme'
import { useT } from '@/i18n'

export function DailyChart({ data }: { data: DashboardOverview['daily'] }) {
  const c = useChartColors()
  const { t } = useT()
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={c.grid} />
          <XAxis dataKey="date" tickFormatter={formatDay} stroke={c.axis} fontSize={12} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} stroke={c.axis} fontSize={12} tickLine={false} axisLine={false} />
          <Tooltip {...c.tooltip} labelFormatter={(l) => formatDay(String(l))} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="real" name={t('Real')} stackId="a" fill={c.real} />
          <Bar dataKey="fake" name={t('Fake')} stackId="a" fill={c.fake} />
          <Bar dataKey="uncertain" name={t('Uncertain')} stackId="a" fill={c.uncertain} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
