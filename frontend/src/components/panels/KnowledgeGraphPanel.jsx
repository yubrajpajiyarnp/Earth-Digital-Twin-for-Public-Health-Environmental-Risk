import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import KnowledgeGraphDiagram from './KnowledgeGraphDiagram'

export default function KnowledgeGraphPanel() {
  const [graph, setGraph] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.knowledgeGraph().then(setGraph).catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="card error">Knowledge graph failed to load: {error}</div>
  if (!graph) {
    return (
      <div className="card loading">
        <span className="spinner" />
        Loading knowledge graph…
      </div>
    )
  }

  return (
    <>
      <div className="card" style={{ marginBottom: 16 }}>
        <KnowledgeGraphDiagram nodes={graph.nodes} edges={graph.edges} />
      </div>
      <div className="kg-grid">
        {graph.edges.map((e) => (
          <div
            className="kg-card"
            key={`${e.source}-${e.target}`}
            style={{ '--kg-accent': e.data_connected ? 'var(--status-good)' : 'var(--text-muted)' }}
          >
            <div className="kg-card-head">
              <span className="path">
                {e.source.replace(/_/g, ' ')} → {e.target.replace(/_/g, ' ')}
              </span>
              <span className={`connected ${e.data_connected ? 'yes' : 'no'}`}>
                {e.data_connected ? 'live data' : 'schema only'}
              </span>
            </div>
            <div className="mechanism">{e.mechanism}</div>
            <div className="citation">{e.citation}</div>
          </div>
        ))}
      </div>
    </>
  )
}
