export default function StatusPill({ level }) {
  const cls = `pill pill-${level}`
  return (
    <span className={cls}>
      <span className="pill-dot" />
      {level}
    </span>
  )
}
