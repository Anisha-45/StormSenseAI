import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useGet } from '../lib/useApi.js'
import { Async, Card, DataTable, Field, Note, PageHeader, Pager, Select } from '../components/ui.jsx'
import { num, usd } from '../lib/format.js'

const FIELDS = [['event_type', 'Type'], ['state', 'State'], ['begin_dt', 'Begin'], ['deaths_total', 'Deaths'], ['injuries_total', 'Injuries'], ['property_damage_usd', 'Property damage'], ['crop_damage_usd', 'Crop damage'], ['magnitude', 'Magnitude']]
const show = (k, v) => (v === null || v === undefined ? '-' : k.includes('damage') ? usd(v) : k === 'begin_dt' ? String(v).slice(0, 16) : typeof v === 'number' ? num(v, 2) : v)

export default function SimilarEvents() {
  const [params, setParams] = useSearchParams()
  const opts = useGet('/geography/filters')
  const [eventId, setEventId] = useState(params.get('event') || '')
  const [active, setActive] = useState(params.get('event') || '')
  const [sameType, setSameType] = useState(true)
  const [k, setK] = useState(10)
  const [cmp, setCmp] = useState(null)
  const [f, setF] = useState({ state: '', event_type: '', year: '', season: '', min_deaths: '', min_damage: '', min_magnitude: '' })
  const [page, setPage] = useState(1)
  const search = useGet('/events/search', { ...f, page, page_size: 10 })
  const sim = useGet(active ? `/events/${active}/similar` : null, { k, same_type: sameType }, { enabled: !!active })
  const set = (key) => (v) => { setF((s) => ({ ...s, [key]: v })); setPage(1) }

  useEffect(() => { const e = params.get('event'); if (e) { setEventId(e); setActive(e) } }, [params])
  const go = (id) => { setParams({ event: String(id) }); setEventId(String(id)); setActive(String(id)); setCmp(null) }

  return (
    <>
      <PageHeader title="Similar Event Search" subtitle="Find the historical events most like a chosen one. Similarity uses standardised distance over impact, duration, magnitude, time of year and location." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="1. Pick an event" subtitle="Enter an event ID, or find one with the filters below.">
          <div className="flex gap-2">
            <input className="input" inputMode="numeric" placeholder="Event ID, e.g. 917518" value={eventId} onChange={(e) => setEventId(e.target.value.replace(/\D/g, ''))} onKeyDown={(e) => e.key === 'Enter' && eventId && go(eventId)} />
            <button className="btn" disabled={!eventId} onClick={() => go(eventId)}>Find similar</button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <Field label="State"><Select value={f.state} onChange={set('state')} options={opts.data?.states || []} placeholder="Any" /></Field>
            <Field label="Type"><Select value={f.event_type} onChange={set('event_type')} options={opts.data?.event_types || []} placeholder="Any" /></Field>
            <Field label="Year"><Select value={f.year} onChange={set('year')} options={opts.data?.years || []} placeholder="Any" /></Field>
            <Field label="Season"><Select value={f.season} onChange={set('season')} options={['Winter', 'Spring', 'Summer', 'Autumn']} placeholder="Any" /></Field>
            <Field label="Min. deaths"><input className="input" type="number" min="0" value={f.min_deaths} onChange={(e) => set('min_deaths')(e.target.value)} /></Field>
            <Field label="Min. magnitude"><input className="input" type="number" value={f.min_magnitude} onChange={(e) => set('min_magnitude')(e.target.value)} /></Field>
          </div>
          <div className="mt-3">
            <Async state={search}>
              {(d) => (<><DataTable onRowClick={(r) => go(r.event_id)} columns={[{ key: 'event_id', label: 'Event' }, { key: 'event_type', label: 'Type' }, { key: 'state', label: 'State' }, { key: 'year', label: 'Year' }, { key: 'deaths_total', label: 'Deaths', align: 'right' }]} rows={d.rows} empty="No events match." /><Pager page={page} pageSize={d.page_size} total={d.total} onChange={setPage} /></>)}
            </Async>
          </div>
        </Card>

        <Card title="2. Similar historical events" actions={<div className="flex items-center gap-3 text-sm"><label className="flex items-center gap-1"><input type="checkbox" checked={sameType} onChange={(e) => setSameType(e.target.checked)} /> same type only</label><Select value={k} onChange={(v) => setK(Number(v))} options={[5, 10, 20, 50]} aria-label="Number of results" /></div>}>
          {!active ? <Note>Choose an event on the left to see its closest matches.</Note> : (
            <Async state={sim}>
              {(d) => (
                <div className="space-y-3">
                  <div className="rounded-lg bg-storm-50 p-3 text-sm"><b>Selected: #{d.query.event_id}</b> {d.query.event_type}, {d.query.state}, {String(d.query.begin_dt).slice(0, 10)} · deaths {d.query.deaths_total} · damage {usd(d.query.property_damage_usd)}</div>
                  <DataTable onRowClick={setCmp} columns={[{ key: 'event_id', label: 'Event' }, { key: 'similarity', label: 'Similarity', align: 'right' }, { key: 'event_type', label: 'Type' }, { key: 'state', label: 'State' }, { key: 'explanation', label: 'Why' }]} rows={d.similar} maxHeight={380} />
                  <p className="text-xs italic text-slate-500">{d.method} Similarity = {d.similarity_formula}. Features used: {d.features.join(', ')}.</p>
                  {cmp && (
                    <div>
                      <div className="label">Side-by-side comparison</div>
                      <table className="min-w-full text-sm"><thead><tr><th className="th">Field</th><th className="th">Selected #{d.query.event_id}</th><th className="th">Match #{cmp.event_id}</th></tr></thead>
                        <tbody>{FIELDS.map(([key, label]) => <tr key={key} className="border-b border-slate-100"><td className="td font-medium">{label}</td><td className="td">{show(key, d.query[key])}</td><td className="td">{show(key, cmp[key])}</td></tr>)}</tbody></table>
                      <button className="btn-secondary mt-2" onClick={() => go(cmp.event_id)}>Use match as new selection</button>
                    </div>
                  )}
                </div>
              )}
            </Async>
          )}
        </Card>
      </div>
    </>
  )
}
