import { useEffect, useState } from 'react'
import { api } from '../api'
import StatTile from './StatTile'
import { classifyAqiLevel, zScore } from '../aqiLevels'

const TIME_ZONE = 'Asia/Kolkata'

function formatLocalTime(date) {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }).format(date)
}

function formatLocalDate(date) {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: TIME_ZONE,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(date)
}

export default function ConditionsBar() {
  const [now, setNow] = useState(new Date())
  const [weather, setWeather] = useState(null)
  const [weatherError, setWeatherError] = useState(null)
  const [proxy, setProxy] = useState(null)
  const [risk, setRisk] = useState(null)
  const [aqiError, setAqiError] = useState(null)

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  // Weather and AQI are fetched independently — /api/risk/aqi now generates its
  // explanation text via a local LLM call and can be noticeably slower than the plain
  // weather lookup, so it shouldn't hold up showing the time/weather that's already back.
  useEffect(() => {
    api.weather().then(setWeather).catch((err) => setWeatherError(err.message))
  }, [])

  useEffect(() => {
    Promise.all([api.aqiProxy(), api.riskAqi(7)])
      .then(([p, r]) => {
        setProxy(p)
        setRisk(r)
      })
      .catch((err) => setAqiError(err.message))
  }, [])

  const aqiZ = zScore(proxy?.value, risk?.baseline_mean, risk?.baseline_std)
  const aqiLevel = classifyAqiLevel(aqiZ)

  return (
    <div className="grid conditions-bar">
      <StatTile
        label="Local time"
        value={formatLocalTime(now)}
        caption={`${formatLocalDate(now)} · IST (UTC+5:30)`}
        accent="var(--series-1)"
      />
      {weatherError && (
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-warning)' }}>
          <div className="label">Weather</div>
          <div className="value" style={{ fontSize: 16 }}>
            Unavailable
          </div>
          <div className="caption">{weatherError}</div>
        </div>
      )}
      {!weatherError && !weather && (
        <div className="card stat-tile loading" style={{ gridColumn: 'span 2' }}>
          <span className="spinner" />
          Loading weather…
        </div>
      )}
      {weather && (
        <>
          <StatTile
            label="Temperature"
            value={`${weather.temperature_c.toFixed(1)}°C`}
            caption={`Feels like ${weather.feels_like_c.toFixed(1)}°C`}
            accent="var(--series-2)"
          />
          <StatTile
            label="Humidity"
            value={`${weather.humidity_pct}%`}
            caption="Relative humidity"
            accent="var(--series-3)"
          />
          <StatTile
            label="Pressure"
            value={`${weather.pressure_hpa.toFixed(0)} hPa`}
            caption={`Wind ${weather.wind_speed_kmh.toFixed(1)} km/h`}
            accent="var(--series-1)"
          />
          <StatTile
            label="Sky & climate"
            value={weather.weather_description}
            caption={
              weather.source === 'Open-Meteo'
                ? weather.climate_zone
                : `${weather.climate_zone} · via ${weather.source}`
            }
            accent="var(--series-2)"
          />
        </>
      )}
      {aqiError && (
        <div className="card stat-tile" style={{ '--stat-accent': 'var(--status-warning)' }}>
          <div className="label">Air quality</div>
          <div className="value" style={{ fontSize: 16 }}>
            Unavailable
          </div>
          <div className="caption">{aqiError}</div>
        </div>
      )}
      {!aqiError && !(proxy && risk) && (
        <div className="card stat-tile loading">
          <span className="spinner" />
          Loading AQI…
        </div>
      )}
      {proxy && risk && (
        <StatTile
          label="Air quality"
          value={proxy.value == null ? 'No data' : aqiLevel?.label ?? '—'}
          valueColor={proxy.value == null ? undefined : aqiLevel?.color}
          caption={proxy.value == null ? 'No recent clear reading' : `NO₂ proxy · ${proxy.value.toExponential(2)} mol/m²`}
          accent="var(--series-3)"
        />
      )}
    </div>
  )
}
