import { useRef, useState, useEffect, useCallback } from 'react'
import { useEditorStore } from '../../stores/editorStore'
import { X, Plus, GitBranch } from 'lucide-react'

interface TabMenu {
  x: number
  y: number
  tabId: string
  tabTitle: string
}

export function EditorTabs() {
  const { tabs, activeTabId, addTab, closeTab, closeOtherTabs, closeAllTabs, setActiveTab, updateTab } = useEditorStore()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [tabMenu, setTabMenu] = useState<TabMenu | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const startEdit = (tabId: string, currentTitle: string) => {
    setTabMenu(null)
    setEditingId(tabId)
    setEditValue(currentTitle)
    setTimeout(() => inputRef.current?.select(), 0)
  }

  const commitEdit = (tabId: string) => {
    const trimmed = editValue.trim()
    if (trimmed) updateTab(tabId, { title: trimmed })
    setEditingId(null)
  }

  const openTabMenu = useCallback((e: React.MouseEvent, tabId: string, tabTitle: string) => {
    e.preventDefault()
    e.stopPropagation()
    setTabMenu({ x: e.clientX, y: e.clientY, tabId, tabTitle })
  }, [])

  useEffect(() => {
    if (!tabMenu) return
    const close = () => setTabMenu(null)
    window.addEventListener('click', close)
    window.addEventListener('contextmenu', close)
    return () => { window.removeEventListener('click', close); window.removeEventListener('contextmenu', close) }
  }, [tabMenu])

  return (
    <>
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
            onContextMenu={e => { setActiveTab(tab.id); openTabMenu(e, tab.id, tab.title) }}
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
                className="truncate flex items-center gap-1"
                onDoubleClick={e => { e.stopPropagation(); startEdit(tab.id, tab.title) }}
              >
                {tab.type === 'er-diagram' && <GitBranch size={10} style={{ flexShrink: 0, opacity: 0.7 }} />}
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

      {tabMenu && (
        <div
          style={{
            position: 'fixed',
            top: tabMenu.y,
            left: tabMenu.x,
            zIndex: 9999,
            background: 'var(--bg-panel)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            minWidth: 160,
            padding: '3px 0',
          }}
          onClick={e => e.stopPropagation()}
        >
          {[
            { label: 'Rename', action: () => startEdit(tabMenu.tabId, tabMenu.tabTitle) },
            null,
            { label: 'Close', action: () => { closeTab(tabMenu.tabId); setTabMenu(null) } },
            { label: 'Close Others', action: () => { closeOtherTabs(tabMenu.tabId); setTabMenu(null) }, disabled: tabs.length <= 1 },
            { label: 'Close All', action: () => { closeAllTabs(); setTabMenu(null) } },
          ].map((item, i) =>
            item === null ? (
              <div key={i} style={{ height: 1, background: 'var(--border)', margin: '3px 0' }} />
            ) : (
              <button
                key={item.label}
                onClick={item.disabled ? undefined : item.action}
                className="flex w-full px-3 py-1.5 text-xs text-left"
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: item.disabled ? 'default' : 'pointer',
                  color: item.disabled ? 'var(--text-muted)' : 'var(--text-primary)',
                  opacity: item.disabled ? 0.4 : 1,
                }}
                onMouseEnter={e => { if (!item.disabled) e.currentTarget.style.background = 'var(--bg-hover)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
              >
                {item.label}
              </button>
            )
          )}
        </div>
      )}
    </>
  )
}
