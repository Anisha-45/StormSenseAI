import { useState } from 'react'
import { useGet } from '../lib/useApi.js'
import { Async, Badge, Card, Field, Note, PageHeader, Select } from '../components/ui.jsx'
import MapView from '../components/MapView.jsx'

const SEV_TONE = { Extreme: 'red', Severe: 'red', Moderate: 'amber', Minor: 'blue', Unknown: 'slate' }
const SEV_COLOR = { Extreme: '#b42318', Severe: '#d4380d', Moderate: '#d48806', Minor: '#2f7de1', Unknown: '#6c757d' }
const STATES = 'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR GU'.split(' ')

export default function LiveAlerts() {
  const [state, setState] = useState('')
  const [severity, setSeverity] = useState('')
  const [event, setEvent] = useState('')
  const [open, setOpen] = useState(null)
  const res = useGet('/alerts', { state, severity, event })

  return (
    <>
      <PageHeader title="Live Weather Alerts" subtitle="Current official alerts from the US National Weather Service. This page is completely separate from the historical clustering results.">
        <button className="btn" onClick={res.reload} disabled={res.loading}>{res.loading ? 'Refreshing...' : 'Refresh'}</button>
      </PageHeader>
      <Note tone="danger" title="Not a warning system.">StormSense AI only relays alerts published by the NWS. For emergencies follow official instructions and call your local emergency number. Historical analysis elsewhere in this app is never an alert.</Note>
      <Card className="my-4"><div className="grid gap-3 md:grid-cols-3">
        <Field label="State (US)"><Select value={state} onChange={setState} options={STATES} placeholder="All of the US" /></Field>
        <Field label="Severity"><Select value={severity} onChange={setSeverity} options={['Extreme', 'Severe', 'Moderate', 'Minor']} placeholder="Any" /></Field>
        <Field label="Alert type contains"><input className="input" placeholder="e.g. Flood" value={event} onChange={(e) => setEvent(e.target.value)} /></Field>
      </div></Card>
      <Async state={res}>
        {(d) => {
          const withGeo = d.alerts.filter((a) => a.geometry)
          return (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">{d.count} active alert(s) · source {d.source} · last updated {d.fetched_at ? new Date(d.fetched_at).toLocaleString() : 'unknown'}</p>
              {d.stale && <Note tone="warn" title="Showing older data.">{d.error}</Note>}
              {withGeo.length > 0 && <MapView height={380} fit={false} geojson={withGeo.slice(0, 150).map((a) => ({ key: a.id, data: { type: 'Feature', geometry: a.geometry, properties: {} }, color: SEV_COLOR[a.severity] || SEV_COLOR.Unknown, popup: <div className="text-xs"><b>{a.event}</b><br />{a.area}</div> }))} />}
              {d.alerts.length === 0 && <Note tone="info">No active alerts match these filters right now.</Note>}
              <ul className="space-y-3">
                {d.alerts.slice(0, 100).map((a) => (
                  <li key={a.id} className="card">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={SEV_TONE[a.severity] || 'slate'}>{a.severity || 'Unknown'}</Badge>
                      <span className="font-semibold text-slate-900">{a.event}</span>
                      {a.urgency && <Badge>{a.urgency}</Badge>}
                    </div>
                    <p className="mt-1 text-sm text-slate-700">{a.headline}</p>
                    <p className="mt-1 text-xs text-slate-500">Area: {a.area}</p>
                    <p className="text-xs text-slate-500">Issued {a.sent ? new Date(a.sent).toLocaleString() : '-'} · Expires {a.expires ? new Date(a.expires).toLocaleString() : '-'} · {a.sender}</p>
                    <div className="mt-2 flex items-center gap-3 text-sm">
                      <button className="text-storm-700 hover:underline" onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? 'Hide details' : 'Details'}</button>
                      {a.source_url && <a className="text-storm-700 hover:underline" href={a.source_url} target="_blank" rel="noreferrer">Official source</a>}
                    </div>
                    {open === a.id && <div className="mt-2 whitespace-pre-line rounded bg-slate-50 p-3 text-sm text-slate-700">{a.description}{a.instruction && `\n\nInstructions: ${a.instruction}`}</div>}
                  </li>
                ))}
              </ul>
              <p className="text-xs italic text-slate-500">{d.disclaimer}</p>
            </div>
          )
        }}
      </Async>
    </>
  )
}
