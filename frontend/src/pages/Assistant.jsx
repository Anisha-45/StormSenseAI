import { useEffect, useRef, useState } from 'react'
import { useAction, useGet } from '../lib/useApi.js'
import { Card, DataTable, ErrorBox, Field, Note, PageHeader, Select } from '../components/ui.jsx'
import { BarBlock } from '../components/charts.jsx'

const EXAMPLES = [
  'Which states have the highest number of flood events?',
  'Which event types have the highest fatalities?',
  'What seasonal pattern appears in tornado records?',
  'Show the yearly distribution of hail events',
  'Compare Texas and Oklahoma',
  'Which clusters have the highest property damage?',
  'Explain cluster 1',
]

function Answer({ m }) {
  const columns = m.table?.length ? Object.keys(m.table[0]).filter((k) => typeof m.table[0][k] !== 'object').slice(0, 8).map((k) => ({ key: k, label: k.replace(/_/g, ' ') })) : []
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-800">{m.answer}</p>
      {m.chart && <BarBlock data={m.chart.data} x={m.chart.x} bars={m.chart.y} height={240} layout={m.chart.data.length > 6 ? 'vertical' : 'horizontal'} />}
      {columns.length > 0 && <DataTable columns={columns} rows={m.table.map((r, i) => ({ ...r, id: i }))} maxHeight={240} />}
      <p className="text-xs italic text-slate-500">Source: {m.source}. {m.note}</p>
    </div>
  )
}

export default function Assistant() {
  const [q, setQ] = useState('')
  const [expId, setExpId] = useState('')
  const [log, setLog] = useState([])
  const exps = useGet('/clustering/experiments')
  const act = useAction()
  const end = useRef(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [log])

  async function ask(text) {
    const question = (text ?? q).trim()
    if (!question) return
    setQ('')
    const r = await act.run((api) => api.post('/assistant/query', { question, ...(expId ? { experiment_id: Number(expId) } : {}) }))
    setLog((l) => [...l, r ? { question, ...r.data } : { question, answer: null }])
  }

  return (
    <>
      <PageHeader title="AI Weather Assistant" subtitle="Ask about the historical records in plain English. Answers are computed from the data, never from memory, and always show their source." />
      <Note tone="warn" title="Historical only.">This assistant uses a fixed set of question patterns over the NOAA extract. It does not know about current weather and cannot issue or confirm alerts.</Note>
      <div className="mt-4 grid gap-5 lg:grid-cols-3">
        <div className="space-y-4">
          <Card title="Try asking">
            <ul className="space-y-1">{EXAMPLES.map((e) => <li key={e}><button className="text-left text-sm text-storm-700 hover:underline" onClick={() => ask(e)} disabled={act.busy}>{e}</button></li>)}</ul>
          </Card>
          <Card title="Cluster questions use"><Field label="Experiment" hint="Defaults to your latest."><Select value={expId} onChange={setExpId} placeholder="Latest experiment" options={(exps.data || []).map((e) => ({ value: e.id, label: `#${e.id} ${e.algorithm}` }))} /></Field></Card>
        </div>
        <div className="space-y-4 lg:col-span-2">
          <div className="space-y-4">
            {log.length === 0 && <p className="text-sm text-slate-500">No questions yet.</p>}
            {log.map((m, i) => (
              <Card key={i}>
                <p className="mb-2 text-sm font-semibold text-slate-900">You: {m.question}</p>
                {m.answer ? <Answer m={m} /> : <p className="text-sm text-red-700">Could not get an answer. See the error below.</p>}
              </Card>
            ))}
            <div ref={end} />
          </div>
          <ErrorBox message={act.error} />
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); ask() }}>
            <input className="input" maxLength={500} placeholder="Ask a question about the historical records..." value={q} onChange={(e) => setQ(e.target.value)} aria-label="Question" />
            <button className="btn" disabled={act.busy || !q.trim()}>{act.busy ? 'Thinking...' : 'Ask'}</button>
          </form>
        </div>
      </div>
    </>
  )
}
