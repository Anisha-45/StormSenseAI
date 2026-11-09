import { useState } from 'react'
import { useGet } from '../lib/useApi.js'
import { Async, Card, DataTable, Field, Note, PageHeader, Select, Stat, Tabs } from '../components/ui.jsx'
import { BarBlock } from '../components/charts.jsx'
import { num, pct, usd } from '../lib/format.js'

export default function Impact() {
  const opts = useGet('/geography/filters')
  const exps = useGet('/clustering/experiments')
  const [f, setF] = useState({ state: '', event_type: '', year: '' })
  const [tab, setTab] = useState('type')
  const [w, setW] = useState({ death_weight: 10, injury_weight: 3, damage_per_point_usd: 1000000 })
  const [expId, setExpId] = useState('')
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }))

  const summary = useGet('/impact/summary', f)
  const byType = useGet('/impact/by-event-type', { state: f.state, year: f.year, top: 20 }, { enabled: tab === 'type' })
  const byRegion = useGet('/impact/by-region', { event_type: f.event_type, year: f.year, top: 20 }, { enabled: tab === 'region' })
  const byCluster = useGet('/impact/by-cluster', { experiment_id: expId }, { enabled: tab === 'cluster' && !!expId })
  const high = useGet('/impact/high-impact', { ...w, ...f, top: 25 }, { enabled: tab === 'high' })

  const impactCols = (key, label) => [
    { key, label }, { key: 'events', label: 'Events', align: 'right', render: (r) => num(r.events) }, { key: 'deaths', label: 'Deaths', align: 'right', render: (r) => num(r.deaths) },
    { key: 'injuries', label: 'Injuries', align: 'right', render: (r) => num(r.injuries) }, { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => usd(r.property_damage_usd) },
    { key: 'crop_damage_usd', label: 'Crops', align: 'right', render: (r) => usd(r.crop_damage_usd) }, { key: 'deaths_per_1000_events', label: 'Deaths / 1000 events', align: 'right' }]

  const grouped = (rows, key) => (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <div><div className="label">Recorded deaths</div><BarBlock data={rows.slice(0, 12)} x={key} bars="deaths" layout="vertical" height={320} /></div>
        <div><div className="label">Property damage</div><BarBlock data={rows.slice(0, 12)} x={key} bars="property_damage_usd" layout="vertical" height={320} yFormatter={usd} /></div>
      </div>
      <DataTable columns={impactCols(key, key === 'event_type' ? 'Event type' : key === 'state' ? 'State / region' : 'Cluster')} rows={rows.map((r) => ({ ...r, id: r[key] }))} maxHeight={360} />
    </div>
  )

  return (
    <>
      <PageHeader title="Impact & Severity Intelligence" subtitle="Compare recorded deaths, injuries and damage across event types, regions and clusters. Damage values are NWS estimates and are missing for many events." />
      <Card className="mb-4"><div className="grid gap-3 md:grid-cols-3">
        <Field label="State / region"><Select value={f.state} onChange={set('state')} options={opts.data?.states || []} placeholder="All" /></Field>
        <Field label="Event type"><Select value={f.event_type} onChange={set('event_type')} options={opts.data?.event_types || []} placeholder="All" /></Field>
        <Field label="Year"><Select value={f.year} onChange={set('year')} options={opts.data?.years || []} placeholder="All" /></Field>
      </div></Card>
      <Async state={summary}>
        {(s) => (
          <div className="mb-5 space-y-3">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5"><Stat label="Events" value={num(s.events)} /><Stat label="Deaths" value={num(s.deaths)} /><Stat label="Injuries" value={num(s.injuries)} /><Stat label="Property damage" value={usd(s.property_damage_usd)} /><Stat label="Crop damage" value={usd(s.crop_damage_usd)} /></div>
            <p className="text-xs italic text-slate-500">{num(s.events_with_impact)} events have any recorded impact; property damage was reported for {pct(s.property_damage_reported_pct)} of the selected events. {s.note}</p>
          </div>
        )}
      </Async>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'type', label: 'By event type' }, { value: 'region', label: 'By region' }, { value: 'cluster', label: 'By cluster' }, { value: 'high', label: 'High-impact events' }]} />
      {tab === 'type' && <Async state={byType}>{(d) => grouped(d.rows, 'event_type')}</Async>}
      {tab === 'region' && <Async state={byRegion}>{(d) => grouped(d.rows, 'state')}</Async>}
      {tab === 'cluster' && (
        <div className="space-y-3">
          <Field label="Experiment"><Select value={expId} onChange={setExpId} placeholder="Choose an experiment" options={(exps.data || []).map((e) => ({ value: e.id, label: `#${e.id} ${e.algorithm} (${e.n_clusters} clusters)` }))} /></Field>
          {expId ? <Async state={byCluster}>{(d) => grouped(d.rows.map((r) => ({ ...r, cluster: `Cluster ${r.cluster}` })), 'cluster')}</Async> : <Note>Choose an experiment to compare its clusters.</Note>}
        </div>
      )}
      {tab === 'high' && (
        <div className="space-y-4">
          <Card title="Configurable severity index" subtitle="severity = deaths × weight + injuries × weight + total damage ÷ dollars-per-point. A project index, not an official classification.">
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="Weight per death"><input className="input" type="number" min="0" value={w.death_weight} onChange={(e) => setW({ ...w, death_weight: Number(e.target.value) })} /></Field>
              <Field label="Weight per injury"><input className="input" type="number" min="0" value={w.injury_weight} onChange={(e) => setW({ ...w, injury_weight: Number(e.target.value) })} /></Field>
              <Field label="Dollars per severity point"><input className="input" type="number" min="1" value={w.damage_per_point_usd} onChange={(e) => setW({ ...w, damage_per_point_usd: Number(e.target.value) || 1 })} /></Field>
            </div>
          </Card>
          <Async state={high}>{(d) => <><DataTable columns={[{ key: 'event_id', label: 'Event' }, { key: 'event_type', label: 'Type' }, { key: 'state', label: 'State' }, { key: 'begin_dt', label: 'Begin', render: (r) => r.begin_dt?.slice(0, 10) }, { key: 'deaths_total', label: 'Deaths', align: 'right' }, { key: 'injuries_total', label: 'Injuries', align: 'right' }, { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => usd(r.property_damage_usd) }, { key: 'severity_score', label: 'Severity (custom)', align: 'right', render: (r) => num(r.severity_score, 1) }]} rows={d.events} /><p className="mt-2 text-xs italic text-slate-500">{d.note}</p></>}</Async>
        </div>
      )}
    </>
  )
}
