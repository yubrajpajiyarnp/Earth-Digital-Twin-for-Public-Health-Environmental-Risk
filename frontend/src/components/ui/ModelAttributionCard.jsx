const METRIC_LABELS = {
  holdout_r2: { label: 'Holdout R²', fmt: (v) => v.toFixed(2) },
  holdout_mae_m3s: { label: 'Holdout MAE', fmt: (v) => `${v.toFixed(1)} m³/s` },
  holdout_roc_auc: { label: 'Holdout ROC-AUC', fmt: (v) => v.toFixed(2) },
  holdout_pr_auc: { label: 'Holdout PR-AUC', fmt: (v) => v.toFixed(2) },
  holdout_base_rate: { label: 'Base rate', fmt: (v) => `${(v * 100).toFixed(1)}%` },
  incidents: { label: 'Incidents learned from', fmt: (v) => v.toLocaleString() },
  train_days: { label: 'Training days', fmt: (v) => v.toLocaleString() },
}

// Which local model produced a number, how it was validated, and what drives it. Holdout
// metrics are from a time-based split (final 730 days held out); drivers are permutation
// importances on that holdout.
export default function ModelAttributionCard({ attribution }) {
  if (!attribution) return null
  const maxImp = Math.max(...attribution.top_drivers.map((d) => Math.abs(d.importance)), 1e-9)
  return (
    <div className="card attribution-card">
      <h3>Model attribution</h3>
      <p className="scenario-desc" style={{ marginBottom: 6 }}>
        <strong>{attribution.model}</strong> — {attribution.technique}. Trained locally{' '}
        {new Date(attribution.trained_at).toLocaleString()} on {attribution.training_period.start} →{' '}
        {attribution.training_period.end}.
      </p>
      <div className="metric-row">
        {Object.entries(METRIC_LABELS)
          .filter(([k]) => attribution.metrics[k] != null)
          .map(([k, m]) => (
            <div className="metric" key={k}>
              <span className="metric-label">{m.label}</span>
              <span className="metric-value" style={{ fontSize: 15 }}>
                {m.fmt(attribution.metrics[k])}
              </span>
            </div>
          ))}
      </div>
      <div className="caption" style={{ marginBottom: 8 }}>
        Top drivers (permutation importance on the holdout years)
      </div>
      {attribution.top_drivers.map((d) => (
        <div className="importance-row" key={d.feature}>
          <span style={{ color: 'var(--text-secondary)' }}>{d.label}</span>
          <span className="shap-track">
            <span
              className="shap-fill"
              style={{
                display: 'block',
                width: `${(Math.max(d.importance, 0) / maxImp) * 100}%`,
                background: 'var(--series-4)',
              }}
            />
          </span>
          <span className="value">{d.importance.toFixed(3)}</span>
        </div>
      ))}
    </div>
  )
}
