import { EditorTabs } from './EditorTabs'
import { SqlEditorPanel } from './SqlEditorPanel'
import { ErDiagramPanel } from '../diagram/ErDiagramPanel'
import { useEditorStore } from '../../stores/editorStore'

export function EditorArea() {
  const { tabs, activeTabId } = useEditorStore()

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-primary)' }}>
      <EditorTabs />
      <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
        {tabs.map(tab => (
          <div key={tab.id} style={{ display: tab.id === activeTabId ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
            {tab.type === 'er-diagram'
              ? <ErDiagramPanel databaseName={tab.database} />
              : <SqlEditorPanel tabId={tab.id} />
            }
          </div>
        ))}
        {tabs.length === 0 && (
          <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--text-muted)' }}>
            Click + to open a new query tab
          </div>
        )}
      </div>
    </div>
  )
}
