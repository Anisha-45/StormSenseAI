import { Link } from 'react-router-dom'
import { useGet } from '../lib/useApi.js'
import { Async, Card, Note, Stat } from '../components/ui.jsx'
import { BarBlock } from '../components/charts.jsx'
import { Icon } from '../components/icons.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { num, pct, usd } from '../lib/format.js'

const QUICK = [
  { to: '/quality', label: 'Check data quality', icon: 'shield' },
  { to: '/clustering', label: 'Run clustering', icon: 'cluster' },
  { to: '/clusters', label: 'Read cluster profiles', icon: 'flask' },
  { to: '/geography', label: 'Open the map', icon: 'map' },
  { to: '/anomalies', label: 'Find anomalies', icon: 'alert' },
  { to: '/similar', label: 'Find similar events', icon: 'search' },
  { to: '/reports', label: 'Build a report', icon: 'file' },
]

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export default function Overview() {
  const ov = useGet('/overview')
  const { user } = useAuth()
  const first = user?.name?.split(/\s+/)[0]
  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-ink-950 via-ink-800 to-storm-700 p-7 text-white shadow-lift sm:p-9 animate-rise">
        <div className="pointer-events-none absolute -right-10 -top-16 h-64 w-64 rounded-full bg-volt-500/25 blur-3xl" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-20 left-1/3 h-64 w-96 rounded-full bg-aqua-500/20 blur-3xl" aria-hidden="true" />
        <div className="relative max-w-3xl">
          <p className="text-sm font-semibold text-volt-400">{greeting()}{first ? `, ${first}` : ''}</p>
          <h1 className="mt-1 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">Storm intelligence dashboard</h1>
          <p className="mt-3 text-sm text-slate-300 sm:text-base">
            Every figure here is computed from the processed NOAA Storm Events data and the experiments you have run. Nothing is hard-coded.
          </p>
        </div>
        <div className="relative mt-6 flex flex-wrap gap-2.5">
          {QUICK.map((q) => (
            <Link key={q.to} to={q.to} className="chip"><Icon name={q.icon} className="h-4 w-4" />{q.label}</Link>
          ))}
        </div>
      </section>

      <Async state={ov}>
        {(d) => {
          const types = Object.entries(d.top_event_types).map(([name, events]) => ({ name, events }))
          const years = Object.entries(d.year_counts || {}).map(([year, events]) => ({ year, events }))
          const le = d.latest_experiment
          return (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Stat icon="database" tone="blue" label="Unique events" value={num(d.total_unique_events)} hint={`${d.date_range?.[0]?.slice(0, 10)} to ${d.date_range?.[1]?.slice(0, 10)}`} />
                <Stat icon="layers" tone="violet" label="Event types" value={num(d.event_types)} hint={`${num(d.states_or_regions)} states / regions`} />
                <Stat icon="calendar" tone="teal" label="Years present" value={d.years.join(', ')} hint="See coverage note below" />
                <Stat icon="pin" tone="amber" label="Mappable events" value={num(d.events_with_coordinates)} hint={pct((d.events_with_coordinates / d.total_unique_events) * 100) + ' have coordinates'} />
                <Stat icon="skull" tone="red" label="Recorded deaths" value={num(d.totals.deaths)} />
                <Stat icon="heart" tone="red" label="Recorded injuries" value={num(d.totals.injuries)} />
                <Stat icon="dollar" tone="amber" label="Property damage" value={usd(d.totals.property_damage_usd)} hint="Estimates; many missing" />
                <Stat icon="flask" tone="blue" label="Experiments run" value={num(d.completed_experiments)}
                  hint={le ? `Latest: #${le.id} ${le.algorithm}, ${le.n_clusters} clusters, ${pct(le.noise_pct)} noise` : 'None yet. Open the Clustering Lab'} />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card title="Most common event types" subtitle="Number of recorded events"><BarBlock data={types} x="name" bars="events" layout="vertical" height={300} /></Card>
                <Card title="Events by year" subtitle="2020 dominates this extract; earlier years are partial"><BarBlock data={years} x="year" bars="events" height={300} /></Card>
              </div>

              <Note tone="warn" title="Read the coverage note.">{d.caveats.join(' ')}</Note>

              <div className="grid gap-4 md:grid-cols-3">
                {[
                  { n: 1, to: '/quality', t: 'Check data quality', x: 'See completeness, duplicates and what was left out.' },
                  { n: 2, to: '/clustering', t: 'Run hierarchical and DBSCAN', x: 'Compare methods with internal metrics and stability.' },
                  { n: 3, to: '/clusters', t: 'Read the explanations', x: 'Plain-language profiles of what each cluster contains.' },
                ].map((s) => (
                  <Link key={s.n} to={s.to} className="card card-hover group flex items-start gap-4">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-volt-400 to-volt-600 font-display text-lg font-extrabold text-ink-950">{s.n}</span>
                    <span>
                      <span className="flex items-center gap-1 font-display font-semibold text-ink-900">{s.t}<Icon name="arrow" className="h-4 w-4 transition group-hover:translate-x-1" /></span>
                      <span className="mt-1 block text-sm text-slate-500">{s.x}</span>
                    </span>
                  </Link>
                ))}
              </div>
            </>
          )
        }}
      </Async>
    </div>
  )
}
