import { useAdmin } from './context/AdminContext'
import AdminLogin from './components/admin/AdminLogin'
import OverviewPage from './pages/OverviewPage'
import FloodPage from './pages/FloodPage'
import LandslidePage from './pages/LandslidePage'
import AdminPage from './pages/AdminPage'
import Link from './router/Link'
import { useRoute } from './router/router'

const PAGES = {
  '/': OverviewPage,
  '/flood': FloodPage,
  '/landslide': LandslidePage,
  '/admin': AdminPage,
}

function NotFound() {
  return (
    <div className="card" style={{ marginTop: 24 }}>
      <h2>Page not found</h2>
      <p className="scenario-desc">
        <Link to="/">Back to the overview</Link>
      </p>
    </div>
  )
}

function App() {
  const path = useRoute()
  const { verified } = useAdmin()
  const Page = PAGES[path.replace(/\/+$/, '') || '/'] || NotFound

  return (
    <>
      <nav className="top-nav">
        <Link to="/" className="brand">
          <span className="dot" />
          Nepal Disaster Twin
        </Link>
        <Link to="/">Overview</Link>
        <Link to="/flood">Kathmandu flood</Link>
        <Link to="/landslide">Mugling landslide</Link>
        {verified && <Link to="/admin">Admin</Link>}
        <AdminLogin />
      </nav>
      <Page />
    </>
  )
}

export default App
