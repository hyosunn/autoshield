import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, LabelList } from 'recharts'

const CATEGORY_COLOR = {
  'Motor Vehicle Theft': '#ef4444',
  'Larceny - From Vehicle': '#f97316',
}

const MONTH_LABELS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function formatMonthKey(key) {
  const [, month] = key.split('-')
  return MONTH_LABELS[parseInt(month, 10) - 1]
}

function dominantCategory(incidents) {
  const counts = {}
  for (const inc of incidents) {
    const cat = inc.incident_subcategory || inc.incident_category || 'Other'
    counts[cat] = (counts[cat] || 0) + 1
  }
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'Other'
}

export default function TrendChart({ incidents }) {
  const byMonth = incidents.reduce((acc, inc) => {
    const d = new Date(inc.incident_date)
    if (isNaN(d)) return acc
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    if (!acc[key]) acc[key] = []
    acc[key].push(inc)
    return acc
  }, {})

  const data = Object.entries(byMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, incs]) => ({
      month: formatMonthKey(key),
      count: incs.length,
      color: CATEGORY_COLOR[dominantCategory(incs)] || '#eab308',
    }))

  if (data.length < 2) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-slate-600">
        Not enough data for trend view
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 12, right: 16, left: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" vertical={false} />
        <XAxis
          dataKey="month"
          tick={{ fill: '#64748b', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={48}
          label={{ value: 'Incidents', angle: -90, position: 'insideLeft', offset: 8, fill: '#64748b', fontSize: 10 }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: '#94a3b8' }}
          itemStyle={{ color: '#e2e8f0' }}
          cursor={{ fill: '#2a2d3a' }}
          formatter={(val) => [val, 'Incidents']}
        />
        <Bar dataKey="count" radius={[2, 2, 0, 0]}>
          {data.map((entry, idx) => (
            <Cell key={idx} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
