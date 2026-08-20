import { useEffect, useState } from 'react'
import { GeoJSON } from 'react-leaflet'
import axios from 'axios'

// Risk color scale: green (low) -> yellow (mid) -> red (high), matching
// the 0-100 percentile scores returned by /api/neighborhoods.
const COLOR_STOPS = [
  { score: 0,   color: [34, 197, 94] },
  { score: 50,  color: [234, 179, 8] },
  { score: 100, color: [239, 68, 68] },
]

function lerp(a, b, t) {
  return a + (b - a) * t
}

function riskColor(score) {
  const s = Math.max(0, Math.min(100, score ?? 0))
  const [lo, hi] = s <= 50 ? [COLOR_STOPS[0], COLOR_STOPS[1]] : [COLOR_STOPS[1], COLOR_STOPS[2]]
  const span = hi.score - lo.score
  const t = span === 0 ? 0 : (s - lo.score) / span
  const rgb = lo.color.map((c, i) => Math.round(lerp(c, hi.color[i], t)))
  return `rgb(${rgb.join(',')})`
}

const SCORE_FIELD = {
  parking: 'parking_risk_score',
  pedestrian: 'pedestrian_risk_score',
}

const AXIS_LABEL = {
  parking: 'Parking',
  pedestrian: 'Pedestrian',
}

export default function NeighborhoodLayer({ axis }) {
  const [geojson, setGeojson] = useState(null)

  useEffect(() => {
    let cancelled = false
    axios.get('/api/neighborhoods')
      .then(res => { if (!cancelled) setGeojson(res.data) })
      .catch(err => console.error('Failed to load neighborhood risk data:', err.message))
    return () => { cancelled = true }
  }, [])

  if (!geojson) return null

  const scoreField = SCORE_FIELD[axis] ?? SCORE_FIELD.parking

  const style = feature => {
    const lowSample = feature.properties.low_sample
    return {
      color: '#0f1117',
      weight: 1,
      fillColor: riskColor(feature.properties[scoreField]),
      // Low-sample neighborhoods are shown with reduced confidence rather
      // than hidden — see docs/risk-scoring-design.md.
      fillOpacity: lowSample ? 0.25 : 0.55,
      dashArray: lowSample ? '4' : null,
    }
  }

  const onEachFeature = (feature, layer) => {
    const { name, low_sample } = feature.properties
    const score = feature.properties[scoreField]
    layer.bindTooltip(
      `<div class="text-xs">
        <div class="font-semibold">${name}</div>
        <div>${AXIS_LABEL[axis] ?? 'Parking'} risk: ${Number(score).toFixed(1)}</div>
        ${low_sample ? '<div class="italic opacity-70">Low sample size</div>' : ''}
      </div>`,
      { sticky: true }
    )
  }

  // key={axis} forces a remount on toggle — react-leaflet's GeoJSON layer
  // doesn't re-run style()/onEachFeature() on prop changes after mount.
  return (
    <GeoJSON
      key={axis}
      data={geojson}
      style={style}
      onEachFeature={onEachFeature}
    />
  )
}
