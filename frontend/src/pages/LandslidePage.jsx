import ConditionsBar from '../components/dashboard/ConditionsBar'
import MuglingLandslidePanel from '../components/panels/MuglingLandslidePanel'
import InteractiveSimulator from '../components/panels/InteractiveSimulator'
import CollinearityPanel from '../components/panels/CollinearityPanel'
import RiskScaleLegend from '../components/ui/RiskScaleLegend'
import usePageTitle from './usePageTitle'

export default function LandslidePage() {
  usePageTitle('Mugling Corridor Landslide Risk')
  return (
    <div className="page page-landslide">
      <div style={{ marginTop: 20 }}>
        <ConditionsBar regionIds={['mugling_landslide']} />
      </div>

      <header className="app-header">
        <div className="app-header-main">
          <span className="eyebrow">Mugling–Narayangadh highway · Landslide risk</span>
          <h1>Trishuli gorge corridor</h1>
          <p className="subtitle">
            Daily slope-failure probability from a model trained on 15 years of reported landslides, cross-checked
            with a physical slope stability index from deep soil wetness and terrain slope.
          </p>
        </div>
        <RiskScaleLegend hazard="landslide" />
      </header>

      <section className="block" id="forecast">
        <div className="section-head">
          <h2>Corridor outlook</h2>
          <span className="section-note">ECMWF weather · Copernicus DEM</span>
        </div>
        <MuglingLandslidePanel />
      </section>

      <section className="block" id="simulator">
        <div className="section-head">
          <h2>What if?</h2>
          <span className="section-note">Same model, hypothetical rain and soil</span>
        </div>
        <InteractiveSimulator focus="landslide" />
      </section>

      <section className="block" id="history">
        <div className="section-head">
          <h2>Past landslides</h2>
          <span className="section-note">Rain and soil triggers vs. reported landslides</span>
        </div>
        <CollinearityPanel region="mugling_landslide" />
      </section>
    </div>
  )
}
