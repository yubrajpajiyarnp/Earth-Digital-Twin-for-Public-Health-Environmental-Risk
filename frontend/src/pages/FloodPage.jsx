import ConditionsBar from '../components/dashboard/ConditionsBar'
import KathmanduFloodPanel from '../components/panels/KathmanduFloodPanel'
import InteractiveSimulator from '../components/panels/InteractiveSimulator'
import CollinearityPanel from '../components/panels/CollinearityPanel'
import RiskScaleLegend from '../components/ui/RiskScaleLegend'
import usePageTitle from './usePageTitle'

export default function FloodPage() {
  usePageTitle('Kathmandu Flood Early Warning')
  return (
    <div className="page page-flood">
      <div style={{ marginTop: 20 }}>
        <ConditionsBar regionIds={['kathmandu_flood']} />
      </div>

      <header className="app-header">
        <div className="app-header-main">
          <span className="eyebrow">Kathmandu Valley · Flood early warning</span>
          <h1>Bagmati, Bishnumati &amp; Dhobi Khola</h1>
          <p className="subtitle">
            14-day river discharge forecasts from locally trained models, compared against each river's own
            15-year record, with warnings when a surge breaks from the recent trend.
          </p>
        </div>
        <RiskScaleLegend hazard="flood" />
      </header>

      <section className="block" id="forecast">
        <div className="section-head">
          <h2>Multi-river forecast</h2>
          <span className="section-note">GloFAS discharge · ECMWF weather</span>
        </div>
        <KathmanduFloodPanel />
      </section>

      <section className="block" id="simulator">
        <div className="section-head">
          <h2>What if?</h2>
          <span className="section-note">Same models, hypothetical rain</span>
        </div>
        <InteractiveSimulator focus="flood" />
      </section>

      <section className="block" id="history">
        <div className="section-head">
          <h2>Past floods</h2>
          <span className="section-note">Rain triggers vs. discharge and reported floods</span>
        </div>
        <CollinearityPanel region="kathmandu_flood" />
      </section>
    </div>
  )
}
