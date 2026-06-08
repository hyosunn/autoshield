import { useState, useEffect } from 'react'
import axios from 'axios'
import Map from './components/Map'
import Sidebar from './components/Sidebar'
import StatsBar from './components/StatsBar'
import TrendChart from './components/TrendChart'

const DEFAULT_FILTERS = {
  dateRange: '3months',
  daysOfWeek: [],
  timeOfDay: [],
  categories: [],
}

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [viewMode, setViewMode] = useState('cluster')

  useEffect(() => {
    const fetchIncidents = async () => {
      setLoading(true)
      setError(null)
      try {
        const params = new URLSearchParams()
        params.set('date_range', filters.dateRange)
        filters.daysOfWeek.forEach(d => params.append('days', d))
        filters.timeOfDay.forEach(t => params.append('times', t))
        filters.categories.forEach(c => params.append('categories', c))

        const res = await axios.get(`/api/incidents?${params.toString()}`)
        if (res.data.error) throw new Error(res.data.error)
        setIncidents(res.data)
      } catch (err) {
        setError(err.message || 'Failed to load incident data.')
        setIncidents([])
      } finally {
        setLoading(false)
      }
    }

    fetchIncidents()
  }, [filters])

  return (
    <div className="flex flex-col h-screen bg-[#0f1117] text-slate-200 overflow-hidden">
      {/* Top stats bar */}
      <StatsBar incidents={incidents} loading={loading} />

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <Sidebar filters={filters} setFilters={setFilters} viewMode={viewMode} setViewMode={setViewMode} />

        {/* Main content: map + chart */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {error && (
            <div className="bg-red-900/60 border border-red-700 text-red-200 text-sm px-4 py-2">
              ⚠ {error}
            </div>
          )}
          {loading && (
            <div className="bg-[#1a1d27] border-b border-[#2a2d3a] text-slate-400 text-xs px-4 py-1">
              Loading incident data…
            </div>
          )}

          {/* Map takes up most of the space */}
          <div className="flex-1 min-h-0">
            <Map incidents={incidents} viewMode={viewMode} />
          </div>

          {/* Trend chart below map */}
          <div className="h-44 border-t border-[#2a2d3a] bg-[#1a1d27]">
            <TrendChart incidents={incidents} />
          </div>
        </div>
      </div>
    </div>
  )
}
