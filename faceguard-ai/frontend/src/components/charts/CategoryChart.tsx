import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DashboardOverview } from '@/types/dashboard'
import { useChartColors } from './chartTheme'
import { useT } from '@/i18n'
import { spoofLabel } from '@/i18n/labels'


export function CategoryChart({ data }: { data: DashboardOverview['spoof_categories'] }) {
  const c = useChartColors()
  const { t } = useT()
  const rows = data.map((d) => ({ ...d, category: spoofLabel(d.category) }))
  return (
    <div className="h-52 w-full">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 8, left: 8, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke={c.grid} />
          <XAxis type="number" allowDecimals={false} stroke={c.axis} fontSize={12} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey="category" width={110} stroke={c.axis} fontSize={12} tickLine={false} axisLine={false} />
          <Tooltip {...c.tooltip} />
          <Bar dataKey="count" name={t('Attempts')} fill={c.secondary} radius={[0, 4, 4, 0]} barSize={14} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
