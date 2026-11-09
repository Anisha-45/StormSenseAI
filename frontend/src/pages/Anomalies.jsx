import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAction, useGet } from '../lib/useApi.js'
import { Badge, Card, DataTable, ErrorBox, Field, Gate, Note, PageHeader, Select, Stat } from '../components/ui.jsx'
import { num, usd } from '../lib/format.js'

const METHODS = [
  { value: 'isolation_forest', label: 'Isolation Forest' },
  { value: 'statistical', label: 'Statistical (IQR fences)' },
  { value: 'lof', label: 'Local Outlier Factor' },
]
const FEATURES = { log_property_damage: 'Property damage', log_crop_damage: 'Crop damage', injuries_total: 'Injuries', deaths_total: 'Deaths', log_duration_hours: 'Duration', magnitude: 'Magnitude' }

export default function Anomalies() {
  const [method, setMethod] = useState('isolation_forest')
  const [contamination, setContamination] = useState(0.01)
  const [z, setZ] = useState(3)
  const [features, setFeatures] = useState(Object.keys(FEATURES))
  const [out, setOut] = useState(null)
  const [sel, setSel] = useState(null)
  const act = useAction()
  const last = useGet('/anomalies/results', null, { enabled: true })
  const rec = useGet(sel ? `/events/${sel.event_id}` : null, null, { enabled: !!sel })

  async function run() {
    const r = await act.run((api) => api.post('/anomalies/run', { method, contamination: Number(contamination), z_threshold: Number(z), features, top: 100 }))
    if (r) { setOut(r.data); setSel(null); last.reload() }
  }
  const shown = out || (last.data ? { ...last.data.summary, results: last.data.results, notes: [], caveat: 'An anomaly is an unusual record, not necessarily an error and not necessarily dangerous. Showing your most recent saved run.' } : null)

  return (
    <>
      <PageHeader title="Anomaly Detection" subtitle="Find historical records that look unusual compared with the rest. An unusual record may be a rare severe event, a reporting quirk or a data-entry error — investigate before concluding." />
      <Gate perm="run_experiments" what="anomaly detection">
        <Card title="Run detection" className="mb-5">
          <div className="grid gap-3 md:grid-cols-4">
            <Field label="Method"><Select value={method} onChange={setMethod} options={METHODS} /></Field>
            {method !== 'statistical' ? <Field label="Expected anomaly share" hint="0.01 = about 1%"><input className="input" type="number" min="0.001" max="0.2" step="0.005" value={contamination} onChange={(e) => setContamination(e.target.value)} /></Field>
              : <Field label="Threshold (IQRs beyond quartile)"><input className="input" type="number" min="1" step="0.5" value={z} onChange={(e) => setZ(e.target.value)} /></Field>}
          </div>
          <div className="mt-3 flex flex-wrap gap-3">{Object.entries(FEATURES).map(([k, l]) => <label key={k} className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={features.includes(k)} onChange={() => setFeatures((f) => (f.includes(k) ? f.filter((x) => x !== k) : [...f, k]))} />{l}</label>)}</div>
          <div className="mt-4 flex items-center gap-3"><button className="btn" disabled={act.busy || features.length === 0} onClick={run}>{act.busy ? 'Scoring...' : 'Run detection'}</button></div>
          <div className="mt-3"><ErrorBox message={act.error} /></div>
        </Card>
      </Gate>

      {shown && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Method" value={METHODS.find((m) => m.value === shown.method)?.label || shown.method} /><Stat label="Rows scored" value={num(shown.rows_scored)} /><Stat label="Flagged" value={num(shown.anomalies_flagged)} /><Stat label="Listed below" value={shown.results.length} hint="Highest scores first" /></div>
          <Note>{shown.caveat} A DBSCAN noise point is a different concept and is not treated as an anomaly here.</Note>
          {(shown.notes || []).map((n) => <Note key={n}>{n}</Note>)}
          <DataTable onRowClick={setSel} columns={[
            { key: 'event_id', label: 'Event' }, { key: 'event_type', label: 'Type' }, { key: 'state', label: 'State' }, { key: 'begin_dt', label: 'Begin', render: (r) => r.begin_dt?.slice(0, 10) },
            { key: 'anomaly_score', label: 'Score', align: 'right' }, { key: 'classification', label: 'Class', render: (r) => <Badge tone="amber">{r.classification}</Badge> },
            { key: 'drivers', label: 'Most unusual features', render: (r) => r.drivers.map((d) => `${FEATURES[d.feature] || d.feature}=${d.value === null ? '-' : +Number(d.value).toFixed(2)}`).join(', ') },
            { key: 'deaths_total', label: 'Deaths', align: 'right' }, { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => usd(r.property_damage_usd) }]} rows={shown.results} maxHeight={480} empty="No anomalies flagged." />
          {sel && (
            <Card title={`Event ${sel.event_id}: ${sel.event_type}, ${sel.state}`} actions={<button className="btn-secondary" onClick={() => setSel(null)}>Close</button>}>
              <ul className="mb-3 space-y-1 text-sm">
                {sel.drivers.map((d) => <li key={d.feature}><b>{FEATURES[d.feature] || d.feature}</b> = {d.value === null ? 'missing' : +Number(d.value).toFixed(2)} — {Math.abs(d.robust_score ?? 0).toFixed(1)} IQRs from the typical range</li>)}
                {sel.unusual_combination && <li className="text-amber-800">Unusual combination: {sel.unusual_combination}</li>}
              </ul>
              {rec.data?.EVENT_NARRATIVE && <p className="mb-3 rounded bg-slate-50 p-3 text-sm text-slate-700">{rec.data.EVENT_NARRATIVE}</p>}
              <Link className="btn inline-flex" to={`/similar?event=${sel.event_id}`}>Compare with similar events</Link>
            </Card>
          )}
        </div>
      )}
    </>
  )
}
