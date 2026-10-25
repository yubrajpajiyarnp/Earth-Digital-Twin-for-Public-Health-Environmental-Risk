import AdminPanel from '../components/admin/AdminPanel'
import { useAdmin } from '../context/AdminContext'
import usePageTitle from './usePageTitle'

export default function AdminPage() {
  usePageTitle('Admin')
  const { verified } = useAdmin()
  return (
    <div className="page">
      <section className="block" style={{ marginTop: 24 }}>
        <div className="section-head">
          <h2>Admin</h2>
          <span className="section-note">Data sources, model retraining, graph edges &amp; settings</span>
        </div>
        {verified ? (
          <AdminPanel />
        ) : (
          <div className="card empty-hint">Sign in with the admin email (top right) to manage this dashboard.</div>
        )}
      </section>
    </div>
  )
}
