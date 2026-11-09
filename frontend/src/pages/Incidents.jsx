import { useRef, useState } from 'react'
import { useAction, useGet } from '../lib/useApi.js'
import { Async, Badge, Card, DataTable, ErrorBox, Field, Gate, Note, PageHeader, Select } from '../components/ui.jsx'
import { can } from '../lib/format.js'
import { useAuth } from '../context/AuthContext.jsx'

const label = (s) => s.replace(/_/g, ' ')
const V_TONE = { unverified: 'amber', verified: 'green', rejected: 'red' }

function Report({ meta, onDone }) {
  const [form, setForm] = useState({ category: meta.categories[0], description: '', lat: '', lon: '' })
  const [msg, setMsg] = useState(null)
  const act = useAction()
  const fileRef = useRef(null)

  function locate() {
    if (!navigator.geolocation) return act.setError('This browser does not support location sharing.')
    navigator.geolocation.getCurrentPosition(
      (p) => setForm((f) => ({ ...f, lat: p.coords.latitude.toFixed(5), lon: p.coords.longitude.toFixed(5) })),
      () => act.setError('Location permission was denied. You can still submit without a location.'))
  }
  async function submit(e) {
    e.preventDefault()
    setMsg(null)
    const body = new FormData()
    body.append('category', form.category)
    body.append('description', form.description)
    if (form.lat !== '' && form.lon !== '') { body.append('lat', form.lat); body.append('lon', form.lon) }
    const file = fileRef.current?.files?.[0]
    if (file) body.append('photo', file)
    const r = await act.run((api) => api.post('/incidents', body))
    if (r) { setMsg('Report submitted. It is marked unverified until staff review it.'); setForm({ ...form, description: '' }); if (fileRef.current) fileRef.current.value = ''; onDone() }
  }
  return (
    <Card title="Report an incident" subtitle="Describe a weather-related problem you can see. In an emergency call your local emergency number first.">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Category"><Select value={form.category} onChange={(v) => setForm({ ...form, category: v })} options={meta.categories.map((c) => ({ value: c, label: label(c) }))} /></Field>
        <Field label="Description" hint={`${form.description.length}/2000 characters (min 10)`}><textarea className="input h-24" required minLength={10} maxLength={2000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Latitude (optional)"><input className="input" type="number" step="any" min="-90" max="90" value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} /></Field>
          <Field label="Longitude (optional)"><input className="input" type="number" step="any" min="-180" max="180" value={form.lon} onChange={(e) => setForm({ ...form, lon: e.target.value })} /></Field>
        </div>
        <button type="button" className="btn-secondary" onClick={locate}>Use my current location</button>
        <Field label="Photo (optional, JPEG or PNG, max 5 MB)"><input ref={fileRef} type="file" accept="image/jpeg,image/png" className="text-sm" /></Field>
        <ErrorBox message={act.error} />
        {msg && <Note tone="info">{msg}</Note>}
        <button className="btn" disabled={act.busy}>{act.busy ? 'Submitting...' : 'Submit report'}</button>
        <p className="text-xs text-slate-500">{meta.notice} Your location and photo are visible only to you and authorised response staff.</p>
      </form>
    </Card>
  )
}

export default function Incidents() {
  const { user } = useAuth()
  const staff = can(user, 'review_incidents')
  const meta = useGet('/incidents/categories')
  const [filter, setFilter] = useState({ status: '', verification: '' })
  const list = useGet(user ? '/incidents' : null, filter, { enabled: !!user })
  const act = useAction()
  const [note, setNote] = useState({})

  async function review(id, patch) {
    const r = await act.run((api) => api.patch(`/incidents/${id}/status`, { ...patch, note: note[id] || undefined }))
    if (r) list.reload()
  }

  const cols = [
    { key: 'id', label: '#' }, { key: 'category', label: 'Category', render: (r) => label(r.category) }, { key: 'description', label: 'Description', render: (r) => <span className="line-clamp-2 max-w-md">{r.description}</span> },
    { key: 'status', label: 'Status', render: (r) => <Badge tone="blue">{label(r.status)}</Badge> },
    { key: 'verification', label: 'Verification', render: (r) => <Badge tone={V_TONE[r.verification]}>{r.verification}</Badge> },
    { key: 'created_at', label: 'Submitted', render: (r) => r.created_at.slice(0, 16).replace('T', ' ') },
    ...(staff ? [{ key: 'review', label: 'Review', render: (r) => (
      <div className="flex min-w-[220px] flex-col gap-1" onClick={(e) => e.stopPropagation()}>
        <input className="input !py-1 text-xs" placeholder="Review note" value={note[r.id] || ''} onChange={(e) => setNote({ ...note, [r.id]: e.target.value })} />
        <div className="flex flex-wrap gap-1">
          <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => review(r.id, { verification: 'verified', status: 'under_review' })}>Verify</button>
          <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => review(r.id, { verification: 'rejected', status: 'dismissed' })}>Reject</button>
          <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => review(r.id, { status: 'resolved' })}>Resolve</button>
        </div>
      </div>) }] : []),
  ]

  return (
    <>
      <PageHeader title="Incident Reporting" subtitle="Citizens report weather-related incidents; authorised staff review them. Citizen reports are never official until verified." />
      <Gate perm="report_incident" what="incident reporting">
        <div className="grid gap-5 lg:grid-cols-3">
          <div><Async state={meta}>{(m) => <Report meta={m} onDone={list.reload} />}</Async></div>
          <div className="space-y-3 lg:col-span-2">
            {staff && (
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Status filter"><Select value={filter.status} onChange={(v) => setFilter({ ...filter, status: v })} options={(meta.data?.statuses || []).map((s) => ({ value: s, label: label(s) }))} placeholder="All" /></Field>
                <Field label="Verification filter"><Select value={filter.verification} onChange={(v) => setFilter({ ...filter, verification: v })} options={meta.data?.verifications || []} placeholder="All" /></Field>
              </div>
            )}
            <ErrorBox message={act.error} />
            <Card title={staff ? 'All incident reports' : 'Your reports'}>
              <Async state={list}>{(rows) => <DataTable columns={cols} rows={rows} empty="No reports yet." />}</Async>
            </Card>
          </div>
        </div>
      </Gate>
    </>
  )
}
