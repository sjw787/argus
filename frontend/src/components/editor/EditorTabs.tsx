import { useRef, useState } from 'react'
import { useEditorStore } from '../../stores/editorStore'
import { X, Plus } from 'lucide-react'

export function EditorTabs() {
  const { tabs, activeTabId, addTab, closeTab, setActiveTab, updateTab } = useEditorStore()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const startEdit = (tabId: string, currentTitle: string) => {
    setEditingId(tabId)
    setEditValue(currentTitle)
    setTimeout(() => inputRef.current?.select(), 0)
  }

  const commitEdit = (tabId: string) => {
    const trimmed = editValue.trim()
    if (trimmed) updateTab(tabId, { title: trimmed })
    setEditingId(null)
  }

  return (
    <div
      className="flex items-center overflow-x-auto shrink-0"
      style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)', height: 34 }}
    >
      {tabs.map(tab => (
        <div
          key={tab.id}
          className="flex items-center gap-1.5 px-3 py-1 text-xs cursor-pointer shrink-0 border-r select-none"
          style={{
            background: tab.id === activeTabId ? 'var(--bg-primary)' : 'var(--bg-secondary)',
            color: tab.id === activeTabId ? 'var(--text-primary)' : 'var(--text-muted)',
            borderColor: 'var(--border)',
            borderBottom: tab.id === activeTabId ? '2px solid var(--accent)' : 'none',
            maxWidth: 200,
          }}
          onClick={() => setActiveTab(tab.id)}
        >
          {editingId === tab.id ? (
            <input
              ref={inputRef}
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              onBlur={() => commitEdit(tab.id)}
              onKeyDown={e => {
                if (e.key === 'Enter') commitEdit(tab.id)
                if (e.key === 'Escape') setEditingId(null)
              }}
              onClick={e => e.stopPropagation()}
              className="text-xs outline-none bg-transparent border-b"
              style={{ width: Math.max(60, editValue.length * 7), borderColor: 'var(--accent)', color: 'var(--text-primary)' }}
            />
          ) : (
            <span
              className="truncate"
              title="Double-click to rename"
              onDoubleClick={e => { e.stopPropagation(); startEdit(tab.id, tab.title) }}
            >
              {tab.title}
            </span>
          )}
          {tab.isLoading && <span className="animate-pulse text-xs shrink-0" style={{ color: 'var(--accent)' }}>●</span>}
          <button
            className="ml-1 hover:opacity-100 opacity-50 transition-opacity shrink-0"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, lineHeight: 1 }}
            onClick={e => { e.stopPropagation(); closeTab(tab.id) }}
          >
            <X size={11} />
          </button>
        </div>
      ))}
      <button
        className="px-2 py-1 shrink-0 transition-colors"
        style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
        onClick={() => addTab()}
        title="New Tab"
        onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
      >
        <Plus size={14} />
      </button>
    </div>
  )
}
