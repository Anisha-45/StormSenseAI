import { useState } from 'react'
import { useAction, useGet } from '../lib/useApi.js'
import { Async, Badge, Card, DataTable, ErrorBox, Field, Gate, Note, PageHeader, Select, Tabs } from '../components/ui.jsx'
import { can, num } from '../lib/format.js'
import { useAuth } from '../context/AuthContext.jsx'

const KINDS = [{ value: 'ambulance', label: 'Ambulance' }, { value: 'rescue_team', label: 'Rescue team' }, { value: 'relief_supplies', label: 'Relief supplies' }, { value: 'other', label: 'Other' }]
const A_TONE = { proposed: 'amber', approved: 'blue', active: 'blue', completed: 'green', cancelled: 'slate' }

export default function Resources() {
  const { user } = useAuth()
  const manage = can(user, 'manage_resources')
  const [tab, setTab] = useState('resources')
  const [kind, setKind] = useState('')
  const res = useGet('/resources', { kind }, { enabled: can(user, 'view_resources') })
  const asg = useGet('/assignments', null, { enabled: can(user, 'view_resources') })
  const act = useAction()
  const [form, setForm] = useState({ kind: 'ambulance', name: '', quantity: 1, lat: '', lon: '', notes: '' })
  const [propose, setPropose] = useState({ resource_id: '', quantity: 1, incident_id: '' })

  async function add(e) {
    e.preventDefault()
    const body = { kind: form.kind, name: form.name, quantity: Number(form.quantity), notes: form.notes || null, ...(form.lat !== '' && form.lon !== '' ? { lat: Number(form.lat), lon: Number(form.lon) } : {}) }
    const r = await act.run((api) => api.post('/resources', body))
    if (r) { setForm({ ...form, name: '', notes: '' }); res.reload() }
  }
  async function patchAvail(r, available) {
    const x = await act.run((api) => api.patch(`/resources/${r.id}`, { available }))
    if (x) res.reload()
  }
  async function proposeAssignment(e) {
    e.preventDefault()
    const r = await act.run((api) => api.post('/assignments', { resource_id: Number(propose.resource_id), quantity: Number(propose.quantity), ...(propose.incident_id ? { incident_id: Number(propose.incident_id) } : {}) }))
    if (r) { asg.reload() }
  }
  async function setStatus(id, status) {
    const r = await act.run((api) => api.patch(`/assignments/${id}/status`, { status }))
    if (r) { asg.reload(); res.reload() }
  }

  return (
    <>
      <PageHeader title="Emergency Resource Management" subtitle="Authorised staff track ambulances, rescue teams and relief supplies. Every record is entered by a person; nothing is pre-loaded or simulated." />
      <Gate perm="view_resources" what="resource management">
        <ErrorBox message={act.error} />
        <Tabs value={tab} onChange={setTab} tabs={[{ value: 'resources', label: 'Resources' }, { value: 'assignments', label: 'Assignments' }]} />
        {tab === 'resources' && (
          <div className="grid gap-5 lg:grid-cols-3">
            {manage && (
              <Card title="Register a resource">
                <form onSubmit={add} className="space-y-3">
                  <Field label="Kind"><Select value={form.kind} onChange={(v) => setForm({ ...form, kind: v })} options={KINDS} /></Field>
                  <Field label="Name / identifier"><input className="input" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
                  <Field label="Quantity"><input className="input" type="number" min="0" required value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="Lat (optional)"><input className="input" type="number" step="any" value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} /></Field>
                    <Field label="Lon (optional)"><input className="input" type="number" step="any" value={form.lon} onChange={(e) => setForm({ ...form, lon: e.target.value })} /></Field>
                  </div>
                  <Field label="Notes"><input className="input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
                  <button className="btn w-full" disabled={act.busy}>Add resource</button>
                </form>
              </Card>
            )}
            <div className={manage ? 'lg:col-span-2' : 'lg:col-span-3'}>
              <div className="mb-3 max-w-xs"><Select value={kind} onChange={setKind} options={KINDS} placeholder="All kinds" /></div>
              <Async state={res}>
                {(d) => (
                  <>
                    <DataTable empty="No resources have been registered yet." rows={d.resources} columns={[
                      { key: 'id', label: '#' }, { key: 'kind', label: 'Kind', render: (r) => r.kind.replace('_', ' ') }, { key: 'name', label: 'Name' },
                      { key: 'quantity', label: 'Total', align: 'right', render: (r) => num(r.quantity) },
                      { key: 'available', label: 'Available', align: 'right', render: (r) => (manage ? (
                        <span className="inline-flex items-center gap-1"><button className="btn-secondary !px-2 !py-0.5" aria-label="Decrease available" disabled={r.available <= 0} onClick={() => patchAvail(r, r.available - 1)}>−</button>{r.available}<button className="btn-secondary !px-2 !py-0.5" aria-label="Increase available" disabled={r.available >= r.quantity} onClick={() => patchAvail(r, r.available + 1)}>+</button></span>) : r.available) },
                      { key: 'location', label: 'Location', render: (r) => (r.lat != null ? `${r.lat.toFixed(3)}, ${r.lon.toFixed(3)}` : '-') }, { key: 'updated_at', label: 'Updated', render: (r) => r.updated_at.slice(0, 16).replace('T', ' ') }]} />
                    <p className="mt-2 text-xs italic text-slate-500">{d.notice}</p>
                  </>
                )}
              </Async>
            </div>
          </div>
        )}
        {tab === 'assignments' && (
          <div className="space-y-5">
            <Note>Assignments start as <b>proposed</b> and reserve nothing. A person with resource-management permission must approve them, which then reduces availability. Nothing is assigned automatically.</Note>
            {manage && (
              <Card title="Propose an assignment">
                <form onSubmit={proposeAssignment} className="grid gap-3 md:grid-cols-4">
                  <Field label="Resource"><Select value={propose.resource_id} onChange={(v) => setPropose({ ...propose, resource_id: v })} placeholder="Choose..." options={(res.data?.resources || []).map((r) => ({ value: r.id, label: `#${r.id} ${r.name} (${r.available} avail.)` }))} /></Field>
                  <Field label="Quantity"><input className="input" type="number" min="1" value={propose.quantity} onChange={(e) => setPropose({ ...propose, quantity: e.target.value })} /></Field>
                  <Field label="Incident # (optional)"><input className="input" type="number" min="1" value={propose.incident_id} onChange={(e) => setPropose({ ...propose, incident_id: e.target.value })} /></Field>
                  <div className="flex items-end"><button className="btn" disabled={!propose.resource_id || act.busy}>Propose</button></div>
                </form>
              </Card>
            )}
            <Async state={asg}>
              {(rows) => <DataTable empty="No assignments yet." rows={rows} columns={[{ key: 'id', label: '#' }, { key: 'resource_id', label: 'Resource' }, { key: 'quantity', label: 'Qty', align: 'right' }, { key: 'incident_id', label: 'Incident' }, { key: 'status', label: 'Status', render: (r) => <Badge tone={A_TONE[r.status]}>{r.status}</Badge> },
                ...(manage ? [{ key: 'actions', label: 'Actions', render: (r) => (
                  <div className="flex flex-wrap gap-1">
                    {r.status === 'proposed' && <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => setStatus(r.id, 'approved')}>Approve</button>}
                    {r.status === 'approved' && <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => setStatus(r.id, 'active')}>Start</button>}
                    {['approved', 'active'].includes(r.status) && <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => setStatus(r.id, 'completed')}>Complete</button>}
                    {['proposed', 'approved', 'active'].includes(r.status) && <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => setStatus(r.id, 'cancelled')}>Cancel</button>}
                  </div>) }] : [])]} />}
            </Async>
          </div>
        )}
      </Gate>
    </>
  )
}
