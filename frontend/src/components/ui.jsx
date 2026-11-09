import { useState } from 'react'
import { Link } from 'react-router-dom'
import { can } from '../lib/format.js'
import { useAuth } from '../context/AuthContext.jsx'
import { Icon } from './icons.jsx'

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3 animate-rise">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink-900">{title}</h1>
        <div className="mt-2 h-1 w-12 rounded-full bg-gradient-to-r from-volt-500 to-volt-400" />
        {subtitle && <p className="mt-2 max-w-3xl text-sm text-slate-600">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}

export function Card({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="font-display text-base font-semibold text-ink-900">{title}</h2>}
            {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}

const STAT_TONES = {
  blue: 'from-storm-500 to-storm-700',
  amber: 'from-volt-400 to-volt-600',
  teal: 'from-aqua-400 to-aqua-500',
  red: 'from-rose-400 to-rose-600',
  violet: 'from-violet-400 to-violet-600',
}
export function Stat({ label, value, hint, icon, tone = 'blue' }) {
  return (
    <div className="card card-hover flex items-start gap-4">
      {icon && (
        <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br text-white shadow-md ${STAT_TONES[tone]}`}>
          <Icon name={icon} className="h-6 w-6" />
        </span>
      )}
      <div className="min-w-0">
        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</div>
        <div className="mt-1 font-display text-2xl font-bold tabular-nums text-ink-900">{value}</div>
        {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
      </div>
    </div>
  )
}

export function Spinner({ label = 'Loading' }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-storm-600" />
      {label}...
    </div>
  )
}

export function ErrorBox({ message, onRetry }) {
  if (!message) return null
  return (
    <div role="alert" className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <span>{message}</span>
      {onRetry && <button className="btn-secondary !py-1" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Empty({ children = 'No data to show.' }) {
  return <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">{children}</div>
}

/** Standard wrapper: shows spinner, error or children depending on a useGet() result. */
export function Async({ state, children, empty }) {
  if (state.loading) return <Spinner />
  if (state.error) return <ErrorBox message={state.error} onRetry={state.reload} />
  if (!state.data || (empty && empty(state.data))) return <Empty />
  return children(state.data)
}

const NOTE_STYLES = {
  info: 'border-storm-200 bg-storm-50 text-storm-700',
  warn: 'border-amber-300 bg-amber-50 text-amber-900',
  danger: 'border-red-300 bg-red-50 text-red-900',
}
export function Note({ tone = 'info', title, children }) {
  return (
    <div className={`rounded-2xl border p-4 text-sm shadow-sm ${NOTE_STYLES[tone]}`}>
      {title && <strong className="mr-1">{title}</strong>}
      {children}
    </div>
  )
}

export function Badge({ children, tone = 'slate' }) {
  const t = { slate: 'bg-slate-100 text-slate-700', green: 'bg-emerald-100 text-emerald-800', amber: 'bg-amber-100 text-amber-800', red: 'bg-red-100 text-red-800', blue: 'bg-blue-100 text-blue-800' }[tone]
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${t}`}>{children}</span>
}

export function Field({ label, children, hint }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

export function Select({ value, onChange, options, placeholder, ...rest }) {
  return (
    <select className="input" value={value ?? ''} onChange={(e) => onChange(e.target.value)} {...rest}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => {
        const v = typeof o === 'object' ? o.value : o
        const l = typeof o === 'object' ? o.label : o
        return <option key={v} value={v}>{l}</option>
      })}
    </select>
  )
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div role="tablist" className="mb-5 inline-flex max-w-full flex-wrap gap-1 rounded-2xl bg-white p-1 shadow-soft ring-1 ring-slate-900/5">
      {tabs.map((t) => {
        const v = typeof t === 'object' ? t.value : t
        const l = typeof t === 'object' ? t.label : t
        return (
          <button key={v} role="tab" aria-selected={value === v} onClick={() => onChange(v)}
            className={`rounded-xl px-3.5 py-2 text-sm font-semibold transition ${value === v ? 'bg-gradient-to-r from-storm-600 to-storm-500 text-white shadow' : 'text-slate-500 hover:bg-storm-50 hover:text-storm-700'}`}>
            {l}
          </button>
        )
      })}
    </div>
  )
}

/** Table with optional click-to-sort. columns: [{key, label, render?, align?}] */
export function DataTable({ columns, rows, onRowClick, empty = 'No rows.', maxHeight }) {
  const [sort, setSort] = useState({ key: null, dir: 1 })
  if (!rows || rows.length === 0) return <Empty>{empty}</Empty>
  const sorted = sort.key
    ? [...rows].sort((a, b) => {
        const x = a[sort.key], y = b[sort.key]
        if (x === y) return 0
        if (x === null || x === undefined) return 1
        if (y === null || y === undefined) return -1
        return (x > y ? 1 : -1) * sort.dir
      })
    : rows
  return (
    <div className="scroll-thin overflow-auto rounded-xl border border-slate-200" style={maxHeight ? { maxHeight } : undefined}>
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="sticky top-0">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={`th ${c.align === 'right' ? 'text-right' : ''}`} aria-sort={sort.key === c.key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
                <button className="font-semibold uppercase" onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? -s.dir : 1 }))}>
                  {c.label}{sort.key === c.key ? (sort.dir === 1 ? ' ▲' : ' ▼') : ''}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((r, i) => (
            <tr key={r.id ?? r.event_id ?? i} className={onRowClick ? 'cursor-pointer hover:bg-storm-50' : ''} onClick={onRowClick ? () => onRowClick(r) : undefined}>
              {columns.map((c) => (
                <td key={c.key} className={`td ${c.align === 'right' ? 'text-right tabular-nums' : ''}`}>{c.render ? c.render(r) : r[c.key] ?? '-'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Pager({ page, pageSize, total, onChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
      <span>{total.toLocaleString()} results · page {page} of {pages}</span>
      <div className="flex gap-2">
        <button className="btn-secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
        <button className="btn-secondary" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button>
      </div>
    </div>
  )
}

/** Shows children only if the user has the permission; otherwise explains how to get access. */
export function Gate({ perm, children, what = 'this feature' }) {
  const { user } = useAuth()
  if (can(user, perm)) return children
  return (
    <Note tone="warn" title="Access required.">
      {user
        ? <>Your role (<b>{user.role}</b>) cannot use {what}. Ask an administrator for the right role.</>
        : <>Please <Link className="underline" to="/login">sign in</Link> to use {what}. Researchers can register themselves; staff roles are granted by an administrator.</>}
    </Note>
  )
}

export function Caveat({ children }) {
  return <p className="mt-2 text-xs italic text-slate-500">{children}</p>
}
