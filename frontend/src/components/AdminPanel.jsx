import { useState } from 'react'
import TabBar from './TabBar'
import AdminHistoryPanel from './AdminHistoryPanel'
import AdminKnowledgeGraphPanel from './AdminKnowledgeGraphPanel'
import AdminSettingsPanel from './AdminSettingsPanel'
import AdminDataSourcesPanel from './AdminDataSourcesPanel'

const ADMIN_TABS = [
  { id: 'history', label: 'History' },
  { id: 'graph', label: 'Knowledge graph' },
  { id: 'settings', label: 'Settings' },
  { id: 'sources', label: 'Data sources' },
]

export default function AdminPanel() {
  const [tab, setTab] = useState('history')
  return (
    <div>
      <TabBar tabs={ADMIN_TABS} activeId={tab} onChange={setTab} />
      {tab === 'history' && <AdminHistoryPanel />}
      {tab === 'graph' && <AdminKnowledgeGraphPanel />}
      {tab === 'settings' && <AdminSettingsPanel />}
      {tab === 'sources' && <AdminDataSourcesPanel />}
    </div>
  )
}
