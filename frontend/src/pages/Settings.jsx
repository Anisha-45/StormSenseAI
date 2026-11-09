import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAction, useGet } from '../lib/useApi.js'
import { Async, Badge, Card, DataTable, ErrorBox, Field, Gate, Note, PageHeader, Select } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { can } from '../lib/format.js'

const ROLES = ['citizen', 'researcher', 'responder', 'coordinator', 'administrator']

function Admin() {
  const users = useGet('/admin/users')
  const audit = useGet('/admin/audit-log', { limit: 100 })
  const act = useAction()
  const [f, setF] = useState({ email: '', name: '', password: '', role: 'coordinator' })
  const [msg, setMsg] = useState(null)
  async function create(e) {
    e.preventDefault()
    setMsg(null)
    const r = await act.run((api) => api.post('/auth/users', f))
    if (r) { setMsg(`Created ${r.data.email} as ${r.data.role}.`); setF({ ...f, email: '', name: '', password: '' }); users.reload(); audit.reload() }
  }
  return (
    <div className="space-y-5">
      <Card title="Create a staff account" subtitle="Elevated roles can only be granted here, never by self-registration.">
        <form onSubmit={create} className="grid gap-3 md:grid-cols-5">
          <Field label="Name"><input className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Email"><input className="input" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label="Temporary password"><input className="input" type="password" required minLength={8} autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          <Field label="Role"><Select value={f.role} onChange={(v) => setF({ ...f, role: v })} options={ROLES} /></Field>
          <div className="flex items-end"><button className="btn w-full" disabled={act.busy}>Create</button></div>
        </form>
        <div className="mt-3 space-y-2"><ErrorBox message={act.error} />{msg && <Note>{msg}</Note>}</div>
      </Card>
      <Card title="Users"><Async state={users}>{(rows) => <DataTable rows={rows} columns={[{ key: 'id', label: '#' }, { key: 'name', label: 'Name' }, { key: 'email', label: 'Email' }, { key: 'role', label: 'Role', render: (r) => <Badge tone="blue">{r.role}</Badge> }, { key: 'created_at', label: 'Created', render: (r) => r.created_at.slice(0, 10) }]} />}</Async></Card>
      <Card title="Audit log" subtitle="Administrative and review actions"><Async state={audit}>{(rows) => <DataTable rows={rows} maxHeight={320} empty="Nothing logged yet." columns={[{ key: 'created_at', label: 'Time', render: (r) => r.created_at.slice(0, 19).replace('T', ' ') }, { key: 'user_id', label: 'User' }, { key: 'action', label: 'Action' }, { key: 'target', label: 'Target' }, { key: 'detail', label: 'Detail' }]} />}</Async></Card>
    </div>
  )
}

export default function Settings() {
  const { user } = useAuth()
  const health = useGet('/health')
  return (
    <>
      <PageHeader title="Settings & Administration" subtitle="Your account, system status and the limitations to keep in mind when using StormSense AI." />
      <div className="space-y-5">
        <Card title="Account">
          {user ? <dl className="grid gap-2 text-sm md:grid-cols-3"><div><dt className="label">Name</dt><dd>{user.name}</dd></div><div><dt className="label">Email</dt><dd>{user.email}</dd></div><div><dt className="label">Role</dt><dd><Badge tone="blue">{user.role}</Badge></dd></div></dl>
            : <p className="text-sm text-slate-600">You are browsing without an account. <Link to="/login" className="text-storm-700 underline">Sign in or register</Link> to run experiments, report incidents or generate reports.</p>}
        </Card>
        <Card title="System status"><Async state={health}>{(h) => <p className="text-sm">API: <Badge tone="green">{h.status}</Badge> · Dataset processed: {h.dataset_processed ? <Badge tone="green">yes</Badge> : <Badge tone="red">no — run <code>python -m app.cli process</code></Badge>}</p>}</Async></Card>
        <Card title="Roles and what they can do">
          <DataTable rows={[
            { id: 1, role: 'citizen', can: 'View analytics, submit and track own incident reports' },
            { id: 2, role: 'researcher', can: 'Everything citizens can view, plus upload CSVs, run clustering and anomaly experiments, generate reports' },
            { id: 3, role: 'responder', can: 'View all incidents, resources and own tasks; update own tasks' },
            { id: 4, role: 'coordinator', can: 'Review and verify incidents, manage resources, assignments and tasks, generate reports' },
            { id: 5, role: 'administrator', can: 'All of the above plus user management and the audit log' }]} columns={[{ key: 'role', label: 'Role' }, { key: 'can', label: 'Permissions' }]} />
        </Card>
        <Card title="Known limitations">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            <li>The details file covers Feb 2017 – Sep 2020, and about 94% of events are from 2020, so year-over-year comparisons are unreliable.</li>
            <li>About 23% of events (mostly forecast-zone types such as heat, drought and winter storms) have no coordinates and cannot be mapped or used in spatial analysis.</li>
            <li>The locations and fatalities files cover many events that are not in the details file. Only matching events are joined; the rest are counted and logged.</li>
            <li>Damage values are NWS estimates and are missing for roughly a fifth of events.</li>
            <li>Clustering describes similarity between historical records. It does not predict future weather, and a historical hotspot is not a forecast of danger.</li>
            <li>Silhouette, Davies-Bouldin and Calinski-Harabasz favour compact groups, are computed without noise points, and the best score is not automatically the most useful solution.</li>
            <li>Hierarchical clustering is limited to a sample (default cap 15,000 rows) because its memory use grows with the square of the sample size.</li>
            <li>Live alerts need internet access to api.weather.gov; routes need access to the OSRM server. No road-closure feed is integrated.</li>
          </ul>
        </Card>
        {can(user, 'admin') ? <Admin /> : <Gate perm="admin" what="administration" />}
      </div>
    </>
  )
}
