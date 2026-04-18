import { useRef, useState, useCallback, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, GridApi, CellContextMenuEvent } from 'ag-grid-community'
import { api } from '../../api/client'
import { Download, Ban, Filter, ListFilter } from 'lucide-react'
import { useThemeStore } from '../../stores/themeStore'
import { useEditorStore } from '../../stores/editorStore'

interface Props {
  queryExecutionId: string
  queryState?: string
  queryError?: string
  limitApplied?: boolean
  autoLimit?: number
  onCancel?: () => void
  tabId?: string
}

interface CellMenu {
  x: number
  y: number
  colId: string
  value: string | null
}

/** Append or inject a WHERE predicate into a SQL string. */
function addWhereCondition(sql: string, col: string, value: string | null): string {
  // Detect whether the query uses uppercase keywords so we can match
  const upper = /\bSELECT\b/.test(sql) || /\bFROM\b/.test(sql)
  const kw = (s: string) => upper ? s.toUpperCase() : s.toLowerCase()

  // Only quote the column name if it contains spaces or non-word characters
  const needsQuote = /[^a-zA-Z0-9_]/.test(col)
  const colRef = needsQuote ? `"${col}"` : col

  // Build the predicate
  let predicate: string
  if (value === null) {
    predicate = `${colRef} ${kw('is null')}`
  } else if (/^-?\d+(\.\d+)?$/.test(value)) {
    predicate = `${colRef} = ${value}`
  } else {
    predicate = `${colRef} = '${value.replace(/'/g, "''")}'`
  }

  // Strip trailing semicolons/whitespace to manipulate cleanly
  const trimmed = sql.trimEnd().replace(/;+$/, '').trimEnd()

  // Detect the leading indentation of the last line to match alignment
  const lines = trimmed.split('\n')
  const lastLineIndent = lines[lines.length - 1].match(/^(\s*)/)?.[1] ?? ''

  const whereRe = /\bWHERE\b/i
  const clauseRe = /\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b/i

  if (whereRe.test(trimmed)) {
    // WHERE already exists — append AND
    const match = clauseRe.exec(trimmed)
    if (match) {
      const indent = trimmed.slice(0, match.index).match(/(\s*)$/)?.[1] ?? lastLineIndent
      return trimmed.slice(0, match.index) + `${indent}${kw('and')} ${predicate}\n` + trimmed.slice(match.index) + ';'
    }
    return trimmed + `\n${lastLineIndent}${kw('and')} ${predicate};`
  }

  // No WHERE — insert before ORDER BY / GROUP BY / HAVING / LIMIT, or at end
  const match = clauseRe.exec(trimmed)
  if (match) {
    const indent = trimmed.slice(0, match.index).match(/(\s*)$/)?.[1] ?? lastLineIndent
    return trimmed.slice(0, match.index) + `${indent}${kw('where')} ${predicate}\n` + trimmed.slice(match.index) + ';'
  }
  return trimmed + `\n${lastLineIndent}${kw('where')} ${predicate};`
}

export function ResultsGrid({ queryExecutionId, queryState, queryError, limitApplied, autoLimit, onCancel, tabId }: Props) {
  const [isExporting, setIsExporting] = useState(false)
  const [cellMenu, setCellMenu] = useState<CellMenu | null>(null)
  const gridApiRef = useRef<GridApi | null>(null)
  const gridTheme = useThemeStore(s => s.theme === 'light' ? 'ag-theme-balham' : 'ag-theme-balham-dark')

  // Close context menu on outside click
  useEffect(() => {
    if (!cellMenu) return
    const close = () => setCellMenu(null)
    window.addEventListener('click', close)
    window.addEventListener('contextmenu', close)
    return () => { window.removeEventListener('click', close); window.removeEventListener('contextmenu', close) }
  }, [cellMenu])

  const handleCellContextMenu = useCallback((e: CellContextMenuEvent) => {
    const evt = e.event as MouseEvent
    evt.preventDefault()
    setCellMenu({
      x: evt.clientX,
      y: evt.clientY,
      colId: e.column.getColId(),
      value: e.value ?? null,
    })
  }, [])

  const applyFilter = useCallback(() => {
    if (!cellMenu || !gridApiRef.current) return
    gridApiRef.current.setColumnFilterModel(cellMenu.colId, {
      filterType: 'text',
      type: 'equals',
      filter: cellMenu.value ?? '',
    }).then(() => gridApiRef.current!.onFilterChanged())
    setCellMenu(null)
  }, [cellMenu])

  const addToWhere = useCallback(() => {
    if (!cellMenu || !tabId) return
    const tab = useEditorStore.getState().tabs.find(t => t.id === tabId)
    if (!tab) return
    const newSql = addWhereCondition(tab.sql, cellMenu.colId, cellMenu.value)
    useEditorStore.getState().updateTab(tabId, { sql: newSql })
    setCellMenu(null)
  }, [cellMenu, tabId])

  const { data: results, isFetching } = useQuery({
    queryKey: ['queryResults', queryExecutionId],
    queryFn: () => api.getQueryResults(queryExecutionId),
    enabled: queryState === 'SUCCEEDED',
    staleTime: Infinity,
  })

  const handleExport = async (format: string) => {
    setIsExporting(true)
    try {
      const blob = await api.exportResults(queryExecutionId, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `query_${queryExecutionId.slice(0, 8)}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setIsExporting(false)
    }
  }

  if (queryState === 'RUNNING' || queryState === 'QUEUED') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <span className="text-sm animate-pulse" style={{ color: 'var(--text-muted)' }}>Executing query…</span>
        {onCancel && (
          <button
            onClick={onCancel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs"
            style={{ background: 'var(--bg-secondary)', color: 'var(--error)', border: '1px solid var(--error)', cursor: 'pointer' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'color-mix(in srgb, var(--error) 10%, transparent)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'var(--bg-secondary)')}
          >
            <Ban size={12} /> Cancel query
          </button>
        )}
      </div>
    )
  }

  if (queryState === 'FAILED') {
    return (
      <div className="flex flex-col gap-2 p-4 h-full overflow-auto" style={{ background: 'var(--bg-panel)' }}>
        <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--error)' }}>
          <span>✕</span> Query Failed
        </div>
        {queryError && (
          <pre
            className="text-xs rounded p-3 overflow-auto whitespace-pre-wrap"
            style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--error)', fontFamily: 'monospace' }}
          >
            {queryError}
          </pre>
        )}
      </div>
    )
  }

  if (!results || isFetching) {
    return (
      <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--text-muted)' }}>
        Loading results...
      </div>
    )
  }

  const colDefs: ColDef[] = results.columns.map(col => ({
    headerName: col.name,
    field: col.name,
    resizable: true,
    sortable: true,
    filter: true,
    minWidth: 80,
    flex: 1,
  }))

  const rowData = results.rows.map(row => {
    const obj: Record<string, string | null> = {}
    results.columns.forEach((col, i) => { obj[col.name] = row[i] })
    return obj
  })

  return (
    <div className="flex flex-col h-full">
      <div
        className="flex items-center gap-3 px-3 py-1.5 shrink-0 text-xs"
        style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}
      >
        <span style={{ color: 'var(--text-muted)' }}>
          {results.row_count} row{results.row_count !== 1 ? 's' : ''}
        </span>
        {limitApplied && autoLimit && (
          <span
            className="flex items-center gap-1 px-2 py-0.5 rounded text-xs"
            style={{ background: 'rgba(234,179,8,0.12)', color: '#ca8a04', border: '1px solid rgba(234,179,8,0.3)' }}
            title="Query had no LIMIT clause — auto-limit was applied. Add an explicit LIMIT to override."
          >
            ⚠ Auto-limited to {autoLimit.toLocaleString()} rows
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {['csv', 'json', 'xlsx', 'parquet'].map(fmt => (
            <button
              key={fmt}
              onClick={() => handleExport(fmt)}
              disabled={isExporting}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors"
              style={{
                background: 'var(--bg-panel)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                cursor: 'pointer',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
            >
              <Download size={10} />
              {fmt.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-auto" style={{ minHeight: 0 }}>
        <div className={gridTheme} style={{ width: '100%' }}>
          <AgGridReact
            theme="legacy"
            domLayout="autoHeight"
            columnDefs={colDefs}
            rowData={rowData}
            suppressMovableColumns={false}
            enableCellTextSelection
            suppressRowClickSelection
            onGridReady={e => { gridApiRef.current = e.api }}
            onCellContextMenu={handleCellContextMenu}
            preventDefaultOnContextMenu
          />
        </div>
      </div>

      {cellMenu && (
        <div
          style={{
            position: 'fixed',
            top: cellMenu.y,
            left: cellMenu.x,
            zIndex: 9999,
            background: 'var(--bg-panel)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            minWidth: 200,
            padding: '3px 0',
          }}
          onClick={e => e.stopPropagation()}
        >
          <button
            onClick={applyFilter}
            className="flex items-center gap-2 w-full px-3 py-2 text-xs text-left"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-primary)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <Filter size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <span>
              Filter by <strong style={{ fontFamily: 'monospace' }}>
                {cellMenu.value === null ? 'NULL' : cellMenu.value.length > 40 ? cellMenu.value.slice(0, 40) + '…' : cellMenu.value}
              </strong>
            </span>
          </button>
          {tabId && (
            <>
              <div style={{ height: 1, background: 'var(--border)', margin: '3px 0' }} />
              <button
                onClick={addToWhere}
                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-left"
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-primary)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <ListFilter size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                <span>
                  Add to WHERE: <strong style={{ fontFamily: 'monospace' }}>
                    {cellMenu.value === null
                      ? `"${cellMenu.colId}" IS NULL`
                      : /^-?\d+(\.\d+)?$/.test(cellMenu.value)
                        ? `"${cellMenu.colId}" = ${cellMenu.value}`
                        : `"${cellMenu.colId}" = '${cellMenu.value.length > 20 ? cellMenu.value.slice(0, 20) + '…' : cellMenu.value}'`}
                  </strong>
                </span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
