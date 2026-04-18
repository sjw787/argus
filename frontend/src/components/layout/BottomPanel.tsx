import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { QueryListItem } from '../../api/client'
import { useUIStore } from '../../stores/uiStore'
import { useQueryNamesStore } from '../../stores/queryNamesStore'
import { useEditorStore } from '../../stores/editorStore'
import { ChevronDown, CheckCircle, XCircle, Loader, Clock, Ban, ExternalLink } from 'lucide-react'

const STATE_ICONS: Record<string, React.ReactNode> = {
  SUCCEEDED: <CheckCircle size={13} style={{ color: 'var(--success)' }} />,
  FAILED: <XCircle size={13} style={{ color: 'var(--error)' }} />,
  CANCELLED: <XCircle size={13} style={{ color: 'var(--warning)' }} />,
  RUNNING: <Loader size={13} className="animate-spin" style={{ color: 'var(--accent)' }} />,
  QUEUED: <Clock size={13} style={{ color: 'var(--text-muted)' }} />,
}

interface LocalActiveQuery {
  id: string
  tabId: string
  tabTitle: string
  database: string
  state: string
  sql?: string
}

export function BottomPanel({ onToggle }: { onToggle?: () => void }) {
  const { bottomTab, setBottomTab } = useUIStore()
  const { names, descriptions } = useQueryNamesStore()
  const { openTab, setActiveTab, tabs, updateTab } = useEditorStore()
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const handleOpenInEditor = async (item: QueryListItem) => {
    setLoadingId(item.query_execution_id)
    try {
      const detail = await api.getQuery(item.query_execution_id)
      openTab({
        title: names[item.query_execution_id] ?? item.database ?? 'Query',
        sql: detail.query,
        database: detail.database ?? item.database ?? '',
      })
    } finally {
      setLoadingId(null)
    }
  }

  const { data: history } = useQuery({
    queryKey: ['queryHistory'],
    queryFn: () => api.listQueries(undefined, 50),
    refetchInterval: 5000,
  })

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.cancelQuery(id),
    onSuccess: (_, id) => {
      // Update the tab state to CANCELLED
      tabs.forEach(tab => {
        if (tab.queryExecutionId === id) {
          updateTab(tab.id, { queryState: 'CANCELLED', isLoading: false })
        }
        if (tab.queryExecutions?.some(qe => qe.id === id)) {
          updateTab(tab.id, {
            queryExecutions: tab.queryExecutions?.map(qe =>
              qe.id === id ? { ...qe, state: 'CANCELLED' } : qe
            ),
          })
        }
      })
      queryClient.invalidateQueries({ queryKey: ['queryHistory'] })
    },
  })

  // Build active query list directly from editor store (real-time, no poll lag)
  const localActive: LocalActiveQuery[] = tabs.flatMap(tab => {
    const result: LocalActiveQuery[] = []
    if (tab.queryExecutions && tab.queryExecutions.length > 0) {
      tab.queryExecutions
        .filter(qe => qe.state === 'RUNNING' || qe.state === 'QUEUED')
        .forEach(qe => result.push({
          id: qe.id,
          tabId: tab.id,
          tabTitle: tab.title,
          database: tab.database,
          state: qe.state,
        }))
    } else if (tab.isLoading && tab.queryExecutionId) {
      result.push({
        id: tab.queryExecutionId,
        tabId: tab.id,
        tabTitle: tab.title,
        database: tab.database,
        state: tab.queryState ?? 'RUNNING',
      })
    }
    return result
  })

  const historyList = history ?? []

  const tabDefs = [
    { id: 'history' as const, label: 'Query History' },
    { id: 'active' as const, label: 'Active Queries' },
    { id: 'messages' as const, label: 'Messages' },
  ]

  return (
    <div
      className="flex flex-col h-full"
      style={{ background: 'var(--bg-panel)', borderTop: '1px solid var(--border)' }}
      onDoubleClick={(e) => {
        // Double-click anywhere in the panel (tab bar or content) to collapse.
        // Ignore clicks on interactive elements so we don't hijack their own
        // double-click behaviour (e.g. text selection inside table cells, or
        // double-firing the chevron close button).
        const target = e.target as HTMLElement
        if (target.closest('button, a, input, textarea, select')) return
        onToggle?.()
      }}
    >
      <div
        className="flex items-center gap-0 px-2 shrink-0"
        style={{ borderBottom: '1px solid var(--border)', cursor: 'default' }}
      >
        {tabDefs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setBottomTab(tab.id)}
            className="px-3 py-1.5 text-xs transition-colors"
            style={{
              color: bottomTab === tab.id ? 'var(--accent)' : 'var(--text-muted)',
              background: 'transparent',
              cursor: 'pointer',
              border: 'none',
              borderBottom: bottomTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
            }}
          >
            {tab.label}
            {tab.id === 'active' && localActive.length > 0 && (
              <span className="ml-1 px-1 rounded text-xs" style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}>
                {localActive.length}
              </span>
            )}
          </button>
        ))}
        <button
          onClick={onToggle}
          title="Hide panel"
          className="ml-auto p-1 rounded"
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          <ChevronDown size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-auto scrollbar-thin">
        {bottomTab === 'history' && <QueryHistoryList items={historyList} names={names} descriptions={descriptions} onOpen={handleOpenInEditor} loadingId={loadingId} />}
        {bottomTab === 'active' && (
          <ActiveQueriesPanel
            queries={localActive}
            onGoToTab={setActiveTab}
            onCancel={id => cancelMutation.mutate(id)}
            cancellingId={cancelMutation.isPending ? (cancelMutation.variables as string) : null}
          />
        )}
        {bottomTab === 'messages' && (
          <div className="p-3 text-xs" style={{ color: 'var(--text-muted)' }}>No messages.</div>
        )}
      </div>
    </div>
  )
}

function ActiveQueriesPanel({ queries, onGoToTab, onCancel, cancellingId }: {
  queries: LocalActiveQuery[]
  onGoToTab: (tabId: string) => void
  onCancel: (id: string) => void
  cancellingId: string | null
}) {
  if (!queries.length) {
    return <div className="p-3 text-xs" style={{ color: 'var(--text-muted)' }}>No queries running.</div>
  }
  return (
    <table className="w-full text-xs">
      <thead>
        <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
          <th className="text-left px-3 py-1.5 font-medium">Status</th>
          <th className="text-left px-3 py-1.5 font-medium">Tab</th>
          <th className="text-left px-3 py-1.5 font-medium">Query ID</th>
          <th className="text-left px-3 py-1.5 font-medium">Database</th>
          <th className="text-left px-3 py-1.5 font-medium">Actions</th>
        </tr>
      </thead>
      <tbody>
        {queries.map(q => (
          <tr
            key={q.id}
            style={{ borderBottom: '1px solid var(--border)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <td className="px-3 py-1.5">
              <span className="flex items-center gap-1">
                {STATE_ICONS[q.state] ?? null}
                {q.state}
              </span>
            </td>
            <td className="px-3 py-1.5" style={{ color: 'var(--text-primary)' }}>{q.tabTitle}</td>
            <td className="px-3 py-1.5 font-mono" style={{ color: 'var(--text-muted)' }}>
              {q.id.slice(0, 8)}…
            </td>
            <td className="px-3 py-1.5">{q.database || '-'}</td>
            <td className="px-3 py-1.5">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onGoToTab(q.tabId)}
                  title="Go to editor tab"
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--accent)', padding: 0, display: 'flex', alignItems: 'center' }}
                >
                  <ExternalLink size={12} />
                </button>
                <button
                  onClick={() => onCancel(q.id)}
                  disabled={cancellingId === q.id}
                  title="Cancel query"
                  style={{ background: 'transparent', border: 'none', cursor: cancellingId === q.id ? 'default' : 'pointer', color: 'var(--error)', padding: 0, display: 'flex', alignItems: 'center', opacity: cancellingId === q.id ? 0.5 : 1 }}
                >
                  {cancellingId === q.id ? <Loader size={12} className="animate-spin" /> : <Ban size={12} />}
                </button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function QueryHistoryList({ items, names, descriptions, onOpen, loadingId }: {
  items: QueryListItem[]
  names: Record<string, string>
  descriptions: Record<string, string>
  onOpen: (item: QueryListItem) => void
  loadingId: string | null
}) {
  if (!items.length) {
    return <div className="p-3 text-xs" style={{ color: 'var(--text-muted)' }}>No queries found.</div>
  }
  return (
    <table className="w-full text-xs">
      <thead>
        <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
          <th className="text-left px-3 py-1.5 font-medium">Status</th>
          <th className="text-left px-3 py-1.5 font-medium">Name</th>
          <th className="text-left px-3 py-1.5 font-medium">Query ID</th>
          <th className="text-left px-3 py-1.5 font-medium">Database</th>
          <th className="text-left px-3 py-1.5 font-medium">Workgroup</th>
          <th className="text-left px-3 py-1.5 font-medium">Submitted</th>
        </tr>
      </thead>
      <tbody>
        {items.map(q => (
          <tr
            key={q.query_execution_id}
            title={descriptions[q.query_execution_id] ?? 'Click to open in editor'}
            style={{ borderBottom: '1px solid var(--border)', cursor: loadingId === q.query_execution_id ? 'wait' : 'pointer' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            onClick={() => { if (!loadingId) onOpen(q) }}
          >
            <td className="px-3 py-1.5">
              <span className="flex items-center gap-1">
                {STATE_ICONS[q.state] ?? null}
                {q.state}
              </span>
            </td>
            <td className="px-3 py-1.5" style={{ color: names[q.query_execution_id] ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              {names[q.query_execution_id] ?? <span style={{ fontStyle: 'italic' }}>—</span>}
            </td>
            <td className="px-3 py-1.5 font-mono" style={{ color: 'var(--text-muted)' }}>
              {q.query_execution_id.slice(0, 8)}...
            </td>
            <td className="px-3 py-1.5">{q.database ?? '-'}</td>
            <td className="px-3 py-1.5">{q.workgroup ?? '-'}</td>
            <td className="px-3 py-1.5" style={{ color: 'var(--text-muted)' }}>
              {q.submitted ? q.submitted.slice(0, 19).replace('T', ' ') : '-'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
