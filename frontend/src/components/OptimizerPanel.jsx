import { useState } from 'react'
import { api } from '../api'

function PriceBadge({ label, value, source, error }) {
  const live = value !== null && value !== undefined
  return (
    <div className={`price-badge ${live ? 'live' : 'offline'}`}>
      <span className="price-badge-dot" />
      <div>
        <div className="price-badge-label">{label}</div>
        <div className="price-badge-value">{live ? value : 'not configured'}</div>
        {live ? (
          <div className="price-badge-source">{source}</div>
        ) : (
          <div className="price-badge-source">{error}</div>
        )}
      </div>
    </div>
  )
}

export default function OptimizerPanel() {
  const [budget, setBudget] = useState(100)
  const [fuelPriceInput, setFuelPriceInput] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function handleRun() {
    setLoading(true)
    setError(null)
    const manualFuelPrice = fuelPriceInput.trim() === '' ? undefined : Number(fuelPriceInput)
    api
      .optimizeBudget(budget, manualFuelPrice)
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  const alloc = result?.recommended_allocation
  const pricing = result?.pricing

  return (
    <div className="card">
      <h2>Budget allocation (RL, stretch component)</h2>
      <p style={{ fontSize: 13, marginBottom: 12 }}>
        Trains a fresh PPO policy against the live NO₂/NDVI baseline to split a fixed budget
        between traffic reduction and afforestation, priced against fuel and carbon markets.
        Amounts are in ₹ but on an illustrative scale, not a real-world program budget — see
        the note below the results.
      </p>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div className="field" style={{ maxWidth: 200 }}>
          <label>
            <span>Budget (₹, illustrative)</span>
          </label>
          <input
            type="number"
            min={1}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
          />
        </div>
        <div className="field" style={{ maxWidth: 220 }}>
          <label>
            <span>Petrol price (₹/L, optional)</span>
          </label>
          <input
            type="number"
            min={0}
            step="0.01"
            placeholder="e.g. 104.75"
            value={fuelPriceInput}
            onChange={(e) => setFuelPriceInput(e.target.value)}
          />
        </div>
      </div>
      <p className="empty-hint" style={{ marginTop: -8, marginBottom: 16 }}>
        Enter today's local petrol price to price traffic-reduction spend accurately. Leave
        blank to use a live price feed if configured, or an illustrative default otherwise.
      </p>
      <button className="run-btn" onClick={handleRun} disabled={loading}>
        {loading ? 'Training policy… (10-20s)' : 'Optimize allocation'}
      </button>

      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}

      {pricing && (
        <div className="price-badge-row">
          <PriceBadge
            label="Petrol price"
            value={pricing.fuel_price_inr_per_litre && `₹${pricing.fuel_price_inr_per_litre.toFixed(2)}/L`}
            source={pricing.fuel_price_source}
            error={pricing.fuel_price_error}
          />
          <PriceBadge
            label="Carbon credit price"
            value={pricing.carbon_price_usd_per_ton && `$${pricing.carbon_price_usd_per_ton.toFixed(2)}/ton`}
            source={pricing.carbon_price_source}
            error={pricing.carbon_price_error}
          />
        </div>
      )}

      {alloc && (
        <>
          {alloc.traffic_reduction_pct < 0.1 && alloc.afforestation_area_pct < 0.1 && (
            <div className="info-banner">
              <strong>No spend recommended.</strong> Vellore's current NO₂ and vegetation
              levels are already at or better than their own recent baseline (risk score{' '}
              {result.projected_risk_score.toFixed(3)}, effectively zero) — there's no
              elevated risk for this budget to reduce, so spending anything would only add
              cost with no benefit. This isn't a stuck calculation; re-run it during a
              period of worse air quality or vegetation loss to see a real allocation.
            </div>
          )}
          <div className="grid" style={{ marginTop: 16, marginBottom: 0 }}>
            <div>
              <div className="label" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Traffic reduction
              </div>
              <div className="value" style={{ fontSize: 20, fontWeight: 600 }}>
                ₹{alloc.traffic_reduction_budget.toFixed(1)}
              </div>
              <div className="caption">≈ {alloc.traffic_reduction_pct.toFixed(1)}% reduction</div>
            </div>
            <div>
              <div className="label" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Afforestation
              </div>
              <div className="value" style={{ fontSize: 20, fontWeight: 600 }}>
                ₹{alloc.afforestation_budget.toFixed(1)}
              </div>
              <div className="caption">≈ {alloc.afforestation_area_pct.toFixed(1)}% of buffer area</div>
            </div>
            {result.estimated_carbon_value_usd !== null && result.estimated_carbon_value_usd !== undefined && (
              <div>
                <div className="label" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  Est. carbon value
                </div>
                <div className="value" style={{ fontSize: 20, fontWeight: 600 }}>
                  ${result.estimated_carbon_value_usd.toFixed(0)}
                </div>
                <div className="caption">at current market carbon price</div>
              </div>
            )}
          </div>
          <div className="assumption-note">{result.assumptions.note}</div>
        </>
      )}
    </div>
  )
}
