import { useState } from 'react'
import { useGet } from '../lib/useApi.js'
import { Async, Card, DataTable, Field, Note, PageHeader, Select, Stat, Tabs } from '../components/ui.jsx'
import MapView, { Legend } from '../components/MapView.jsx'
import { BarBlock } from '../components/charts.jsx'
import { clusterColor, num, usd } from '../lib/format.js'

const TYPE_COLORS = {}
const palette = ['#2f7de1', '#e8833a', '#2a9d8f', '#c44e8a', '#8e7cc3', '#d4a72c', '#4d908e', '#b5543c']
const colorFor = (t) => (TYPE_COLORS[t] ||= palette[Object.keys(TYPE_COLORS).length % palette.length])

export default function Geographic() {
  const opts = useGet('/geography/filters')
  const exps = useGet('/clustering/experiments')
  const [view, setView] = useState('events')
  const [f, setF] = useState({ state: '', event_type: '', year: '' })
  const [cell, setCell] = useState(1)
  const [expId, setExpId] = useState('')
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }))

  const ev = useGet('/geography/events', { ...f, limit: 3000 }, { enabled: view === 'events' })
  const hot = useGet('/geography/hotspots', { ...f, cell_deg: cell, top: 60 }, { enabled: view === 'hotspots' })
  const cl = useGet('/geography/clusters', { experiment_id: expId }, { enabled: view === 'clusters' && !!expId })
  const regions = useGet('/geography/regions', { event_type: f.event_type, year: f.year })

  return (
    <>
      <PageHeader title="Geographic Intelligence" subtitle="Where historical events were recorded. Only events with recorded coordinates can be mapped; forecast-zone events (heat, drought, winter storms) have none." />
      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="State / region"><Select value={f.state} onChange={set('state')} options={opts.data?.states || []} placeholder="All" /></Field>
          <Field label="Event type"><Select value={f.event_type} onChange={set('event_type')} options={opts.data?.event_types || []} placeholder="All" /></Field>
          <Field label="Year"><Select value={f.year} onChange={set('year')} options={opts.data?.years || []} placeholder="All" /></Field>
          {view === 'hotspots' && <Field label="Grid cell (degrees)"><Select value={cell} onChange={(v) => setCell(Number(v))} options={[0.5, 1, 2, 5]} /></Field>}
          {view === 'clusters' && <Field label="Experiment"><Select value={expId} onChange={setExpId} placeholder="Choose..." options={(exps.data || []).map((e) => ({ value: e.id, label: `#${e.id} ${e.algorithm} (${e.n_clusters} clusters)` }))} /></Field>}
        </div>
      </Card>
      <Tabs value={view} onChange={setView} tabs={[{ value: 'events', label: 'Event markers' }, { value: 'hotspots', label: 'Concentration (density grid)' }, { value: 'clusters', label: 'Clusters on map' }]} />

      {view === 'events' && (
        <Async state={ev}>
          {(d) => {
            const types = [...new Set(d.events.map((e) => e.event_type))].slice(0, 8)
            return (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-3"><Stat label="Matching events" value={num(d.matching_events)} /><Stat label="With coordinates" value={num(d.with_coordinates)} /><Stat label="Shown" value={num(d.returned)} hint={d.sampled ? 'random sample' : 'all'} /></div>
                <MapView height={520} legend={<Legend items={types.map((t) => ({ label: t, color: colorFor(t) }))} />}
                  points={d.events.map((e) => ({ key: e.event_id, lat: e.lat, lon: e.lon, color: colorFor(e.event_type), radius: e.deaths_total > 0 ? 8 : 4,
                    tooltip: `${e.event_type} · ${e.state}`,
                    popup: <div className="text-xs"><b>{e.event_type}</b> (#{e.event_id})<br />{e.state} · {e.begin_dt?.slice(0, 16)}<br />Deaths {e.deaths_total} · Injuries {e.injuries_total}<br />Property {usd(e.property_damage_usd)}{e.magnitude != null && <><br />Magnitude {e.magnitude}</>}</div> }))} />
                <Note>{d.note} Larger markers have at least one recorded death.</Note>
              </div>
            )
          }}
        </Async>
      )}

      {view === 'hotspots' && (
        <Async state={hot}>
          {(d) => {
            const max = Math.max(1, ...d.cells.map((c) => c.events))
            return (
              <div className="space-y-3">
                <MapView height={520} legend="Circle size = events in grid cell"
                  points={d.cells.map((c, i) => ({ key: i, lat: c.lat, lon: c.lon, color: '#c0392b', radius: 6 + (c.events / max) * 26,
                    tooltip: `${num(c.events)} events`, popup: <div className="text-xs"><b>{num(c.events)} events</b> in a {d.cell_degrees}° cell<br />Most common: {c.top_type} ({c.top_state})<br />Deaths {c.deaths} · Injuries {c.injuries}<br />Damage {usd(c.damage)}</div> }))} />
                <Note tone="warn" title="Historical only.">{d.caveat}</Note>
                <DataTable columns={[{ key: 'top_state', label: 'Region' }, { key: 'top_type', label: 'Most common type' }, { key: 'events', label: 'Events', align: 'right', render: (r) => num(r.events) }, { key: 'deaths', label: 'Deaths', align: 'right' }, { key: 'damage', label: 'Damage', align: 'right', render: (r) => usd(r.damage) }]} rows={d.cells.map((c, i) => ({ ...c, id: i }))} maxHeight={300} />
              </div>
            )
          }}
        </Async>
      )}

      {view === 'clusters' && (!expId ? <Note>Choose an experiment to see its clusters on the map. Run one in the Clustering Lab if the list is empty.</Note> : (
        <Async state={cl}>
          {(d) => {
            const ids = [...new Set(d.points.map((p) => p.cluster))].sort((a, b) => a - b)
            return (
              <div className="space-y-3">
                <MapView height={520} legend={<Legend items={ids.map((i) => ({ label: i === -1 ? 'Noise' : `Cluster ${i}`, color: clusterColor(i) }))} />}
                  points={d.points.map((p) => ({ key: p.event_id, lat: p.lat, lon: p.lon, color: clusterColor(p.cluster), radius: 4, tooltip: `Cluster ${p.cluster} · ${p.event_type}`, popup: <div className="text-xs">#{p.event_id} {p.event_type}<br />{p.state} · cluster {p.cluster}</div> }))} />
                <Note>{num(d.unmapped_events)} clustered events have no coordinates and are not shown. {d.caveat}</Note>
                <DataTable columns={[{ key: 'cluster', label: 'Cluster' }, { key: 'events', label: 'Mapped events', align: 'right' }, { key: 'lat', label: 'Mean lat', align: 'right', render: (r) => r.lat.toFixed(2) }, { key: 'lon', label: 'Mean lon', align: 'right', render: (r) => r.lon.toFixed(2) }]} rows={d.centroids.map((c) => ({ ...c, id: c.cluster }))} />
              </div>
            )
          }}
        </Async>
      ))}

      <Card className="mt-5" title="Regional distribution" subtitle="Events per state / region for the selected event type and year">
        <Async state={regions}>
          {(rows) => (
            <>
              <BarBlock data={rows.slice(0, 15)} x="state" bars="events" height={260} />
              <DataTable maxHeight={320} columns={[{ key: 'state', label: 'State / region' }, { key: 'events', label: 'Events', align: 'right', render: (r) => num(r.events) }, { key: 'deaths', label: 'Deaths', align: 'right' }, { key: 'injuries', label: 'Injuries', align: 'right' }, { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => usd(r.property_damage_usd) }]} rows={rows.map((r) => ({ ...r, id: r.state }))} />
            </>
          )}
        </Async>
      </Card>
    </>
  )
}
