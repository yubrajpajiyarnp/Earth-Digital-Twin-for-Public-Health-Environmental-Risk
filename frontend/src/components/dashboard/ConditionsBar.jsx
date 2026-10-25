import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import StatTile from '../ui/StatTile'

const TIME_ZONE = 'Asia/Kathmandu'
const REGIONS = [
  { id: 'kathmandu_flood', label: 'Kathmandu' },
  { id: 'mugling_landslide', label: 'Mugling' },
]
const MODEL_POLL_MS = 10_000

function formatLocalTime(date) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }).format(date)
}

function formatLocalDate(date) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: TIME_ZONE,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(date)
}

function WeatherTile({ region }) {
  const [weather, setWeather] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.weather(region.id).then(setWeather).catch((err) => setError(err.message))
  }, [region.id])

  if (error) {
    return <StatTile label={`${region.label} weather`} value="Unavailable" caption={error} accent="var(--status-warning)" />
  }
  if (!weather) {
    return (
      <div className="card stat-tile loading">
        <span className="spinner" />
        Loading {region.label} weather…
      </div>
    )
  }
  return (
    <StatTile
      label={`${region.label} · ${weather.weather_description}`}
      value={`${weather.temperature_c.toFixed(1)}°C`}
      caption={`Humidity ${weather.humidity_pct}% · rain ${weather.precipitation_mm ?? 0} mm · ${weather.pressure_hpa.toFixed(0)} hPa`}
      accent="var(--series-1)"
    />
  )
}

// Polls while the background trainer runs so the tile flips to "Ready" on its own.
function ModelTile() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    let timer
    const poll = () =>
      api
        .modelStatus()
        .then((s) => {
          setStatus(s)
          if (s.status === 'training' || !s.bundle_available) timer = setTimeout(poll, MODEL_POLL_MS)
        })
        .catch(() => (timer = setTimeout(poll, MODEL_POLL_MS)))
    poll()
    return () => clearTimeout(timer)
  }, [])

  if (!status) return <StatTile label="Local ML model" value="…" accent="var(--series-4)" />
  const value = status.bundle_available ? (status.status === 'training' ? 'Refreshing' : 'Ready') : status.status === 'failed' ? 'Failed' : 'Training…'
  return (
    <StatTile
      label="Local ML model"
      value={value}
      valueColor={status.status === 'failed' ? 'var(--status-critical)' : undefined}
      caption={
        status.bundle_available
          ? `Trained ${new Date(status.trained_at).toLocaleDateString('en-GB')} on ${status.training_period.start.slice(0, 4)}–${status.training_period.end.slice(0, 4)} data`
          : status.error || 'First run: training on 15 years of history (~1 min)'
      }
      accent="var(--series-4)"
    />
  )
}

// `regionIds` limits the weather tiles to the regions a page is about (default: both).
export default function ConditionsBar({ regionIds }) {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="grid conditions-bar">
      <StatTile
        label="Nepal time"
        value={formatLocalTime(now)}
        caption={`${formatLocalDate(now)} · NPT (UTC+5:45)`}
        accent="var(--series-1)"
      />
      {REGIONS.filter((r) => !regionIds || regionIds.includes(r.id)).map((r) => (
        <WeatherTile key={r.id} region={r} />
      ))}
      <ModelTile />
    </div>
  )
}
