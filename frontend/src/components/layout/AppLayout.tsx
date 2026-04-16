import { useEffect, useState } from 'react'
import { Allotment } from 'allotment'
import 'allotment/dist/style.css'
import { DatabaseNavigator } from '../navigator/DatabaseNavigator'
import { EditorArea } from '../editor/EditorArea'
import { BottomPanel } from './BottomPanel'
import { Toolbar } from './Toolbar'
import { useEditorStore } from '../../stores/editorStore'
import { useThemeStore } from '../../stores/themeStore'

export function AppLayout() {
  const tabs = useEditorStore(s => s.tabs)
  const addTab = useEditorStore(s => s.addTab)
  const showHistoryDefault = useThemeStore(s => s.showHistoryDefault)
  const [showHistory, setShowHistory] = useState(showHistoryDefault)

  useEffect(() => {
    if (tabs.length === 0) addTab()
  }, [])

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg-primary)' }}>
      <Toolbar />
      <div className="flex-1 overflow-hidden">
        <Allotment defaultSizes={[280, 800]}>
          <Allotment.Pane minSize={180} maxSize={500}>
            <DatabaseNavigator />
          </Allotment.Pane>
          <Allotment.Pane>
            <Allotment vertical defaultSizes={[600, 200]}>
              <Allotment.Pane minSize={100}>
                <EditorArea />
              </Allotment.Pane>
              <Allotment.Pane minSize={120} maxSize={400} visible={showHistory}>
                <BottomPanel onToggle={() => setShowHistory(v => !v)} />
              </Allotment.Pane>
            </Allotment>
          </Allotment.Pane>
        </Allotment>
      </div>

      {/* Collapsed history bar */}
      {!showHistory && (
        <div
          className="flex items-center gap-2 px-3 shrink-0"
          style={{ height: 28, background: 'var(--bg-panel)', borderTop: '1px solid var(--border)', cursor: 'pointer' }}
          onClick={() => setShowHistory(true)}
          title="Show Query History"
        >
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>▲ Query History</span>
        </div>
      )}
    </div>
  )
}
