const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const TIMES = [
  { key: 'morning',   label: 'Morning',   sub: '6am–12pm' },
  { key: 'afternoon', label: 'Afternoon', sub: '12pm–6pm' },
  { key: 'evening',   label: 'Evening',   sub: '6pm–12am' },
  { key: 'night',     label: 'Night',     sub: '12am–6am' },
]

const CATEGORIES = [
  'Motor Vehicle Theft',
  'Larceny - From Vehicle',
  'Burglary',
  'Robbery',
  'Assault',
]

function toggle(arr, val) {
  return arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]
}

const VIEW_MODES = [
  { key: 'cluster',  label: 'Cluster'  },
  { key: 'heatmap',  label: 'Heatmap'  },
]

export default function Sidebar({ filters, setFilters, viewMode, setViewMode }) {
  const set = (key, val) => setFilters(f => ({ ...f, [key]: val }))

  return (
    <aside className="w-56 flex-shrink-0 bg-[#1a1d27] border-r border-[#2a2d3a] overflow-y-auto p-4 space-y-6">
      <div>
        <h1 className="text-lg font-bold tracking-wide text-white">AutoShield</h1>
        <p className="text-xs text-slate-500 mt-0.5">SF Crime Patterns</p>
      </div>

      {/* View mode toggle */}
      <div className="flex rounded overflow-hidden border border-[#2a2d3a]">
        {VIEW_MODES.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setViewMode(key)}
            className={`flex-1 text-xs py-1.5 transition-colors ${
              viewMode === key
                ? 'bg-blue-600 text-white'
                : 'bg-[#0f1117] text-slate-400 hover:bg-[#2a2d3a]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Date range */}
      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
          Date Range
        </label>
        <select
          value={filters.dateRange}
          onChange={e => set('dateRange', e.target.value)}
          className="w-full bg-[#0f1117] border border-[#2a2d3a] rounded px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-slate-500"
        >
          <option value="1month">Last 1 month</option>
          <option value="3months">Last 3 months</option>
          <option value="1year">Last 1 year</option>
        </select>
      </div>

      {/* Day of week */}
      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
          Day of Week
        </label>
        <div className="grid grid-cols-4 gap-1">
          {DAYS.map((day, i) => {
            const active = filters.daysOfWeek.includes(day)
            return (
              <button
                key={day}
                onClick={() => set('daysOfWeek', toggle(filters.daysOfWeek, day))}
                className={`text-xs py-1 rounded transition-colors ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-[#0f1117] text-slate-400 hover:bg-[#2a2d3a]'
                }`}
              >
                {DAY_LABELS[i]}
              </button>
            )
          })}
        </div>
      </div>

      {/* Time of day */}
      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
          Time of Day
        </label>
        <div className="space-y-1">
          {TIMES.map(({ key, label, sub }) => {
            const active = filters.timeOfDay.includes(key)
            return (
              <button
                key={key}
                onClick={() => set('timeOfDay', toggle(filters.timeOfDay, key))}
                className={`w-full flex justify-between items-center text-xs px-2 py-1.5 rounded transition-colors ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-[#0f1117] text-slate-400 hover:bg-[#2a2d3a]'
                }`}
              >
                <span>{label}</span>
                <span className="opacity-60">{sub}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Categories */}
      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
          Category
        </label>
        <div className="space-y-1">
          {CATEGORIES.map(cat => {
            const active = filters.categories.includes(cat)
            return (
              <label key={cat} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => set('categories', toggle(filters.categories, cat))}
                  className="accent-blue-500"
                />
                {cat}
              </label>
            )
          })}
        </div>
        {filters.categories.length === 0 && (
          <p className="text-xs text-slate-600 italic">Showing vehicle crime</p>
        )}
      </div>

      {/* Reset */}
      <button
        onClick={() => setFilters({
          dateRange: '3months',
          daysOfWeek: [],
          timeOfDay: [],
          categories: [],
        })}
        className="w-full text-xs text-slate-500 hover:text-slate-300 py-1 border border-[#2a2d3a] rounded transition-colors"
      >
        Reset filters
      </button>
    </aside>
  )
}
