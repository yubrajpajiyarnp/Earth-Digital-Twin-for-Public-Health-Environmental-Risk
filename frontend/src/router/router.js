import { useSyncExternalStore } from 'react'

// Minimal path router on the History API — four static pages don't justify a routing
// dependency. Vite's dev server (and `vite preview`) serve index.html for any path, so
// deep links like /landslide load directly.
const listeners = new Set()

function subscribe(listener) {
  listeners.add(listener)
  window.addEventListener('popstate', listener)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('popstate', listener)
  }
}

export function navigate(path) {
  if (path === window.location.pathname) return
  window.history.pushState({}, '', path)
  window.scrollTo({ top: 0 })
  listeners.forEach((l) => l())
}

export function useRoute() {
  return useSyncExternalStore(subscribe, () => window.location.pathname)
}
