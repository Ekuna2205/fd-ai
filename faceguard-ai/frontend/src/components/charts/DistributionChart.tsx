import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useChartColors } from './chartTheme'
import { useT } from '@/i18n'

export function DistributionChart({ real, fake, uncertain }: { real: number; fake: number; uncertain: number }) {
  const c = useChartColors()
  const { t } = useT()
  const rows = [
    { name: t('Real'), value: real, color: c.real },
    { name: t('Fake'), value: fake, color: c.fake },
    { name: t('Uncertain'), value: uncertain, color: c.uncertain },
  ]
  return (
    <div>
      <div className="h-44">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={rows} dataKey="value" nameKey="name" innerRadius={50} outerRadius={72} paddingAngle={2} stroke="none">
              {rows.map((r) => <Cell key={r.name} fill={r.color} />)}
            </Pie>
            <Tooltip {...c.tooltip} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-2 space-y-1.5 text-sm">
        {rows.map((r) => (
          <li key={r.name} className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-muted"><span className="size-2 rounded-full" style={{ background: r.color }} />{r.name}</span>
            <span className="tabular-nums">{r.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
