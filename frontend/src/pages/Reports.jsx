import { useState } from 'react'
import { api, errorMessage } from '../api/client.js'
import { useAction, useGet } from '../lib/useApi.js'
import { Async, Card, DataTable, ErrorBox, Field, Gate, Note, PageHeader, Select } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { can } from '../lib/format.js'

export default function Reports() {
  const { user } = useAuth()
  const allowed = can(user, 'generate_reports')
  const opts = useGet('/geography/filters')
  const exps = useGet('/clustering/experiments')
  const list = useGet('/reports', null, { enabled: allowed })
  const act = useAction()
  const [dlError, setDlError] = useState(null)
  const [f, setF] = useState({ title: 'StormSense AI historical weather report', format: 'pdf', experiment_id: '', state: '', event_type: '', year: '' })
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }))

  async function generate(e) {
    e.preventDefault()
    const body = { title: f.title, format: f.format, ...(f.experiment_id ? { experiment_id: Number(f.experiment_id) } : {}), ...(f.state ? { state: f.state } : {}), ...(f.event_type ? { event_type: f.event_type } : {}), ...(f.year ? { year: Number(f.year) } : {}) }
    const r = await act.run((a) => a.post('/reports/generate', body))
    if (r) { list.reload(); download(r.data) }
  }

  // The download endpoint needs the Authorization header, so fetch as a blob instead of using a plain link.
  async function download(rep) {
    setDlError(null)
    try {
      const r = await api.get(`/reports/${rep.id}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `stormsense_report_${rep.id}.${rep.format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) { setDlError(errorMessage(e)) }
  }

  return (
    <>
      <PageHeader title="Reports" subtitle="Generate a PDF summary or a CSV export of the historical records, with data period, methodology and limitations included." />
      <Gate perm="generate_reports" what="report generation">
        <div className="grid gap-5 lg:grid-cols-3">
          <Card title="New report">
            <form onSubmit={generate} className="space-y-3">
              <Field label="Title"><input className="input" required value={f.title} onChange={(e) => set('title')(e.target.value)} /></Field>
              <Field label="Format"><Select value={f.format} onChange={set('format')} options={[{ value: 'pdf', label: 'PDF report' }, { value: 'csv', label: 'CSV data export' }]} /></Field>
              <Field label="State / region"><Select value={f.state} onChange={set('state')} options={opts.data?.states || []} placeholder="All" /></Field>
              <Field label="Event type"><Select value={f.event_type} onChange={set('event_type')} options={opts.data?.event_types || []} placeholder="All" /></Field>
              <Field label="Year"><Select value={f.year} onChange={set('year')} options={opts.data?.years || []} placeholder="All" /></Field>
              {f.format === 'pdf' && <Field label="Include clustering experiment"><Select value={f.experiment_id} onChange={set('experiment_id')} placeholder="None" options={(exps.data || []).map((e) => ({ value: e.id, label: `#${e.id} ${e.algorithm} (${e.n_clusters} clusters)` }))} /></Field>}
              <ErrorBox message={act.error || dlError} />
              <button className="btn w-full" disabled={act.busy}>{act.busy ? 'Generating...' : 'Generate and download'}</button>
            </form>
          </Card>
          <div className="space-y-4 lg:col-span-2">
            <Card title="Report history" subtitle="Your previously generated reports">
              <Async state={list}>{(rows) => <DataTable empty="No reports yet." rows={rows} columns={[{ key: 'id', label: '#' }, { key: 'title', label: 'Title' }, { key: 'format', label: 'Format', render: (r) => r.format.toUpperCase() }, { key: 'created_at', label: 'Created', render: (r) => r.created_at.slice(0, 16).replace('T', ' ') }, { key: 'dl', label: '', render: (r) => <button className="btn-secondary !py-1" onClick={() => download(r)}>Download</button> }]} />}</Async>
            </Card>
            <Note>Every report states its data source and period and lists the known limitations (partial years, missing coordinates, estimated damage). Reports describe historical records only.</Note>
          </div>
        </div>
      </Gate>
    </>
  )
}
