const COLORS = {
  'Motor Vehicle Theft': 'text-red-400',
  'Larceny - From Vehicle': 'text-orange-400',
}

export default function StatsBar({ incidents, loading }) {
  // Tally by subcategory
  const counts = incidents.reduce((acc, inc) => {
    const key = inc.incident_subcategory || 'Unknown'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})

  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 4)

  return (
    <div className="flex items-center gap-6 px-4 py-2 bg-[#1a1d27] border-b border-[#2a2d3a] text-sm flex-shrink-0">
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-white">
          {loading ? '—' : incidents.length.toLocaleString()}
        </span>
        <span className="text-xs text-slate-500">incidents</span>
      </div>

      <div className="w-px h-6 bg-[#2a2d3a]" />

      <div className="flex gap-5">
        {sorted.map(([cat, count]) => (
          <div key={cat} className="flex items-baseline gap-1">
            <span className={`font-semibold ${COLORS[cat] || 'text-yellow-400'}`}>
              {count.toLocaleString()}
            </span>
            <span className="text-xs text-slate-500 max-w-[120px] truncate">{cat}</span>
          </div>
        ))}
      </div>

      {loading && (
        <span className="ml-auto text-xs text-slate-600 animate-pulse">Fetching data…</span>
      )}
    </div>
  )
}
