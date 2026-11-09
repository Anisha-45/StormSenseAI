import { useRef, useState } from 'react'
import { useAction, useGet } from '../lib/useApi.js'
import { Async, Badge, Card, DataTable, ErrorBox, Gate, Note, PageHeader, Select, Stat, Tabs } from '../components/ui.jsx'
import { BarBlock } from '../components/charts.jsx'
import { num, pct } from '../lib/format.js'

function Report({ q }) {
  const comps = Object.entries(q.score_components || {}).map(([name, v]) => ({ name: name.replace('_', ' '), score: Math.round(v * 1000) / 10 }))
  const miss = [...(q.column_profile || [])].filter((c) => c.missing_pct > 0).sort((a, b) => b.missing_pct - a.missing_pct).slice(0, 18).map((c) => ({ name: c.name, pct: c.missing_pct }))
  const checks = [
    ...Object.entries(q.date_checks || {}).map(([k, v]) => ({ id: `d-${k}`, area: 'Dates', item: k, checked: v.checked, invalid: v.invalid })),
    ...Object.entries(q.coordinate_checks || {}).map(([k, v]) => ({ id: `c-${k}`, area: 'Coordinates', item: k, checked: v.checked, invalid: v.invalid })),
    ...Object.entries(q.numeric_checks || {}).map(([k, v]) => ({ id: `n-${k}`, area: 'Numeric', item: k, checked: v.checked, invalid: v.invalid })),
  ]
  const variants = Object.entries(q.event_types?.inconsistent_variants || {})
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Quality score" value={`${q.quality_score}/100`} hint="Project-defined, not an official NOAA score" />
        <Stat label="Rows" value={num(q.rows)} />
        <Stat label="Columns" value={num(q.columns)} />
        <Stat label="Missing cells" value={pct(q.missing_pct_overall)} />
        <Stat label="Duplicate rows" value={num(q.duplicate_rows)} hint={q.identifier ? `${num(q.identifier.duplicated_ids)} duplicate ${q.identifier.column}s` : undefined} />
      </div>
      <Note>
        <b>How the score works:</b> 40% completeness + 20% uniqueness + 15% date validity + 15% coordinate validity + 10% numeric validity.
        Structurally sparse columns (such as tornado-only fields) lower completeness on purpose; they are listed below.
        {q.not_evaluated?.length > 0 && <> Not evaluated for this file (scored neutral): {q.not_evaluated.join(', ')}.</>}
      </Note>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Score components (%)"><BarBlock data={comps} x="name" bars="score" height={240} colorByIndex /></Card>
        <Card title="Columns with most missing values (%)"><BarBlock data={miss} x="name" bars="pct" layout="vertical" height={340} /></Card>
      </div>
      <Card title="Validity checks">
        <DataTable columns={[{ key: 'area', label: 'Area' }, { key: 'item', label: 'Column' }, { key: 'checked', label: 'Checked', align: 'right', render: (r) => num(r.checked) },
          { key: 'invalid', label: 'Invalid', align: 'right', render: (r) => (r.invalid ? <Badge tone="red">{num(r.invalid)}</Badge> : <Badge tone="green">0</Badge>) }]} rows={checks} empty="No date, coordinate or numeric checks apply to this file." />
      </Card>
      {variants.length > 0 && <Note tone="warn" title="Inconsistent event type spellings:">{variants.map(([k, v]) => `${k}: ${v.join(' / ')}`).join('; ')}</Note>}
      {q.structurally_sparse_columns?.length > 0 && <Card title="Structurally sparse columns (≥90% empty)"><p className="text-sm text-slate-600">{q.structurally_sparse_columns.join(', ')}</p></Card>}
      <Card title="Column profile">
        <DataTable maxHeight={420} columns={[{ key: 'name', label: 'Column' }, { key: 'dtype', label: 'Type' }, { key: 'kind', label: 'Kind' },
          { key: 'missing', label: 'Missing', align: 'right', render: (r) => num(r.missing) }, { key: 'missing_pct', label: 'Missing %', align: 'right' }, { key: 'unique', label: 'Unique', align: 'right', render: (r) => num(r.unique) }]} rows={q.column_profile.map((c) => ({ ...c, id: c.name }))} />
      </Card>
      {q.preview?.length > 0 && (
        <Card title="Record preview (first rows, source values)">
          <div className="overflow-auto"><DataTable maxHeight={320} columns={Object.keys(q.preview[0]).slice(0, 14).map((k) => ({ key: k, label: k }))} rows={q.preview.map((r, i) => ({ ...r, id: i }))} /></div>
        </Card>
      )}
    </div>
  )
}

export default function DataQuality() {
  const [tab, setTab] = useState('details')
  const [uploadId, setUploadId] = useState('')
  const datasets = useGet('/datasets')
  const builtin = useGet('/datasets/builtin/quality', { table: tab }, { enabled: tab !== 'upload' })
  const upload = useGet(uploadId ? `/datasets/${uploadId}/quality` : null, null, { enabled: tab === 'upload' && !!uploadId })
  const act = useAction()
  const fileRef = useRef(null)

  async function doUpload() {
    const file = fileRef.current?.files?.[0]
    if (!file) return act.setError('Choose a CSV file first.')
    const body = new FormData()
    body.append('file', file)
    const r = await act.run((api) => api.post('/datasets/upload', body))
    if (r) { setUploadId(String(r.data.id)); datasets.reload() }
  }

  return (
    <>
      <PageHeader title="Data Quality" subtitle="Inspect structure, missing values, duplicates, date and coordinate validity before analysing. Raw files are never modified." />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'details', label: 'NOAA details' }, { value: 'locations', label: 'NOAA locations' }, { value: 'fatalities', label: 'NOAA fatalities' }, { value: 'upload', label: 'Upload your own CSV' }]} />
      {tab !== 'upload' && <Async state={builtin}>{(q) => <Report q={q} />}</Async>}
      {tab === 'upload' && (
        <div className="space-y-4">
          <Gate perm="upload_data" what="dataset upload">
            <Card title="Upload a CSV" subtitle="Max 100 MB. Only .csv; the file is stored untouched and profiled.">
              <div className="flex flex-wrap items-center gap-3">
                <input ref={fileRef} type="file" accept=".csv,text/csv" className="text-sm" />
                <button className="btn" disabled={act.busy} onClick={doUpload}>{act.busy ? 'Uploading...' : 'Upload and analyse'}</button>
              </div>
              <div className="mt-3"><ErrorBox message={act.error} /></div>
            </Card>
          </Gate>
          <Card title="Your uploaded datasets">
            <Async state={datasets} empty={(d) => d.uploads.length === 0}>
              {(d) => <Select value={uploadId} onChange={setUploadId} placeholder="Choose an upload" options={d.uploads.map((u) => ({ value: u.id, label: `#${u.id} ${u.name} (${num(u.rows)} rows, score ${u.quality_score})` }))} />}
            </Async>
          </Card>
          {uploadId && <Async state={upload}>{(q) => <Report q={q} />}</Async>}
        </div>
      )}
    </>
  )
}
