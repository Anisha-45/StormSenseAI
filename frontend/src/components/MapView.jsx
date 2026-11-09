import { useEffect } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// Bundlers break Leaflet's default icon URLs; set them explicitly.
L.Icon.Default.mergeOptions({ iconUrl: markerIcon, iconRetinaUrl: markerIcon2x, shadowUrl: markerShadow })

const US_CENTER = [38.5, -96]

function FitBounds({ points }) {
  const map = useMap()
  useEffect(() => {
    if (points && points.length > 1) {
      const b = L.latLngBounds(points.map((p) => [p.lat, p.lon]))
      if (b.isValid()) map.fitBounds(b, { padding: [30, 30], maxZoom: 9 })
    }
  }, [points, map])
  return null
}

function ClickCapture({ onClick }) {
  useMapEvents({ click: (e) => onClick && onClick(e.latlng) })
  return null
}

/**
 * Generic map. points: [{lat, lon, color, radius, popup, tooltip}]
 * lines: [{positions: [[lat, lon], ...], color, weight}]  geojson: FeatureCollection-like list
 */
export default function MapView({ points = [], lines = [], geojson = [], markers = [], height = 480, fit = true, onMapClick, legend }) {
  return (
    <div className="relative" style={{ height }}>
      <MapContainer center={US_CENTER} zoom={4} scrollWheelZoom preferCanvas>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {fit && <FitBounds points={points} />}
        <ClickCapture onClick={onMapClick} />
        {points.map((p, i) => (
          <CircleMarker key={p.key ?? i} center={[p.lat, p.lon]} radius={p.radius ?? 5} pathOptions={{ color: p.color || '#1f64c4', fillColor: p.color || '#2f7de1', fillOpacity: 0.65, weight: 1 }}>
            {p.tooltip && <Tooltip>{p.tooltip}</Tooltip>}
            {p.popup && <Popup>{p.popup}</Popup>}
          </CircleMarker>
        ))}
        {lines.map((l, i) => <Polyline key={i} positions={l.positions} pathOptions={{ color: l.color || '#1f64c4', weight: l.weight || 5, opacity: l.opacity ?? 0.8, dashArray: l.dash }} />)}
        {geojson.map((g, i) => <GeoJSON key={g.key ?? i} data={g.data} style={() => ({ color: g.color || '#d4380d', weight: 1.5, fillOpacity: 0.15 })}>{g.popup && <Popup>{g.popup}</Popup>}</GeoJSON>)}
        {markers.map((m, i) => <Marker key={i} position={[m.lat, m.lon]}><Popup>{m.label}</Popup></Marker>)}
      </MapContainer>
      {legend && <div className="absolute bottom-3 left-3 z-[400] rounded-lg border border-slate-200 bg-white/95 p-2 text-xs shadow">{legend}</div>}
    </div>
  )
}

export function Legend({ items }) {
  return (
    <ul className="space-y-1">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 rounded-full" style={{ background: it.color }} />
          {it.label}
        </li>
      ))}
    </ul>
  )
}
