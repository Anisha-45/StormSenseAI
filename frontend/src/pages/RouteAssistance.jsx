import { useState } from 'react'
import { useAction, useGet } from '../lib/useApi.js'
import { Card, ErrorBox, Field, Note, PageHeader, Stat } from '../components/ui.jsx'
import MapView from '../components/MapView.jsx'

const ROUTE_COLORS = ['#1f64c4', '#7a8794', '#a05a2c']

export default function RouteAssistance() {
  const [origin, setOrigin] = useState(null)
  const [dest, setDest] = useState(null)
  const [mode, setMode] = useState('origin')
  const [data, setData] = useState(null)
  const [sel, setSel] = useState(0)
  const [overlay, setOverlay] = useState(false)
  const act = useAction()
  const hazards = useGet('/geography/events', { limit: 1500 }, { enabled: overlay })

  const onMapClick = (ll) => {
    const p = { lat: +ll.lat.toFixed(5), lon: +ll.lng.toFixed(5) }
    if (mode === 'origin') { setOrigin(p); setMode('dest') } else { setDest(p) }
    setData(null)
  }
  const num = (v) => (v === '' ? null : Number(v))
  const setCoord = (setter, key) => (e) => setter((p) => ({ lat: 0, lon: 0, ...(p || {}), [key]: num(e.target.value) }))

  async function find() {
    const r = await act.run((api) => api.get('/routes', { params: { origin_lat: origin.lat, origin_lon: origin.lon, dest_lat: dest.lat, dest_lon: dest.lon } }))
    if (r) { setData(r.data); setSel(0) }
  }
  const ready = origin && dest && [origin.lat, origin.lon, dest.lat, dest.lon].every((v) => typeof v === 'number' && !Number.isNaN(v))
  const route = data?.routes?.[sel]

  return (
    <>
      <PageHeader title="Route Assistance" subtitle="Driving routes from OpenStreetMap data (OSRM), with optional historical hazard points for context." />
      <Note tone="danger" title="A route is never a guarantee of safety.">Follow official emergency instructions and check current road closures with your transport authority or 511 service. Historical hazard markers are past records, not evidence of a current hazard.</Note>
      <div className="mt-4 grid gap-5 lg:grid-cols-3">
        <div className="space-y-4">
          <Card title="Origin and destination" subtitle="Click the map to set points, or type coordinates.">
            <div className="mb-3 flex gap-2">
              <button className={mode === 'origin' ? 'btn' : 'btn-secondary'} onClick={() => setMode('origin')}>Set origin</button>
              <button className={mode === 'dest' ? 'btn' : 'btn-secondary'} onClick={() => setMode('dest')}>Set destination</button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Origin lat"><input className="input" type="number" step="any" value={origin?.lat ?? ''} onChange={setCoord(setOrigin, 'lat')} /></Field>
              <Field label="Origin lon"><input className="input" type="number" step="any" value={origin?.lon ?? ''} onChange={setCoord(setOrigin, 'lon')} /></Field>
              <Field label="Dest. lat"><input className="input" type="number" step="any" value={dest?.lat ?? ''} onChange={setCoord(setDest, 'lat')} /></Field>
              <Field label="Dest. lon"><input className="input" type="number" step="any" value={dest?.lon ?? ''} onChange={setCoord(setDest, 'lon')} /></Field>
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={overlay} onChange={(e) => setOverlay(e.target.checked)} /> Show historical event points (context only)</label>
            <button className="btn mt-3 w-full" disabled={!ready || act.busy} onClick={find}>{act.busy ? 'Finding routes...' : 'Find routes'}</button>
            <div className="mt-3"><ErrorBox message={act.error} /></div>
          </Card>
          {data && (
            <Card title="Routes">
              <div className="space-y-2">
                {data.routes.map((r, i) => (
                  <button key={i} onClick={() => setSel(i)} className={`w-full rounded-lg border p-2 text-left text-sm ${sel === i ? 'border-storm-600 bg-storm-50' : 'border-slate-200'}`}>
                    <b>{i === 0 ? 'Fastest' : `Alternative ${i}`}</b> · {r.distance_km} km · {r.duration_min} min
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-slate-500">Source: {data.source} · fetched {new Date(data.fetched_at).toLocaleTimeString()}</p>
              <p className="mt-1 text-xs text-slate-500">{data.road_closures}</p>
            </Card>
          )}
        </div>
        <div className="space-y-4 lg:col-span-2">
          <MapView height={460} fit={false} onMapClick={onMapClick}
            markers={[...(origin && typeof origin.lat === 'number' ? [{ ...origin, label: 'Origin' }] : []), ...(dest && typeof dest.lat === 'number' ? [{ ...dest, label: 'Destination' }] : [])]}
            lines={(data?.routes || []).map((r, i) => ({ positions: r.geometry.coordinates.map(([lon, lat]) => [lat, lon]), color: ROUTE_COLORS[i % 3], weight: i === sel ? 6 : 3, opacity: i === sel ? 0.9 : 0.5 }))}
            points={overlay && hazards.data ? hazards.data.events.map((e) => ({ key: e.event_id, lat: e.lat, lon: e.lon, color: '#c0392b', radius: 3, tooltip: `Historical: ${e.event_type} (${e.begin_dt?.slice(0, 10)})` })) : []} />
          {route && (
            <Card title={`Directions: ${route.distance_km} km, ${route.duration_min} min`}>
              <ol className="max-h-72 list-decimal space-y-1 overflow-auto pl-5 text-sm text-slate-700">
                {route.steps.map((s, i) => <li key={i}>{s.instruction} <span className="text-slate-400">({Math.round(s.distance_m)} m)</span></li>)}
              </ol>
            </Card>
          )}
          {data && <p className="text-xs italic text-slate-500">{data.disclaimer}</p>}
        </div>
      </div>
    </>
  )
}
