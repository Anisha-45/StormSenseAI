import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { PALETTE, clusterColor, num } from '../lib/format.js'
import { Empty } from './ui.jsx'

const axis = { fontSize: 11, fill: '#64748b' }

export function BarBlock({ data, x, bars, height = 260, stacked = false, layout = 'horizontal', colorByIndex = false, yFormatter = num }) {
  if (!data || data.length === 0) return <Empty />
  const list = typeof bars === 'string' ? [{ key: bars, name: bars }] : bars
  const vertical = layout === 'vertical'
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={layout} margin={{ top: 4, right: 12, left: vertical ? 40 : 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        {vertical ? <XAxis type="number" tick={axis} tickFormatter={yFormatter} /> : <XAxis dataKey={x} tick={axis} interval={0} angle={data.length > 8 ? -35 : 0} textAnchor={data.length > 8 ? 'end' : 'middle'} height={data.length > 8 ? 70 : 30} />}
        {vertical ? <YAxis type="category" dataKey={x} tick={axis} width={110} /> : <YAxis tick={axis} tickFormatter={yFormatter} />}
        <Tooltip formatter={(v) => yFormatter(v)} />
        {list.length > 1 && <Legend />}
        {list.map((b, i) => (
          <Bar key={b.key} dataKey={b.key} name={b.name || b.key} fill={PALETTE[i % PALETTE.length]} stackId={stacked ? 'a' : undefined} radius={[3, 3, 0, 0]}>
            {colorByIndex && list.length === 1 && data.map((_, j) => <Cell key={j} fill={PALETTE[j % PALETTE.length]} />)}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

export function LineBlock({ data, x, lines, height = 260, yFormatter = num }) {
  if (!data || data.length === 0) return <Empty />
  const list = typeof lines === 'string' ? [{ key: lines, name: lines }] : lines
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey={x} tick={axis} />
        <YAxis tick={axis} tickFormatter={yFormatter} />
        <Tooltip formatter={(v) => yFormatter(v)} />
        {list.length > 1 && <Legend />}
        {list.map((l, i) => <Line key={l.key} type="monotone" dataKey={l.key} name={l.name || l.key} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={{ r: 2 }} />)}
      </LineChart>
    </ResponsiveContainer>
  )
}

/** PCA scatter coloured by cluster. points: [{x, y, cluster}] */
export function ClusterScatter({ points, height = 380, xLabel = 'PC1', yLabel = 'PC2' }) {
  if (!points || points.length === 0) return <Empty />
  const groups = {}
  points.forEach((p) => { (groups[p.cluster] ||= []).push(p) })
  const ids = Object.keys(groups).map(Number).sort((a, b) => a - b)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis type="number" dataKey="x" name={xLabel} tick={axis} label={{ value: xLabel, position: 'insideBottom', offset: -8, fontSize: 11 }} />
        <YAxis type="number" dataKey="y" name={yLabel} tick={axis} label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 11 }} />
        <ZAxis range={[18, 18]} />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
        <Legend />
        {ids.map((id) => <Scatter key={id} name={id === -1 ? 'Noise' : `Cluster ${id}`} data={groups[id]} fill={clusterColor(id)} fillOpacity={id === -1 ? 0.5 : 0.75} />)}
      </ScatterChart>
    </ResponsiveContainer>
  )
}

/** Dendrogram drawn from scipy's icoord/dcoord with plain SVG (no extra library). */
export function Dendrogram({ icoord, dcoord, height = 320 }) {
  if (!icoord || icoord.length === 0) return <Empty />
  const W = 800, H = height, pad = 30
  const xs = icoord.flat(), ys = dcoord.flat()
  const xMin = Math.min(...xs), xMax = Math.max(...xs), yMax = Math.max(...ys) || 1
  const sx = (v) => pad + ((v - xMin) / (xMax - xMin || 1)) * (W - 2 * pad)
  const sy = (v) => H - pad - (v / yMax) * (H - 2 * pad)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Dendrogram of hierarchical merges; vertical axis is merge distance">
      <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke="#cbd5e1" />
      <line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke="#cbd5e1" />
      {icoord.map((ic, i) => (
        <polyline key={i} fill="none" stroke="#2f7de1" strokeWidth="1.2" points={ic.map((x, j) => `${sx(x)},${sy(dcoord[i][j])}`).join(' ')} />
      ))}
      <text x={6} y={14} fontSize="10" fill="#64748b">merge distance</text>
      <text x={W / 2 - 60} y={H - 8} fontSize="10" fill="#64748b">events (truncated leaves)</text>
    </svg>
  )
}
