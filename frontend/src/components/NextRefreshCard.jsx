import { useEffect, useRef, useState } from 'react'

function formatMmSs(totalSeconds) {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// Countdown to the next automatic re-fetch from the live API — this is a real, exact timer
// the app controls (not a guess at satellite pass times), so the number shown is always
// accurate.
export default function NextRefreshCard({ intervalSeconds = 300, onRefresh }) {
  const [secondsLeft, setSecondsLeft] = useState(intervalSeconds)
  const onRefreshRef = useRef(onRefresh)
  onRefreshRef.current = onRefresh

  useEffect(() => {
    const id = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          onRefreshRef.current?.()
          return intervalSeconds
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [intervalSeconds])

  return (
    <div className="card next-refresh">
      <div className="label">Next data refresh</div>
      <div className="next-refresh-value">{formatMmSs(secondsLeft)}</div>
      <div className="caption">
        Auto-refreshing from the live API every {Math.round(intervalSeconds / 60)} min
      </div>
    </div>
  )
}
