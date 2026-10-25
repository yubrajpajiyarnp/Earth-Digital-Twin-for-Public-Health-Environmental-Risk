import { navigate, useRoute } from './router'

// <a> that navigates client-side (keeping modifier-clicks as normal browser links) and
// gets an `active` class when its path is the current page.
export default function Link({ to, className = '', children, ...rest }) {
  const path = useRoute()
  function handleClick(e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    e.preventDefault()
    navigate(to)
  }
  return (
    <a href={to} onClick={handleClick} className={`${className} ${path === to ? 'active' : ''}`.trim()} {...rest}>
      {children}
    </a>
  )
}
