import { useEffect, useState } from 'react'
import { api } from '../api/client'
import ConditionsBar from '../components/dashboard/ConditionsBar'
import DashboardSummaryCard from '../components/dashboard/DashboardSummaryCard'
import KnowledgeGraphPanel from '../components/panels/KnowledgeGraphPanel'
import RiskScaleLegend from '../components/ui/RiskScaleLegend'
import StatusPill from '../components/ui/StatusPill'
import Link from '../router/Link'
import usePageTitle from './usePageTitle'

const REGION_CARDS = [
  {
    id: 'kathmandu_flood',
    to: '/flood',
    kicker: 'Flood early warning',
    title: 'Kathmandu Valley',
    blurb: 'Bagmati, Bishnumati and Dhobi Khola discharge forecasts with surge warnings.',
    headline: (d) => {
      const r = d.rivers.reduce((a, b) => (b.peak_m3s / b.thresholds_m3s.p90 > a.peak_m3s / a.thresholds_m3s.p90 ? b : a))
      return `${r.river} peaks at ${r.peak_m3s.toFixed(1)} m³/s on ${new Date(r.peak_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}${d.surge_warning ? ' · surge flagged' : ''}`
    },
  },
  {
    id: 'mugling_landslide',
    to: '/landslide',
    kicker: 'Landslide risk',
    title: 'Mugling–Narayangadh corridor',
    blurb: 'Slope-failure probability and stability index for the Trishuli gorge highway.',
    headline: (d) =>
      `Highest risk ${new Date(d.peak.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}: ${(d.peak.failure_probability * 100).toFixed(1)}% failure probability`,
  },
]

function RegionCard({ card }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Narrative skipped: this card only needs the tier and one headline figure.
    api.predictNepal(card.id, false).then(setData).catch((err) => setError(err.message))
  }, [card.id])

  return (
    <Link to={card.to} className={`card region-card region-card-${card.id}`}>
      <div className="outcome-card-head">
        <span className="eyebrow" style={{ margin: 0 }}>
          {card.kicker}
        </span>
        {data && <StatusPill level={data.risk_tier} />}
      </div>
      <h2 style={{ margin: '8px 0 6px' }}>{card.title}</h2>
      <p className="scenario-desc" style={{ marginBottom: 12 }}>
        {card.blurb}
      </p>
      <div className="region-card-status">
        {error ? error : data ? card.headline(data) : <span className="loading"><span className="spinner" /> Checking the next 14 days…</span>}
      </div>
      <span className="region-card-cta">Open page →</span>
    </Link>
  )
}

export default function OverviewPage() {
  usePageTitle('')
  return (
    <div className="page">
      <div style={{ marginTop: 20 }}>
        <ConditionsBar />
      </div>

      <header className="app-header">
        <div className="app-header-main">
          <span className="eyebrow">Live · Nepal</span>
          <h1>Flood &amp; landslide early warning, in real time</h1>
          <p className="subtitle">
            A hydro-geological digital twin of the Kathmandu Valley and the Mugling–Narayangadh corridor — local
            machine-learning models trained on 15 years of weather, river discharge and reported disasters,
            forecasting the next two weeks.
          </p>
        </div>
        <RiskScaleLegend />
      </header>

      <div className="region-cards">
        {REGION_CARDS.map((c) => (
          <RegionCard key={c.id} card={c} />
        ))}
      </div>

      <div style={{ marginBottom: 16 }}>
        <DashboardSummaryCard />
      </div>

      <section className="block" id="graph">
        <div className="section-head">
          <h2>Knowledge graph</h2>
          <span className="section-note">Driver → hazard → outcome links</span>
        </div>
        <KnowledgeGraphPanel />
      </section>
    </div>
  )
}
