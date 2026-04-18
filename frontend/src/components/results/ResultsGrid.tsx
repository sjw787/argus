import { useRef, useState, useCallback, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, GridApi, CellContextMenuEvent } from 'ag-grid-community'
import { format as formatSql } from 'sql-formatter'
import { api } from '../../api/client'
import { Download, Ban, Filter, ListFilter } from 'lucide-react'
import { useThemeStore } from '../../stores/themeStore'
import { useEditorStore } from '../../stores/editorStore'
import { splitSqlStatements, addWhereCondition } from '../../utils/sql'

interface Props {
  queryExecutionId: string
  queryState?: string
  queryError?: string
  limitApplied?: boolean
  autoLimit?: number
  onCancel?: () => void
  tabId?: string
  /** Index of this result within a multi-query tab (0-based). Used to target
   *  the correct statement when injecting WHERE conditions. */
  queryIndex?: number
}

interface CellMenu {
  x: number
  y: number
  colId: string
  value: string | null
  colType?: string
}

export function ResultsGrid({ queryExecutionId, queryState, queryError, limitApplied, autoLimit, onCancel, tabId, queryIndex }: Props) {
  const [isExporting, setIsExporting] = useState(false)
  const [cellMenu, setCellMenu] = useState<CellMenu | null>(null)
  const gridApiRef = useRef<GridApi | null>(null)
  const colTypeMapRef = useRef<Record<string, string>>({})
  const gridTheme = useThemeStore(s => s.theme === 'light' ? 'ag-theme-balham' : 'ag-theme-balham-dark')
  const formatStyle = useThemeStore(s => s.formatStyle)

  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.getConfig, staleTime: 60000 })
  const allowDownload = config?.allow_download ?? true

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
    const colId = e.column.getColId()
    setCellMenu({
      x: evt.clientX,
      y: evt.clientY,
      colId,
      value: e.value ?? null,
      colType: colTypeMapRef.current[colId],
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

    let newSql: string
    if (queryIndex !== undefined) {
      // Multi-query tab — only modify the statement that produced these results.
      // splitSqlStatements strips semicolons, so we must restore them on all
      // statements before joining; otherwise formatSql sees one big statement
      // and removes the inter-query semicolons.
      const stmts = splitSqlStatements(tab.sql)
      const target = stmts[queryIndex]
      if (target === undefined) return
      stmts[queryIndex] = addWhereCondition(target, cellMenu.colId, cellMenu.value, cellMenu.colType)
      newSql = stmts.map(s => s.trimEnd().replace(/;+$/, '') + ';').join('\n\n')
    } else {
      newSql = addWhereCondition(tab.sql, cellMenu.colId, cellMenu.value, cellMenu.colType)
    }

    // Re-run through the formatter to keep the injected clause consistent with
    // the rest of the query's style (keyword case, indentation, line breaks).
    try {
      newSql = formatSql(newSql, {
        language: 'trino',
        tabWidth: 2,
        keywordCase: 'upper',
        linesBetweenQueries: 2,
        indentStyle: formatStyle,
      })
    } catch {
      // If the formatter fails (e.g. partial SQL), keep the raw injection
    }

    useEditorStore.getState().updateTab(tabId, { sql: newSql })
    setCellMenu(null)
  }, [cellMenu, tabId, queryIndex, formatStyle])

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

  // Build column type map whenever results arrive
  colTypeMapRef.current = Object.fromEntries(
    results.columns.map(col => [col.name, col.type ?? ''])
  )

  const colDefs: ColDef[] = results.columns.map(col => ({
    headerName: col.name,
    field: col.name,
    resizable: true,
    sortable: true,
    filter: true,
    minWidth: 80,
    flex: 1,
    headerTooltip: col.type ?? undefined,
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
          {allowDownload && ['csv', 'json', 'xlsx', 'parquet'].map(fmt => (
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
