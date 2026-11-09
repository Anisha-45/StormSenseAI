import { useAction, useGet } from '../lib/useApi.js'
import { Async, Badge, Card, DataTable, ErrorBox, Gate, Note, PageHeader, Stat } from '../components/ui.jsx'
import { num } from '../lib/format.js'

export default function ProcessingStudio() {
  const rep = useGet('/processing/latest/report')
  const man = useGet('/processing/latest')
  const act = useAction()

  async function rerun() {
    const r = await act.run((api) => api.post('/processing/run', {}))
    if (r) { rep.reload(); man.reload() }
  }

  return (
    <>
      <PageHeader title="Data Processing Studio" subtitle="How the three NOAA files become one clean event table. Every decision and every problem found is listed here.">
        <Gate perm="upload_data" what="re-running the pipeline"><button className="btn" disabled={act.busy} onClick={rerun}>{act.busy ? 'Processing...' : 'Re-run pipeline'}</button></Gate>
      </PageHeader>
      <ErrorBox message={act.error} />
      <div className="space-y-5">
        <Async state={man}>
          {(m) => (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Unique events" value={num(m.unique_events)} hint="One row per EVENT_ID" />
                <Stat label="With coordinates" value={num(m.events_with_coordinates)} />
                <Stat label="With location rows" value={num(m.events_with_location_rows)} hint="locations table, aggregated" />
                <Stat label="With fatality rows" value={num(m.events_with_fatality_rows)} hint="fatalities table, aggregated" />
              </div>
              <Card title="Raw rows read" subtitle={`Dataset version ${m.dataset_version} · processed in ${m.processing_seconds}s`}>
                <DataTable columns={[{ key: 'table', label: 'Table' }, { key: 'rows', label: 'Rows', align: 'right', render: (r) => num(r.rows) }]} rows={Object.entries(m.raw_row_counts).map(([table, rows]) => ({ id: table, table, rows }))} />
              </Card>
              <Card title="Events per year after processing"><DataTable columns={[{ key: 'year', label: 'Year' }, { key: 'events', label: 'Events', align: 'right', render: (r) => num(r.events) }]} rows={Object.entries(m.year_counts).map(([year, events]) => ({ id: year, year, events }))} /></Card>
            </>
          )}
        </Async>
        <Async state={rep}>
          {(r) => (
            <>
              <Card title="Issues found and how they were handled" subtitle="Nothing is dropped silently. Everything below is counted and kept in the manifest.">
                <DataTable columns={[{ key: 'table', label: 'Table', render: (i) => <Badge tone="blue">{i.table}</Badge> }, { key: 'issue', label: 'Issue' }, { key: 'count', label: 'Count', align: 'right', render: (i) => num(i.count) }, { key: 'detail', label: 'Detail' }]} rows={r.issues.map((i, n) => ({ ...i, id: n }))} empty="No issues logged." />
              </Card>
              <Card title="Method notes"><ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul></Card>
              <Card title="Processing configuration"><pre className="overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(r.config, null, 2)}</pre></Card>
              <Card title="Features available for clustering" subtitle="Choose them in the Clustering Lab. Defaults are marked.">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="label">Numerical (standardised)</div>
                    <ul className="space-y-1 text-sm">{Object.entries(r.features_available.numeric).map(([k, v]) => <li key={k}><code className="rounded bg-slate-100 px-1">{k}</code> {r.features_available.default.includes(k) && <Badge tone="green">default</Badge>} <span className="text-slate-500">{v}</span></li>)}</ul>
                  </div>
                  <div>
                    <div className="label">Categorical (one-hot encoded)</div>
                    <ul className="space-y-1 text-sm">{Object.entries(r.features_available.categorical).map(([k, v]) => <li key={k}><code className="rounded bg-slate-100 px-1">{k}</code> {r.features_available.default.includes(k) && <Badge tone="green">default</Badge>} <span className="text-slate-500">{v}</span></li>)}</ul>
                  </div>
                </div>
              </Card>
              <Note>Raw NOAA CSVs stay untouched in <code>data/raw</code>. The processed table is a separate file in <code>data/processed</code>. Original damage strings are kept beside the converted dollar values.</Note>
            </>
          )}
        </Async>
      </div>
    </>
  )
}
