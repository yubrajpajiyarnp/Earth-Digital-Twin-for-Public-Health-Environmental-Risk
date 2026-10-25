import { useState } from 'react'
import TabBar from '../ui/TabBar'
import AdminKnowledgeGraphPanel from './AdminKnowledgeGraphPanel'
import AdminSettingsPanel from './AdminSettingsPanel'
import AdminDataSourcesPanel from './AdminDataSourcesPanel'

const ADMIN_TABS = [
  { id: 'sources', label: 'Data sources & model' },
  { id: 'graph', label: 'Knowledge graph' },
  { id: 'settings', label: 'Settings' },
]

export default function AdminPanel() {
  const [tab, setTab] = useState('sources')
  return (
    <div>
      <TabBar tabs={ADMIN_TABS} activeId={tab} onChange={setTab} />
      {tab === 'sources' && <AdminDataSourcesPanel />}
      {tab === 'graph' && <AdminKnowledgeGraphPanel />}
      {tab === 'settings' && <AdminSettingsPanel />}
    </div>
  )
}
