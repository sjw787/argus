import { EditorTabs } from './EditorTabs'
import { SqlEditorPanel } from './SqlEditorPanel'
import { ErDiagramPanel } from '../diagram/ErDiagramPanel'
import { useUIStore } from '../../stores/uiStore'
import { useEditorStore } from '../../stores/editorStore'

export function EditorArea() {
  const { showErDiagram, selectedDatabase, setShowErDiagram } = useUIStore()
  const { tabs, activeTabId } = useEditorStore()

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-primary)' }}>
      <EditorTabs />
      {showErDiagram && selectedDatabase ? (
        <div className="flex-1 overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-1.5 text-xs" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
            <span style={{ color: 'var(--text-muted)' }}>ER Diagram:</span>
            <span style={{ color: 'var(--accent)' }}>{selectedDatabase}</span>
            <button
              className="ml-auto text-xs px-2 py-0.5 rounded"
              style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)', cursor: 'pointer', border: 'none' }}
              onClick={() => setShowErDiagram(false)}
            >
              ✕ Close
            </button>
          </div>
          <ErDiagramPanel databaseName={selectedDatabase} />
        </div>
      ) : (
        <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
          {tabs.map(tab => (
            <div key={tab.id} style={{ display: tab.id === activeTabId ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
              <SqlEditorPanel tabId={tab.id} />
            </div>
          ))}
          {tabs.length === 0 && (
            <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--text-muted)' }}>
              Click + to open a new query tab
            </div>
          )}
        </div>
      )}
    </div>
  )
}
