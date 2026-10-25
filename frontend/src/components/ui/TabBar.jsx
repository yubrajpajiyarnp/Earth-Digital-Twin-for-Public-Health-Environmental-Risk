// Segmented-control tab selector. Deliberately unmounts inactive panels (see usage in
// App.jsx) rather than just hiding them with CSS — each region's panels fetch live
// forecasts and model output on mount, so only fetching the tab the user actually asks to
// see avoids paying for both on every page load.
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
