import { useState } from 'react'
import TabBar from './TabBar'
import AdminHistoryPanel from './AdminHistoryPanel'
import AdminKnowledgeGraphPanel from './AdminKnowledgeGraphPanel'
import AdminSettingsPanel from './AdminSettingsPanel'

const ADMIN_TABS = [
  { id: 'history', label: 'History' },
  { id: 'graph', label: 'Knowledge graph' },
  { id: 'settings', label: 'Settings' },
]

export default function AdminPanel() {
  const [tab, setTab] = useState('history')
  return (
    <div>
      <TabBar tabs={ADMIN_TABS} activeId={tab} onChange={setTab} />
      {tab === 'history' && <AdminHistoryPanel />}
      {tab === 'graph' && <AdminKnowledgeGraphPanel />}
      {tab === 'settings' && <AdminSettingsPanel />}
    </div>
  )
}
