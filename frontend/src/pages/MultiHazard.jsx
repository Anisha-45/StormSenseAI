import { useState } from 'react'
import { useGet } from '../lib/useApi.js'
import { Async, Card, DataTable, Field, Note, PageHeader, Select, Stat, Tabs } from '../components/ui.jsx'
import { BarBlock } from '../components/charts.jsx'
import { num } from '../lib/format.js'

export default function MultiHazard() {
  const opts = useGet('/geography/filters')
  const [tab, setTab] = useState('combos')
  const [radius, setRadius] = useState(25)
  const [hours, setHours] = useState(6)
  const [f, setF] = useState({ type_a: '', type_b: '', state: '' })
  const [eid, setEid] = useState('')
  const [activeEid, setActiveEid] = useState('')
  const [nb, setNb] = useState({ radius: 50, hours: 24 })
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }))

  const mh = useGet('/multi-hazard', { radius_km: radius, window_hours: hours, ...f }, { enabled: tab === 'combos' })
  const near = useGet(activeEid ? `/events/${activeEid}/nearby` : null, { radius_km: nb.radius, window_hours: nb.hours }, { enabled: tab === 'nearby' && !!activeEid })

  return (
    <>
      <PageHeader title="Multi-Hazard Relationships" subtitle="Which different event types were recorded close together in space and time. Proximity in the records does not mean one event caused another." />
      <Note tone="warn" title="No causation.">Two reports near each other may reflect one storm system, different reporting offices, or coincidence. Treat results as leads for investigation.</Note>
      <div className="mt-4"><Tabs value={tab} onChange={setTab} tabs={[{ value: 'combos', label: 'Type combinations' }, { value: 'nearby', label: 'Events near a chosen event' }]} /></div>

      {tab === 'combos' && (
        <>
          <Card className="mb-5">
            <div className="grid gap-3 md:grid-cols-5">
              <Field label={`Distance: ${radius} km`}><input type="range" min="5" max="200" step="5" value={radius} onChange={(e) => setRadius(Number(e.target.value))} className="w-full" /></Field>
              <Field label={`Time window: ${hours} h`}><input type="range" min="1" max="72" step="1" value={hours} onChange={(e) => setHours(Number(e.target.value))} className="w-full" /></Field>
              <Field label="Includes type"><Select value={f.type_a} onChange={set('type_a')} options={opts.data?.event_types || []} placeholder="Any" /></Field>
              <Field label="and type"><Select value={f.type_b} onChange={set('type_b')} options={opts.data?.event_types || []} placeholder="Any" /></Field>
              <Field label="State"><Select value={f.state} onChange={set('state')} options={opts.data?.states || []} placeholder="All" /></Field>
            </div>
          </Card>
          <Async state={mh}>
            {(d) => (
              <div className="space-y-5">
                <div className="grid grid-cols-3 gap-3"><Stat label="Events with coordinates considered" value={num(d.events_considered)} /><Stat label="Cross-type pairs found" value={num(d.pair_count)} hint={d.truncated ? 'capped at 20,000' : undefined} /><Stat label="Distinct combinations" value={num(d.combinations.length)} /></div>
                <Card title="Most frequent combinations" subtitle={`Different event types within ${d.radius_km} km and ${d.window_hours} h`}>
                  <BarBlock data={d.combinations.slice(0, 12).map((c) => ({ name: `${c.type_a} + ${c.type_b}`, pairs: c.pairs }))} x="name" bars="pairs" layout="vertical" height={340} />
                  <DataTable columns={[{ key: 'type_a', label: 'Type A' }, { key: 'type_b', label: 'Type B' }, { key: 'pairs', label: 'Pairs', align: 'right', render: (r) => num(r.pairs) }, { key: 'median_hours_apart', label: 'Median hours apart', align: 'right' }]} rows={d.combinations.map((c, i) => ({ ...c, id: i }))} maxHeight={280} />
                </Card>
                <Card title="Example pairs (first 200)"><DataTable columns={[{ key: 'event_a', label: 'Event A' }, { key: 'type_a', label: 'Type A' }, { key: 'event_b', label: 'Event B' }, { key: 'type_b', label: 'Type B' }, { key: 'hours_apart', label: 'Hours apart', align: 'right' }]} rows={d.pairs.map((p, i) => ({ ...p, id: i }))} maxHeight={320} /></Card>
                <p className="text-xs italic text-slate-500">{d.caveat}</p>
              </div>
            )}
          </Async>
        </>
      )}

      {tab === 'nearby' && (
        <div className="space-y-4">
          <Card>
            <div className="grid gap-3 md:grid-cols-4">
              <Field label="Event ID"><input className="input" inputMode="numeric" value={eid} onChange={(e) => setEid(e.target.value.replace(/\D/g, ''))} /></Field>
              <Field label="Radius (km)"><input className="input" type="number" min="1" max="500" value={nb.radius} onChange={(e) => setNb({ ...nb, radius: Number(e.target.value) })} /></Field>
              <Field label="Window (± hours)"><input className="input" type="number" min="1" max="720" value={nb.hours} onChange={(e) => setNb({ ...nb, hours: Number(e.target.value) })} /></Field>
              <div className="flex items-end"><button className="btn" disabled={!eid} onClick={() => setActiveEid(eid)}>Search</button></div>
            </div>
          </Card>
          {activeEid && (
            <Async state={near}>
              {(d) => (
                <Card title={`Around event ${d.event.event_id}: ${d.event.event_type}, ${d.event.state}`}>
                  {d.note ? <Note>{d.note}</Note> : (<><DataTable columns={[{ key: 'event_id', label: 'Event' }, { key: 'event_type', label: 'Type' }, { key: 'state', label: 'State' }, { key: 'km', label: 'Km away', align: 'right' }, { key: 'hours', label: 'Hours (±)', align: 'right' }, { key: 'deaths_total', label: 'Deaths', align: 'right' }]} rows={d.nearby} empty="No other events within this distance and time window." maxHeight={420} /><p className="mt-2 text-xs italic text-slate-500">{d.caveat}</p></>)}
                </Card>
              )}
            </Async>
          )}
        </div>
      )}
    </>
  )
}
