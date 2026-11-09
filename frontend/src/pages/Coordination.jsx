import { useState } from 'react'
import { useAction, useGet } from '../lib/useApi.js'
import { Async, Badge, Card, DataTable, ErrorBox, Field, Gate, Note, PageHeader, Select, Stat } from '../components/ui.jsx'
import MapView from '../components/MapView.jsx'
import { can, num } from '../lib/format.js'
import { useAuth } from '../context/AuthContext.jsx'
import { Link } from 'react-router-dom'

const T_NEXT = { open: 'in_progress', in_progress: 'done' }

export default function Coordination() {
  const { user } = useAuth()
  const manage = can(user, 'manage_tasks')
  const ov = useGet('/coordination/overview', null, { enabled: can(user, 'view_all_incidents') })
  const tasks = useGet('/tasks', null, { enabled: can(user, 'view_tasks') })
  const alerts = useGet('/alerts', null, { enabled: can(user, 'view_all_incidents') })
  const act = useAction()
  const [t, setT] = useState({ title: '', description: '', incident_id: '', assignee_id: '' })

  async function addTask(e) {
    e.preventDefault()
    const body = { title: t.title, description: t.description || null, ...(t.incident_id ? { incident_id: Number(t.incident_id) } : {}), ...(t.assignee_id ? { assignee_id: Number(t.assignee_id) } : {}) }
    const r = await act.run((api) => api.post('/tasks', body))
    if (r) { setT({ title: '', description: '', incident_id: '', assignee_id: '' }); tasks.reload(); ov.reload() }
  }
  async function advance(task, status) {
    const r = await act.run((api) => api.patch(`/tasks/${task.id}/status`, { status }))
    if (r) { tasks.reload(); ov.reload() }
  }
  const sumBy = (rows, pred) => rows.filter(pred).reduce((s, r) => s + r.n, 0)

  return (
    <>
      <PageHeader title="Response Coordination" subtitle="One view of official alerts, citizen reports, resources and tasks for authorised staff. All numbers are records entered into this system." />
      <Gate perm="view_all_incidents" what="the coordination dashboard">
        <ErrorBox message={act.error} />
        <div className="space-y-5">
          <Async state={ov}>
            {(d) => {
              const open = sumBy(d.incidents, (r) => !['resolved', 'dismissed'].includes(r.status))
              const unverified = sumBy(d.incidents, (r) => r.verification === 'unverified')
              const verified = sumBy(d.incidents, (r) => r.verification === 'verified')
              const avail = d.resources.reduce((s, r) => s + r.available, 0)
              return (
                <>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                    <Stat label="Open incidents" value={num(open)} /><Stat label="Unverified" value={num(unverified)} hint="Not official" /><Stat label="Verified" value={num(verified)} />
                    <Stat label="Resources available" value={num(avail)} hint={`${d.resources.length} kind(s) registered`} /><Stat label="Open tasks" value={num(sumBy(d.tasks, (r) => ['open', 'in_progress'].includes(r.status)))} />
                  </div>
                  <div className="grid gap-5 lg:grid-cols-2">
                    <Card title="Open incident locations" subtitle="Only reports that included a location">
                      {d.open_incident_locations.length === 0 ? <p className="text-sm text-slate-500">No open reports with a location.</p> :
                        <MapView height={340} points={d.open_incident_locations.map((i) => ({ key: i.id, lat: i.lat, lon: i.lon, color: i.verification === 'verified' ? '#1a7f4b' : '#d48806', radius: 7, tooltip: `#${i.id} ${i.category.replace('_', ' ')} (${i.verification})` }))} legend={<span>Green = verified · Amber = unverified</span>} />}
                    </Card>
                    <Card title="Official alerts (National Weather Service)">
                      <Async state={alerts}>{(a) => (<><p className="mb-2 text-sm text-slate-600">{a.count} active nationwide{a.stale ? ' (cached)' : ''}. <Link className="text-storm-700 underline" to="/alerts">Open Live Alerts</Link></p><ul className="max-h-72 space-y-2 overflow-auto text-sm">{a.alerts.slice(0, 8).map((x) => <li key={x.id} className="rounded border border-slate-200 p-2"><b>{x.event}</b> · {x.severity}<br /><span className="text-xs text-slate-500">{x.area}</span></li>)}</ul></>)}</Async>
                    </Card>
                  </div>
                  <Card title="Resources by kind"><DataTable columns={[{ key: 'kind', label: 'Kind' }, { key: 'records', label: 'Records', align: 'right' }, { key: 'total', label: 'Total', align: 'right' }, { key: 'available', label: 'Available', align: 'right' }]} rows={d.resources.map((r) => ({ ...r, id: r.kind }))} empty="No resources registered yet." /></Card>
                  <Card title="Recent activity (audit trail)"><DataTable columns={[{ key: 'created_at', label: 'Time', render: (r) => r.created_at.slice(0, 19).replace('T', ' ') }, { key: 'action', label: 'Action' }, { key: 'target', label: 'Target' }, { key: 'detail', label: 'Detail' }]} rows={d.recent_activity.map((r, i) => ({ ...r, id: i }))} empty="No activity yet." maxHeight={260} /></Card>
                  <Note>{d.notice}</Note>
                </>
              )
            }}
          </Async>
          <Gate perm="view_tasks" what="tasks">
            <div className="grid gap-5 lg:grid-cols-3">
              {manage && (
                <Card title="Create a task">
                  <form onSubmit={addTask} className="space-y-3">
                    <Field label="Title"><input className="input" required minLength={3} value={t.title} onChange={(e) => setT({ ...t, title: e.target.value })} /></Field>
                    <Field label="Description"><textarea className="input h-20" value={t.description} onChange={(e) => setT({ ...t, description: e.target.value })} /></Field>
                    <div className="grid grid-cols-2 gap-2"><Field label="Incident #"><input className="input" type="number" min="1" value={t.incident_id} onChange={(e) => setT({ ...t, incident_id: e.target.value })} /></Field><Field label="Assignee user #"><input className="input" type="number" min="1" value={t.assignee_id} onChange={(e) => setT({ ...t, assignee_id: e.target.value })} /></Field></div>
                    <button className="btn w-full" disabled={act.busy}>Create task</button>
                  </form>
                </Card>
              )}
              <div className={manage ? 'lg:col-span-2' : 'lg:col-span-3'}>
                <Card title={manage ? 'All tasks' : 'Tasks assigned to you'}>
                  <Async state={tasks}>{(rows) => <DataTable empty="No tasks yet." rows={rows} columns={[{ key: 'id', label: '#' }, { key: 'title', label: 'Task' }, { key: 'incident_id', label: 'Incident' }, { key: 'assignee_id', label: 'Assignee' }, { key: 'status', label: 'Status', render: (r) => <Badge tone={r.status === 'done' ? 'green' : 'blue'}>{r.status.replace('_', ' ')}</Badge> },
                    { key: 'a', label: '', render: (r) => (T_NEXT[r.status] ? <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => advance(r, T_NEXT[r.status])}>Mark {T_NEXT[r.status].replace('_', ' ')}</button> : null) }]} />}</Async>
                </Card>
              </div>
            </div>
          </Gate>
        </div>
      </Gate>
    </>
  )
}
