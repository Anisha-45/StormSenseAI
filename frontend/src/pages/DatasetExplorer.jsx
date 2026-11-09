import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useGet } from '../lib/useApi.js'
import { Async, Card, DataTable, Field, Note, PageHeader, Pager, Select } from '../components/ui.jsx'
import { num, usd } from '../lib/format.js'

export default function DatasetExplorer() {
  const opts = useGet('/geography/filters')
  const [f, setF] = useState({ state: '', event_type: '', year: '', season: '', text: '', min_deaths: '' })
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const res = useGet('/events/search', { ...f, page, page_size: 25 })
  const rec = useGet(selected ? `/events/${selected}` : null, null, { enabled: !!selected })
  const set = (k) => (v) => { setF((s) => ({ ...s, [k]: v })); setPage(1) }

  const cols = [
    { key: 'event_id', label: 'Event ID' }, { key: 'event_type', label: 'Type' }, { key: 'state', label: 'State' },
    { key: 'begin_dt', label: 'Begin', render: (r) => r.begin_dt?.slice(0, 16) }, { key: 'magnitude', label: 'Magnitude', align: 'right' },
    { key: 'deaths_total', label: 'Deaths', align: 'right' }, { key: 'injuries_total', label: 'Injuries', align: 'right' },
    { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => usd(r.property_damage_usd) },
  ]
  return (
    <>
      <PageHeader title="Dataset Explorer" subtitle="Search and page through the processed event table (one row per unique event). Click a row to see the full record." />
      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-6">
          <Field label="State"><Select value={f.state} onChange={set('state')} options={opts.data?.states || []} placeholder="All" /></Field>
          <Field label="Event type"><Select value={f.event_type} onChange={set('event_type')} options={opts.data?.event_types || []} placeholder="All" /></Field>
          <Field label="Year"><Select value={f.year} onChange={set('year')} options={opts.data?.years || []} placeholder="All" /></Field>
          <Field label="Season"><Select value={f.season} onChange={set('season')} options={['Winter', 'Spring', 'Summer', 'Autumn']} placeholder="All" /></Field>
          <Field label="Min. deaths"><input className="input" type="number" min="0" value={f.min_deaths} onChange={(e) => set('min_deaths')(e.target.value)} /></Field>
          <Field label="Text"><input className="input" placeholder="type or state" value={f.text} onChange={(e) => set('text')(e.target.value)} /></Field>
        </div>
        <button className="btn-secondary mt-3" onClick={() => { setF({ state: '', event_type: '', year: '', season: '', text: '', min_deaths: '' }); setPage(1) }}>Reset filters</button>
      </Card>
      <Async state={res}>
        {(d) => (
          <>
            <DataTable columns={cols} rows={d.rows} onRowClick={(r) => setSelected(r.event_id)} empty="No events match these filters." />
            <Pager page={page} pageSize={d.page_size} total={d.total} onChange={setPage} />
          </>
        )}
      </Async>
      {selected && (
        <Card className="mt-5" title={`Event ${selected}`} actions={<button className="btn-secondary" onClick={() => setSelected(null)}>Close</button>}>
          <Async state={rec}>
            {(r) => (
              <div className="space-y-3">
                <dl className="grid gap-x-6 gap-y-2 text-sm md:grid-cols-3">
                  {['event_type', 'state', 'begin_dt', 'end_dt', 'duration_hours', 'magnitude', 'magnitude_type', 'deaths_total', 'injuries_total', 'DAMAGE_PROPERTY', 'property_damage_usd', 'DAMAGE_CROPS', 'crop_damage_usd', 'lat', 'lon', 'CZ_NAME', 'SOURCE', 'episode_id', 'loc_row_count', 'fatality_rows'].map((k) => (
                    <div key={k}><dt className="label">{k}</dt><dd>{r[k] === null || r[k] === undefined ? '-' : typeof r[k] === 'number' ? num(r[k], 3) : String(r[k])}</dd></div>
                  ))}
                </dl>
                {r.EVENT_NARRATIVE && <div><div className="label">Narrative (NWS)</div><p className="text-sm text-slate-700">{r.EVENT_NARRATIVE}</p></div>}
                <Link className="btn inline-flex" to={`/similar?event=${selected}`}>Find similar events</Link>
                {!r.has_coordinates && <Note>This event has no recorded coordinates (typical for forecast-zone events), so it cannot be shown on the map.</Note>}
              </div>
            )}
          </Async>
        </Card>
      )}
    </>
  )
}
