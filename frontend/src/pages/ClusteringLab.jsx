import { useEffect, useState } from 'react'
import { useAction, useGet } from '../lib/useApi.js'
import { Async, Badge, Caveat, Card, DataTable, ErrorBox, Field, Gate, Note, PageHeader, Select, Spinner, Stat, Tabs } from '../components/ui.jsx'
import { BarBlock, ClusterScatter, Dendrogram, LineBlock } from '../components/charts.jsx'
import { num, pct } from '../lib/format.js'

function ResultView({ result }) {
  const m = result.metrics
  const pts = useGet(`/clustering/${result.experiment_id}/assignments`, { limit: 30000 })
  const sizes = Object.entries(m.cluster_sizes).map(([id, n]) => ({ cluster: `C${id}`, events: n }))
  const sil = Object.entries(m.silhouette_by_cluster || {}).map(([id, s]) => ({ cluster: `C${id}`, silhouette: s }))
  const imp = (m.feature_importance || []).slice(0, 8).map((f) => ({ feature: f.feature, share: Math.round(f.eta_squared * 1000) / 10 }))
  const largest = Math.max(0, ...Object.values(m.cluster_sizes)) / m.n_rows
  const variance = m.pca_explained_variance || []
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Clusters" value={m.n_clusters} />
        <Stat label="Noise" value={`${num(m.noise_count)} (${pct(m.noise_pct)})`} />
        <Stat label="Silhouette" value={m.silhouette ?? 'n/a'} hint="-1 to 1, higher is more compact" />
        <Stat label="Davies-Bouldin" value={m.davies_bouldin ?? 'n/a'} hint="lower is better" />
        <Stat label="Calinski-Harabasz" value={m.calinski_harabasz ?? 'n/a'} hint="higher is better" />
        <Stat label="Run time" value={`${result.seconds}s`} hint={`peak ${result.peak_mb} MB`} />
      </div>
      {result.algorithm === 'dbscan' && <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Core points" value={num(m.core_count)} /><Stat label="Border points" value={num(m.border_count)} /><Stat label="eps used" value={Number(result.params.eps).toFixed(3)} /><Stat label="min_samples" value={result.params.min_samples} /></div>}
      {largest > 0.9 && <Note tone="warn" title="Degenerate result.">{pct(largest * 100, 0)} of events fell into a single cluster. Metric scores for such a result can look good while telling you very little; try other parameters.</Note>}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="PCA projection" subtitle={`PC1 ${pct((variance[0] || 0) * 100)} + PC2 ${pct((variance[1] || 0) * 100)} of variance (2-D view of a higher-dimensional space)`}>
          <Async state={pts}>{(rows) => <ClusterScatter points={rows.map((r) => ({ x: r.pc1, y: r.pc2, cluster: r.cluster }))} />}</Async>
        </Card>
        <div className="space-y-5">
          <Card title="Cluster sizes"><BarBlock data={sizes} x="cluster" bars="events" height={170} colorByIndex /></Card>
          {sil.length > 0 && <Card title="Silhouette by cluster" subtitle="Noise excluded"><BarBlock data={sil} x="cluster" bars="silhouette" height={170} /></Card>}
        </div>
      </div>
      {imp.length > 0 && <Card title="Which impact features separate the clusters?" subtitle="Share of variance explained by cluster membership (eta squared, %). Descriptive, not causal."><BarBlock data={imp} x="feature" bars="share" layout="vertical" height={240} /></Card>}
      {m.stability && (
        <Card title="Stability under resampling" subtitle={`${m.stability.runs} runs on ${pct(m.stability.fraction * 100, 0)} subsamples, Adjusted Rand Index vs the full run`}>
          <div className="flex flex-wrap items-center gap-4"><Stat label="Mean ARI" value={m.stability.ari_mean} hint={`± ${m.stability.ari_std}`} /><p className="max-w-xl text-sm text-slate-600">{m.stability.interpretation}</p></div>
        </Card>
      )}
      <Card title="Configuration saved with this experiment" subtitle={`Experiment #${result.experiment_id}: reproducible from these settings`}>
        <pre className="overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify({ algorithm: result.algorithm, params: result.params, ...result.config }, null, 2)}</pre>
      </Card>
      <ul className="list-disc space-y-1 pl-5 text-xs text-slate-500">{m.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  )
}

export default function ClusteringLab() {
  const meta = useGet('/clustering/features')
  const exps = useGet('/clustering/experiments')
  const types = useGet('/geography/filters')
  const act = useAction()
  const tool = useAction()

  const [algo, setAlgo] = useState('hierarchical')
  const [features, setFeatures] = useState(null)
  const [fc, setFc] = useState({ sample_size: 5000, scaler: 'standard', impute: 'median', event_types: [] })
  const [h, setH] = useState({ n_clusters: 6, linkage: 'ward', metric: 'euclidean' })
  const [d, setD] = useState({ eps: '', min_samples: 10, metric: 'euclidean' })
  const [hd, setHd] = useState({ min_cluster_size: 20 })
  const [stab, setStab] = useState(false)
  const [seed, setSeed] = useState(42)
  const [result, setResult] = useState(null)
  const [toolTab, setToolTab] = useState('linkage')
  const [toolOut, setToolOut] = useState(null)
  const [sens, setSens] = useState({ eps: '0.5,1,1.5,2,3', ms: '5,10,20' })
  const [cmp, setCmp] = useState([])
  const [cmpOut, setCmpOut] = useState(null)

  useEffect(() => { if (meta.data && !features) setFeatures(meta.data.default) }, [meta.data, features])

  const featureConfig = () => ({ features, sample_size: Number(fc.sample_size), scaler: fc.scaler, impute: fc.impute, event_types: fc.event_types.length ? fc.event_types : null })
  const toggle = (k) => setFeatures((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]))
  const invalid = !features || features.length === 0

  async function run() {
    let url, body
    if (algo === 'hierarchical') { url = '/clustering/hierarchical'; body = { ...h, seed: Number(seed), with_stability: stab, feature_config: featureConfig() } }
    else if (algo === 'dbscan') { url = '/clustering/dbscan'; body = { min_samples: Number(d.min_samples), metric: d.metric, seed: Number(seed), with_stability: stab, feature_config: featureConfig(), ...(d.eps !== '' ? { eps: Number(d.eps) } : {}) } }
    else { url = '/clustering/hdbscan'; body = { min_cluster_size: Number(hd.min_cluster_size), seed: Number(seed), with_stability: stab, feature_config: featureConfig() } }
    const r = await act.run((api) => api.post(url, body))
    if (r) { setResult(r.data); exps.reload() }
  }

  async function runTool() {
    setToolOut(null)
    const small = { ...featureConfig(), sample_size: Math.min(3000, Number(fc.sample_size)) }
    let r
    if (toolTab === 'linkage') r = await tool.run((api) => api.post(`/clustering/linkage-comparison?n_clusters=${h.n_clusters}`, small))
    if (toolTab === 'dendrogram') r = await tool.run((api) => api.post(`/clustering/dendrogram?linkage=${h.linkage}`, small))
    if (toolTab === 'kdist') r = await tool.run((api) => api.post(`/clustering/dbscan/k-distance?k=${d.min_samples}`, small))
    if (toolTab === 'sens') r = await tool.run((api) => api.post('/clustering/dbscan/sensitivity', {
      eps_values: sens.eps.split(',').map(Number).filter((x) => x > 0), min_samples_values: sens.ms.split(',').map(Number).filter((x) => x > 0), metric: d.metric, feature_config: small }))
    if (r) setToolOut({ tab: toolTab, data: r.data })
  }

  async function compare() {
    setCmpOut(null)
    const r = await tool.run((api) => api.get('/clustering/compare', { params: { ids: cmp.join(',') } }))
    if (r) setCmpOut(r.data)
  }

  return (
    <>
      <PageHeader title="Clustering Lab" subtitle="Hierarchical agglomerative clustering and DBSCAN (HDBSCAN optional) on a representative sample of NOAA events. Every run is saved so it can be reproduced and compared." />
      <Gate perm="run_experiments" what="the Clustering Lab">
        <div className="space-y-5">
          <Card title="1. Choose features and preprocessing" subtitle="Missing values are imputed, numerical features scaled, categorical features one-hot encoded.">
            <Async state={meta}>
              {(m) => (
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <div className="label">Numerical features</div>
                      <div className="space-y-1">{Object.entries(m.numeric).map(([k, v]) => <label key={k} className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={features?.includes(k) || false} onChange={() => toggle(k)} /><span><code>{k}</code> <span className="text-slate-500">{v}</span></span></label>)}</div>
                    </div>
                    <div>
                      <div className="label">Categorical features</div>
                      <div className="space-y-1">{Object.entries(m.categorical).map(([k, v]) => <label key={k} className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={features?.includes(k) || false} onChange={() => toggle(k)} /><span><code>{k}</code> <span className="text-slate-500">{v}</span></span></label>)}</div>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-4">
                    <Field label="Sample size" hint={`Stratified, not first-N. Hierarchical max ${num(m.max_hierarchical_rows)}.`}><input className="input" type="number" min="200" max="30000" step="500" value={fc.sample_size} onChange={(e) => setFc({ ...fc, sample_size: e.target.value })} /></Field>
                    <Field label="Scaler"><Select value={fc.scaler} onChange={(v) => setFc({ ...fc, scaler: v })} options={['standard', 'robust', 'minmax']} /></Field>
                    <Field label="Missing values"><Select value={fc.impute} onChange={(v) => setFc({ ...fc, impute: v })} options={[{ value: 'median', label: 'Median' }, { value: 'zero', label: 'Zero' }]} /></Field>
                    <Field label="Random seed"><input className="input" type="number" value={seed} onChange={(e) => setSeed(e.target.value)} /></Field>
                  </div>
                  <Field label="Restrict to event types (optional)" hint="Hold Ctrl/Cmd to select several. Leave empty for all.">
                    <select multiple className="input h-24" value={fc.event_types} onChange={(e) => setFc({ ...fc, event_types: [...e.target.selectedOptions].map((o) => o.value) })}>
                      {(types.data?.event_types || []).map((t) => <option key={t}>{t}</option>)}
                    </select>
                  </Field>
                  {features?.some((f) => f === 'lat' || f === 'lon') && <Note>Latitude/longitude selected: events without coordinates (about 23%) are excluded from the run, and the exact count is reported in the saved configuration.</Note>}
                </div>
              )}
            </Async>
          </Card>

          <Card title="2. Choose an algorithm">
            <Tabs value={algo} onChange={setAlgo} tabs={[{ value: 'hierarchical', label: 'Hierarchical (agglomerative)' }, { value: 'dbscan', label: 'DBSCAN' }, { value: 'hdbscan', label: 'HDBSCAN (optional)' }]} />
            {algo === 'hierarchical' && (
              <div className="grid gap-3 md:grid-cols-3">
                <Field label="Number of clusters"><input className="input" type="number" min="2" max="50" value={h.n_clusters} onChange={(e) => setH({ ...h, n_clusters: Number(e.target.value) })} /></Field>
                <Field label="Linkage" hint="Ward needs Euclidean distance."><Select value={h.linkage} onChange={(v) => setH({ ...h, linkage: v })} options={meta.data?.linkages || ['ward']} /></Field>
                <Field label="Distance metric"><Select value={h.linkage === 'ward' ? 'euclidean' : h.metric} disabled={h.linkage === 'ward'} onChange={(v) => setH({ ...h, metric: v })} options={meta.data?.metrics || ['euclidean']} /></Field>
              </div>
            )}
            {algo === 'dbscan' && (
              <div className="grid gap-3 md:grid-cols-3">
                <Field label="eps (neighbourhood radius)" hint="Leave blank to use the k-distance knee suggestion."><input className="input" type="number" step="0.05" min="0.01" placeholder="auto" value={d.eps} onChange={(e) => setD({ ...d, eps: e.target.value })} /></Field>
                <Field label="min_samples"><input className="input" type="number" min="1" max="500" value={d.min_samples} onChange={(e) => setD({ ...d, min_samples: e.target.value })} /></Field>
                <Field label="Distance metric"><Select value={d.metric} onChange={(v) => setD({ ...d, metric: v })} options={meta.data?.metrics || ['euclidean']} /></Field>
              </div>
            )}
            {algo === 'hdbscan' && <Field label="Minimum cluster size"><input className="input max-w-xs" type="number" min="2" value={hd.min_cluster_size} onChange={(e) => setHd({ min_cluster_size: e.target.value })} /></Field>}
            <div className="mt-4 flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={stab} onChange={(e) => setStab(e.target.checked)} /> Also measure stability (4 extra runs, slower)</label>
              <button className="btn" disabled={act.busy || invalid} onClick={run}>{act.busy ? 'Running...' : `Run ${algo}`}</button>
              {invalid && <span className="text-sm text-red-700">Select at least one feature.</span>}
            </div>
            <div className="mt-3"><ErrorBox message={act.error} /></div>
          </Card>

          {act.busy && <Spinner label="Clustering (a few seconds up to a minute for large samples)" />}
          {result && !act.busy && <ResultView result={result} />}

          <Card title="3. Diagnostics" subtitle="Run on a sample of up to 3,000 events using the features chosen above.">
            <Tabs value={toolTab} onChange={(t) => { setToolTab(t); setToolOut(null) }} tabs={[{ value: 'linkage', label: 'Linkage comparison' }, { value: 'dendrogram', label: 'Dendrogram' }, { value: 'kdist', label: 'DBSCAN k-distance' }, { value: 'sens', label: 'DBSCAN sensitivity' }]} />
            {toolTab === 'sens' && (
              <div className="mb-3 grid gap-3 md:grid-cols-2">
                <Field label="eps values (comma separated)"><input className="input" value={sens.eps} onChange={(e) => setSens({ ...sens, eps: e.target.value })} /></Field>
                <Field label="min_samples values"><input className="input" value={sens.ms} onChange={(e) => setSens({ ...sens, ms: e.target.value })} /></Field>
              </div>
            )}
            <button className="btn" disabled={tool.busy || invalid} onClick={runTool}>{tool.busy ? 'Working...' : 'Run diagnostic'}</button>
            <div className="mt-3"><ErrorBox message={tool.error} /></div>
            {toolOut?.tab === 'linkage' && (
              <div className="mt-4">
                <DataTable columns={[{ key: 'linkage', label: 'Linkage' }, { key: 'n_clusters', label: 'Clusters' }, { key: 'silhouette', label: 'Silhouette' }, { key: 'davies_bouldin', label: 'Davies-Bouldin' }, { key: 'calinski_harabasz', label: 'Calinski-Harabasz' },
                  { key: 'largest_cluster_share_pct', label: 'Largest cluster %', render: (r) => (r.largest_cluster_share_pct > 90 ? <Badge tone="red">{r.largest_cluster_share_pct}%</Badge> : `${r.largest_cluster_share_pct}%`) }, { key: 'seconds', label: 'Seconds' }]} rows={toolOut.data.rows.map((r) => ({ ...r, id: r.linkage }))} />
                <Caveat>{toolOut.data.caveat}</Caveat>
              </div>
            )}
            {toolOut?.tab === 'dendrogram' && <div className="mt-4"><Dendrogram icoord={toolOut.data.icoord} dcoord={toolOut.data.dcoord} /><Caveat>Drawn from a random subsample of {toolOut.data.sample_rows} events with the last 30 merges shown ({toolOut.data.linkage} linkage). A large jump in merge distance suggests a natural cut level.</Caveat></div>}
            {toolOut?.tab === 'kdist' && (
              <div className="mt-4">
                <LineBlock data={toolOut.data.k_distances.map((v, i) => ({ i, distance: v }))} x="i" lines="distance" />
                <p className="text-sm">Suggested eps (knee of the curve): <b>{toolOut.data.suggested_eps.toFixed(3)}</b> for k = {toolOut.data.k}. The knee is a starting point, not a guarantee.</p>
              </div>
            )}
            {toolOut?.tab === 'sens' && (
              <div className="mt-4 space-y-3">
                <DataTable columns={[{ key: 'eps', label: 'eps' }, { key: 'min_samples', label: 'min_samples' }, { key: 'n_clusters', label: 'Clusters' }, { key: 'noise_pct', label: 'Noise %' }, { key: 'largest_cluster', label: 'Largest cluster', render: (r) => num(r.largest_cluster) }, { key: 'silhouette', label: 'Silhouette' }]} rows={toolOut.data.grid.map((r, i) => ({ ...r, id: i }))} />
                <Caveat>Look for a region where the cluster count and noise percentage stay stable as parameters change. Settings where one cluster absorbs nearly everything are not useful, whatever their Silhouette.</Caveat>
              </div>
            )}
          </Card>

          <Card title="Experiment history and comparison" subtitle="Select two or more experiments to compare them side by side.">
            <Async state={exps} empty={(e) => e.length === 0}>
              {(rows) => (
                <>
                  <DataTable columns={[
                    { key: 'sel', label: '', render: (r) => <input type="checkbox" aria-label={`Select experiment ${r.id}`} checked={cmp.includes(r.id)} onChange={() => setCmp((c) => (c.includes(r.id) ? c.filter((x) => x !== r.id) : [...c, r.id]))} /> },
                    { key: 'id', label: '#' }, { key: 'algorithm', label: 'Algorithm' }, { key: 'params', label: 'Parameters', render: (r) => Object.entries(r.params).map(([k, v]) => `${k}=${typeof v === 'number' ? +v.toFixed(3) : v}`).join(', ') },
                    { key: 'n_clusters', label: 'Clusters' }, { key: 'noise_pct', label: 'Noise %' }, { key: 'silhouette', label: 'Silhouette' }, { key: 'stability_ari', label: 'Stability ARI' }, { key: 'seconds', label: 'Seconds' }, { key: 'created_at', label: 'Created', render: (r) => r.created_at.slice(0, 16).replace('T', ' ') }]} rows={rows} />
                  <button className="btn mt-3" disabled={cmp.length < 2 || tool.busy} onClick={compare}>Compare selected ({cmp.length})</button>
                </>
              )}
            </Async>
            {cmpOut && (
              <div className="mt-4 space-y-3">
                <DataTable columns={[{ key: 'id', label: '#' }, { key: 'algorithm', label: 'Algorithm' }, { key: 'sample_size', label: 'Sample', render: (r) => num(r.sample_size) }, { key: 'n_clusters', label: 'Clusters' }, { key: 'noise_pct', label: 'Noise %' }, { key: 'largest_cluster_share_pct', label: 'Largest cluster %' }, { key: 'silhouette', label: 'Silhouette' }, { key: 'davies_bouldin', label: 'DB' }, { key: 'calinski_harabasz', label: 'CH' }, { key: 'stability_ari', label: 'ARI' }, { key: 'seconds', label: 'Seconds' }]} rows={cmpOut.experiments} />
                {cmpOut.caveats.map((c) => <Caveat key={c}>{c}</Caveat>)}
              </div>
            )}
          </Card>
        </div>
      </Gate>
    </>
  )
}
