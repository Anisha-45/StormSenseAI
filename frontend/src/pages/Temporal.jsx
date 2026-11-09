import { useState } from 'react'
import { useGet } from '../lib/useApi.js'
import { Async, Card, DataTable, Field, Note, PageHeader, Select, Tabs } from '../components/ui.jsx'
import { BarBlock, LineBlock } from '../components/charts.jsx'
import { MONTHS, num, pct, usd } from '../lib/format.js'

export default function Temporal() {
  const opts = useGet('/geography/filters')
  const [tab, setTab] = useState('monthly')
  const [f, setF] = useState({ state: '', event_type: '', year: '' })
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }))
  const params = tab === 'yearly' ? { state: f.state, event_type: f.event_type } : f
  const series = useGet(`/temporal/${tab}`, params, { enabled: tab !== 'trends' })
  const trends = useGet('/temporal/trends', { state: f.state, event_type: f.event_type }, { enabled: tab === 'trends' })

  const label = (r) => (tab === 'monthly' ? MONTHS[r.month - 1] : tab === 'yearly' ? String(r.year) : r.season)
  const x = tab === 'monthly' ? 'month' : tab === 'yearly' ? 'year' : 'season'

  return (
    <>
      <PageHeader title="Temporal & Seasonal Analysis" subtitle="How recorded events are distributed across years, months and seasons. Differences in counts reflect what was recorded in this extract, not climate trends." />
      <Note tone="warn" title="Coverage:">The details file spans Feb 2017 – Sep 2020 and about 94% of events are from 2020. Earlier years are partial, so year-to-year comparisons mostly reflect extract coverage.</Note>
      <Card className="my-4">
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="State / region"><Select value={f.state} onChange={set('state')} options={opts.data?.states || []} placeholder="All" /></Field>
          <Field label="Event type"><Select value={f.event_type} onChange={set('event_type')} options={opts.data?.event_types || []} placeholder="All" /></Field>
          {(tab === 'monthly' || tab === 'seasonal') && <Field label="Year"><Select value={f.year} onChange={set('year')} options={opts.data?.years || []} placeholder="All" /></Field>}
        </div>
      </Card>
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'monthly', label: 'Month-wise' }, { value: 'seasonal', label: 'Seasonal' }, { value: 'yearly', label: 'Year-wise' }, { value: 'trends', label: 'Year-over-year' }]} />

      {tab !== 'trends' && (
        <Async state={series} empty={(d) => d.series.length === 0}>
          {(d) => {
            const rows = d.series.map((r) => ({ ...r, label: label(r) }))
            const byType = d.by_event_type.map((r) => ({ ...r, label: tab === 'monthly' ? MONTHS[r.month - 1] : String(r[x]) }))
            const typeKeys = byType.length ? Object.keys(byType[0]).filter((k) => !['month', 'year', 'season', 'label'].includes(k)) : []
            return (
              <div className="space-y-5">
                <div className="grid gap-5 lg:grid-cols-2">
                  <Card title="Events"><BarBlock data={rows} x="label" bars="events" height={260} /></Card>
                  <Card title="Events by top event types"><BarBlock data={byType} x="label" bars={typeKeys.map((k) => ({ key: k, name: k }))} stacked height={260} /></Card>
                  <Card title="Fatalities and injuries"><BarBlock data={rows} x="label" bars={[{ key: 'deaths', name: 'Deaths' }, { key: 'injuries', name: 'Injuries' }]} height={240} /></Card>
                  <Card title="Property and crop damage (USD)"><BarBlock data={rows} x="label" bars={[{ key: 'property_damage_usd', name: 'Property' }, { key: 'crop_damage_usd', name: 'Crops' }]} height={240} yFormatter={usd} /></Card>
                </div>
                <Card title="Mean event duration (hours)"><LineBlock data={rows} x="label" lines="mean_duration_hours" height={200} /></Card>
                {d.missing_months?.length > 0 && <Note>Months with no events in the data: {d.missing_months.join(', ')}. These are gaps in the extract, not necessarily quiet months.</Note>}
                <p className="text-xs italic text-slate-500">{d.caveat}</p>
              </div>
            )
          }}
        </Async>
      )}

      {tab === 'trends' && (
        <Async state={trends}>
          {(d) => (
            <div className="space-y-5">
              <Card title="Yearly totals"><DataTable columns={[{ key: 'year', label: 'Year' }, { key: 'events', label: 'Events', align: 'right', render: (r) => num(r.events) }, { key: 'deaths', label: 'Deaths', align: 'right' }, { key: 'injuries', label: 'Injuries', align: 'right' }, { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => usd(r.property_damage_usd) }, { key: 'months', label: 'Months recorded', align: 'right', render: (r) => d.months_covered[r.year] }]} rows={d.yearly.map((r) => ({ ...r, id: r.year }))} /></Card>
              <Card title="Year-over-year change (%)" subtitle="Computed only for comparison of recorded counts"><DataTable columns={[{ key: 'year', label: 'Year' }, { key: 'events', label: 'Events', align: 'right', render: (r) => pct(r.events) }, { key: 'deaths', label: 'Deaths', align: 'right', render: (r) => pct(r.deaths) }, { key: 'injuries', label: 'Injuries', align: 'right', render: (r) => pct(r.injuries) }, { key: 'property_damage_usd', label: 'Property', align: 'right', render: (r) => pct(r.property_damage_usd) }]} rows={d.yoy_pct_change.map((r) => ({ ...r, id: r.year }))} /></Card>
              <Note tone="warn" title="Do not read these as climate trends.">{d.caveat}</Note>
            </div>
          )}
        </Async>
      )}
    </>
  )
}
