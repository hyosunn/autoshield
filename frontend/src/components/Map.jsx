import { useEffect } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, Marker, useMap } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import 'react-leaflet-cluster/dist/assets/MarkerCluster.css'
import 'react-leaflet-cluster/dist/assets/MarkerCluster.Default.css'
import L from 'leaflet'
import 'leaflet.heat'

const CATEGORY_COLOR = {
  'Motor Vehicle Theft': '#ef4444',
  'Larceny - From Vehicle': '#f97316',
}

function markerColor(subcategory) {
  return CATEGORY_COLOR[subcategory] || '#eab308'
}

function HeatmapLayer({ incidents }) {
  const map = useMap()

  useEffect(() => {
    const points = incidents
      .map(inc => {
        const lat = parseFloat(inc.latitude)
        const lng = parseFloat(inc.longitude)
        return isNaN(lat) || isNaN(lng) ? null : [lat, lng, 1]
      })
      .filter(Boolean)

    const layer = L.heatLayer(points, { radius: 25, blur: 15, maxZoom: 17 })
    layer.addTo(map)
    return () => map.removeLayer(layer)
  }, [incidents, map])

  return null
}

function IncidentPopup({ inc }) {
  return (
    <Popup>
      <div className="text-sm space-y-1">
        <p className="font-semibold">{inc.incident_subcategory}</p>
        <p className="text-gray-400">{inc.incident_category}</p>
        <p>{inc.incident_date} · {inc.incident_time}</p>
        <p>{inc.incident_day_of_week}</p>
      </div>
    </Popup>
  )
}

export default function Map({ incidents, viewMode = 'cluster' }) {
  return (
    <MapContainer
      center={[37.77, -122.41]}
      zoom={12}
      style={{ height: '100%', width: '100%' }}
      zoomControl={true}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        subdomains="abcd"
        maxZoom={19}
      />

      {viewMode === 'cluster' && (
        <MarkerClusterGroup key={`cluster-${viewMode}`} chunkedLoading>
          {incidents.map((inc, idx) => {
            const lat = parseFloat(inc.latitude)
            const lng = parseFloat(inc.longitude)
            if (isNaN(lat) || isNaN(lng)) return null
            return (
              <Marker key={idx} position={[lat, lng]}>
                <IncidentPopup inc={inc} />
              </Marker>
            )
          })}
        </MarkerClusterGroup>
      )}

      {viewMode === 'heatmap' && <HeatmapLayer incidents={incidents} />}
    </MapContainer>
  )
}
