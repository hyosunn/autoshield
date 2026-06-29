import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Popup, Marker, useMap } from 'react-leaflet'
import _MarkerClusterGroup from '@changey/react-leaflet-markercluster'
const MarkerClusterGroup = _MarkerClusterGroup.default ?? _MarkerClusterGroup
import '@changey/react-leaflet-markercluster/dist/styles.min.css'
import L from 'leaflet'
import 'leaflet.heat'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

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

function HeatmapController({ viewMode, incidents }) {
  const map = useMap()
  const heatLayerRef = useRef(null)

  useEffect(() => {
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current)
      heatLayerRef.current = null
    }

    if (viewMode !== 'heatmap') return

    const addHeatLayer = () => {
      const container = map.getContainer()
      if (!container.offsetWidth || !container.offsetHeight) return

      const points = incidents
        .map(inc => {
          const lat = parseFloat(inc.latitude)
          const lng = parseFloat(inc.longitude)
          return isNaN(lat) || isNaN(lng) ? null : [lat, lng, 1]
        })
        .filter(Boolean)

      try {
        heatLayerRef.current = L.heatLayer(points, { radius: 25, blur: 15, maxZoom: 17 })
        heatLayerRef.current.addTo(map)
      } catch (e) {
        // swallow zero-size canvas error during initial render
      }
    }

    map.whenReady(addHeatLayer)

    return () => {
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current)
        heatLayerRef.current = null
      }
    }
  }, [viewMode, incidents, map])

  return null
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
      <HeatmapController viewMode={viewMode} incidents={incidents} />
      {viewMode === 'cluster' && (
        <MarkerClusterGroup chunkedLoading>
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
    </MapContainer>
  )
}
