// Segmented-control tab selector. Deliberately unmounts inactive panels (see usage in
// App.jsx) rather than just hiding them with CSS — several of these panels make slow
// live-data calls (GBIF ~15-20s, NDVI 30-90s+) on mount, so only fetching the one the
// user actually asks to see avoids paying for all of them on every page load.
export default function TabBar({ tabs, activeId, onChange }) {
  return (
    <div className="tab-bar" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={tab.id === activeId}
          className={`tab-btn ${tab.id === activeId ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
