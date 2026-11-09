import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useGet } from '../lib/useApi.js'
import { Async, Badge, Card, DataTable, Empty, Field, Note, PageHeader, Select, Stat } from '../components/ui.jsx'
import { BarBlock } from '../components/charts.jsx'
import { MONTHS, clusterColor, num, usd } from '../lib/format.js'

function Profile({ p, experimentId }) {
  const events = useGet(`/clusters/${p.cluster_id}/events`, { experiment_id: experimentId, limit: 25 })
  const [show, setShow] = useState(false)
  const types = p.dominant_event_types.map((t) => ({ name: t.name, share: t.share_pct }))
  const months = MONTHS.map((m, i) => ({ month: m, events: p.month_distribution[i + 1] || 0 }))
  const years = Object.entries(p.year_distribution).map(([year, events]) => ({ year, events }))
  return (
    <Card className="border-l-4" title={<span className="flex items-center gap-2"><span className="inline-block h-3 w-3 rounded-full" style={{ background: clusterColor(p.cluster_id) }} />{p.is_noise ? 'Noise (unclustered)' : `Cluster ${p.cluster_id}`} · {num(p.event_count)} events ({p.share_pct}%)</span>}>
      <p className="mb-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{p.explanation}</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Deaths" value={num(p.totals.deaths)} />
        <Stat label="Injuries" value={num(p.totals.injuries)} />
        <Stat label="Property damage" value={usd(p.totals.property_damage_usd)} />
        <Stat label="Crop damage" value={usd(p.totals.crop_damage_usd)} />
        <Stat label="Median duration" value={`${p.stats.duration_hours?.median ?? '-'} h`} hint={`mean ${p.stats.duration_hours?.mean ?? '-'}`} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div><div className="label">Dominant event types (% of cluster)</div><BarBlock data={types} x="name" bars="share" layout="vertical" height={150} /></div>
        <div><div className="label">By month</div><BarBlock data={months} x="month" bars="events" height={150} /></div>
        <div><div className="label">By year</div><BarBlock data={years} x="year" bars="events" height={150} /></div>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="label">Top states / regions</div>
          <div className="flex flex-wrap gap-1">{p.top_states.map((s) => <Badge key={s.name} tone="blue">{s.name} {s.share_pct}%</Badge>)}</div>
          {p.point_types && <div className="mt-3"><div className="label">DBSCAN point types</div><div className="flex gap-2 text-sm">{Object.entries(p.point_types).map(([k, v]) => <Badge key={k}>{k}: {num(v)}</Badge>)}</div></div>}
        </div>
        <div>
          <div className="label">How this cluster differs from the whole sample</div>
          <DataTable columns={[{ key: 'feature', label: 'Feature' }, { key: 'cluster_mean', label: 'Cluster mean', align: 'right' }, { key: 'overall_mean', label: 'Overall mean', align: 'right' }, { key: 'ratio_to_overall', label: 'Ratio', align: 'right', render: (r) => `${r.ratio_to_overall}x` }]} rows={p.differences.map((d) => ({ ...d, id: d.feature }))} empty="No notable differences." />
        </div>
      </div>
      <button className="btn-secondary mt-4" onClick={() => setShow(!show)}>{show ? 'Hide' : 'Show'} example events</button>
      {show && <div className="mt-3"><Async state={events}>{(d) => <DataTable columns={[{ key: 'event_id', label: 'Event', render: (r) => <Link className="text-storm-700 underline" to={`/similar?event=${r.event_id}`}>{r.event_id}</Link> }, { key: 'event_type', label: 'Type' }, { key: 'state', label: 'State' }, { key: 'begin_dt', label: 'Begin', render: (r) => r.begin_dt?.slice(0, 16) }, { key: 'deaths_total', label: 'Deaths', align: 'right' }, { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => usd(r.property_damage_usd) }]} rows={d.events} />}</Async></div>}
    </Card>
  )
}

export default function ClusterIntelligence() {
  const exps = useGet('/clustering/experiments')
  const [id, setId] = useState('')
  useEffect(() => { if (exps.data?.length && !id) setId(String(exps.data[0].id)) }, [exps.data, id])
  const exp = useGet(id ? `/clustering/${id}` : null, null, { enabled: !!id })
  return (
    <>
      <PageHeader title="Cluster Intelligence" subtitle="Plain-language explanations built from each cluster's actual statistics. They describe historical records; they do not predict events or explain causes." />
      <Async state={exps}>
        {(rows) => rows.length === 0 ? null : (
          <div className="space-y-5">
            <Card>
              <Field label="Experiment"><Select value={id} onChange={setId} options={rows.map((r) => ({ value: r.id, label: `#${r.id} ${r.algorithm} · ${r.n_clusters} clusters · ${r.noise_pct}% noise · ${r.created_at.slice(0, 16).replace('T', ' ')}` }))} /></Field>
            </Card>
            <Async state={exp}>
              {(e) => (
                <>
                  <Note>Sample of {num(e.config.sample_size)} events (from {num(e.config.population_after_filters)}), features: {e.config.features.join(', ')}. Algorithm: <b>{e.algorithm}</b> {JSON.stringify(e.params)}.</Note>
                  {[...e.profiles].sort((a, b) => b.event_count - a.event_count).map((p) => <Profile key={p.cluster_id} p={p} experimentId={e.id} />)}
                </>
              )}
            </Async>
          </div>
        )}
      </Async>
      {exps.data && exps.data.length === 0 && <Empty>No experiments yet. Run one in the <Link className="underline" to="/clustering">Clustering Lab</Link>.</Empty>}
    </>
  )
}
