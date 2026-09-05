import { useEffect, useState } from 'react'
import { api } from './api'
import { useAdmin } from './AdminContext'
import AqiPanel from './components/AqiPanel'
import VegetationPanel from './components/VegetationPanel'
import RainfallPanel from './components/RainfallPanel'
import FaunaPanel from './components/FaunaPanel'
import SimulationPanel from './components/SimulationPanel'
import DisasterSimulationPanel from './components/DisasterSimulationPanel'
import OptimizerPanel from './components/OptimizerPanel'
import KnowledgeGraphPanel from './components/KnowledgeGraphPanel'
import AdminPanel from './components/AdminPanel'
import AdminLogin from './components/AdminLogin'
import RiskScaleLegend from './components/RiskScaleLegend'
import ConditionsBar from './components/ConditionsBar'
import DashboardSummaryCard from './components/DashboardSummaryCard'
import TabBar from './components/TabBar'

const ENV_TABS = [
  { id: 'rainfall', label: 'Rainfall & flood' },
  { id: 'fauna', label: 'Wildlife' },
  { id: 'simulate', label: 'Simulate' },
]

function App() {
  const [city, setCity] = useState(null)
  const [envTab, setEnvTab] = useState('rainfall')
  const { verified } = useAdmin()

  useEffect(() => {
    api.health().then((h) => setCity(h.pilot_city)).catch(() => {})
  }, [])

  const navLinks = [
    { href: '#air-quality', label: 'Air quality' },
    { href: '#vegetation', label: 'Vegetation' },
    { href: '#environment', label: 'Rainfall, wildlife & simulate' },
    { href: '#optimize', label: 'Optimize' },
    { href: '#graph', label: 'Knowledge graph' },
    ...(verified ? [{ href: '#admin', label: 'Admin' }] : []),
  ]

  return (
    <>
      <nav className="top-nav">
        <span className="brand">
          <span className="dot" />
          Earth Digital Twin
        </span>
        {navLinks.map((link) => (
          <a key={link.href} href={link.href}>
            {link.label}
          </a>
        ))}
        <AdminLogin />
      </nav>

      <div style={{ marginTop: 20 }}>
        <ConditionsBar />
      </div>

      <header className="app-header">
        <div className="app-header-main">
          <span className="eyebrow">Live · {city || '…'}</span>
          <h1>Environmental &amp; public-health risk, in real time</h1>
          <p className="subtitle">
            Live satellite data on air quality, vegetation, rainfall, and wildlife — forecast,
            explained, and tested against real intervention and disaster scenarios.
          </p>
        </div>
        <RiskScaleLegend />
      </header>

      <div style={{ marginBottom: 16 }}>
        <DashboardSummaryCard />
      </div>

      <section className="block" id="air-quality">
        <div className="section-head">
          <h2>Air quality</h2>
          <span className="section-note">Sentinel-5P NO₂ proxy</span>
        </div>
        <AqiPanel />
      </section>

      <section className="block" id="vegetation">
        <div className="section-head">
          <h2>Vegetation</h2>
          <span className="section-note">Sentinel-2 NDVI</span>
        </div>
        <VegetationPanel />
      </section>

      <section className="block" id="environment">
        <div className="section-head">
          <h2>Rainfall, wildlife &amp; simulation</h2>
          <span className="section-note">Pick a tab — each loads only on demand</span>
        </div>
        <TabBar tabs={ENV_TABS} activeId={envTab} onChange={setEnvTab} />
        {envTab === 'rainfall' && <RainfallPanel />}
        {envTab === 'fauna' && <FaunaPanel />}
        {envTab === 'simulate' && (
          <>
            <SimulationPanel />
            <div style={{ marginTop: 16 }}>
              <DisasterSimulationPanel />
            </div>
          </>
        )}
      </section>

      <section className="block" id="optimize">
        <div className="section-head">
          <h2>Budget optimization</h2>
          <span className="section-note">PPO reinforcement learning</span>
        </div>
        <OptimizerPanel />
      </section>

      <section className="block" id="graph">
        <div className="section-head">
          <h2>Knowledge graph</h2>
          <span className="section-note">Environment → health links</span>
        </div>
        <KnowledgeGraphPanel />
      </section>

      {verified && (
        <section className="block" id="admin">
          <div className="section-head">
            <h2>Admin</h2>
            <span className="section-note">Manage history, graph edges &amp; settings</span>
          </div>
          <AdminPanel />
        </section>
      )}
    </>
  )
}

export default App
