import React, { useRef, useEffect, useState, useCallback } from 'react'
import { Allotment } from 'allotment'
import Editor, { useMonaco, type OnMount } from '@monaco-editor/react'
import type * as Monaco from 'monaco-editor'
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { ExplainPlanType } from '../../api/client'
import { useEditorStore } from '../../stores/editorStore'
import { useThemeStore } from '../../stores/themeStore'
import { useQueryNamesStore, extractSqlComment } from '../../stores/queryNamesStore'
import { registerSqlCompletion, unregisterSqlCompletion, setActiveDatabase } from '../../lib/sqlCompletion'
import { registerSqlDiagnostics, unregisterSqlDiagnostics } from '../../lib/sqlDiagnostics'
import { ResultsGrid } from '../results/ResultsGrid'
import { splitSqlStatements, applyFormatStyle } from '../../utils/sql'
import { Play, ChevronDown, Search, WandSparkles, Loader, FileSearch } from 'lucide-react'


const PAGE_LIMIT = 50

function DatabasePicker({ value, onChange }: {
  value: string
  onChange: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const handleSearchChange = (val: string) => {
    setSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedSearch(val), 300)
  }

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isFetching } = useInfiniteQuery({
    queryKey: ['databases-picker', debouncedSearch],
    queryFn: ({ pageParam = 0 }) =>
      api.listDatabases({ search: debouncedSearch, limit: PAGE_LIMIT, offset: pageParam as number }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.has_more ? last.offset + last.limit : undefined,
    staleTime: 30000,
    enabled: open,
  })

  const allDbs = data?.pages.flatMap(p => p.items) ?? []
  const total = data?.pages[0]?.total ?? 0

  useEffect(() => {
    if (open) setTimeout(() => searchRef.current?.focus(), 50)
    else { setSearch(''); setDebouncedSearch('') }
  }, [open])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleScroll = () => {
    const el = listRef.current
    if (!el || !hasNextPage || isFetchingNextPage) return
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 40) {
      fetchNextPage()
    }
  }

  return (
    <div ref={ref} style={{ position: 'relative', minWidth: 160 }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs rounded px-2 py-1 w-full"
        style={{ background: 'var(--bg-panel)', color: value ? 'var(--text-primary)' : 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer', outline: 'none' }}
      >
        <span className="flex-1 text-left truncate">{value || 'Select database…'}</span>
        <ChevronDown size={11} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
      </button>

      {open && (
        <div
          className="absolute z-50 rounded shadow-lg"
          style={{ top: '100%', left: 0, minWidth: '100%', marginTop: 2, background: 'var(--bg-panel)', border: '1px solid var(--border)', maxHeight: 280, display: 'flex', flexDirection: 'column' }}
        >
          <div className="flex items-center gap-1.5 px-2 py-1.5" style={{ borderBottom: '1px solid var(--border)' }}>
            <Search size={11} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input
              ref={searchRef}
              value={search}
              onChange={e => handleSearchChange(e.target.value)}
              placeholder={total ? `Search ${total} databases…` : 'Search databases…'}
              className="flex-1 text-xs bg-transparent outline-none"
              style={{ color: 'var(--text-primary)' }}
              onKeyDown={e => {
                if (e.key === 'Escape') setOpen(false)
                if (e.key === 'Enter' && allDbs.length === 1) { onChange(allDbs[0].name); setOpen(false) }
              }}
            />
            {isFetching && !isFetchingNextPage && <Loader size={11} className="animate-spin" style={{ color: 'var(--text-muted)', flexShrink: 0 }} />}
          </div>
          <div ref={listRef} style={{ overflowY: 'auto' }} onScroll={handleScroll}>
            {allDbs.length === 0 && !isFetching ? (
              <div className="px-3 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>No matches</div>
            ) : allDbs.map(db => (
              <div
                key={db.name}
                className="px-3 py-1.5 text-xs cursor-pointer truncate"
                style={{ color: 'var(--text-primary)', background: db.name === value ? 'var(--bg-hover)' : 'transparent' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                onMouseLeave={e => (e.currentTarget.style.background = db.name === value ? 'var(--bg-hover)' : 'transparent')}
                onClick={() => { onChange(db.name); setOpen(false) }}
              >
                {db.name}
              </div>
            ))}
            {isFetchingNextPage && (
              <div className="px-3 py-2 text-xs flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
                <Loader size={11} className="animate-spin" /> Loading more…
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}


interface Props {
  tabId: string
}

export function SqlEditorPanel({ tabId }: Props) {
  const { tabs, updateTab, activeTabId, pendingInsert, setPendingInsert } = useEditorStore()
  const monacoTheme = useThemeStore(s => s.theme === 'light' ? 'vs' : 'vs-dark')
  const sqlAutocomplete = useThemeStore(s => s.sqlAutocomplete)
  const sqlDiagnostics = useThemeStore(s => s.sqlDiagnostics)
  const autoLimit = useThemeStore(s => s.autoLimit)
  const formatStyle = useThemeStore(s => s.formatStyle)
  const { setName, setDescription } = useQueryNamesStore()
  const tab = tabs.find(t => t.id === tabId)
  const queryClient = useQueryClient()
  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null)
  const monaco = useMonaco()

  const [explainPlanType, setExplainPlanType] = useState<ExplainPlanType>('LOGICAL')
  const [explainDropdownOpen, setExplainDropdownOpen] = useState(false)
  const [isExplaining, setIsExplaining] = useState(false)
  const explainDropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!explainDropdownOpen) return
    const close = (e: MouseEvent) => {
      if (explainDropdownRef.current && !explainDropdownRef.current.contains(e.target as Node))
        setExplainDropdownOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [explainDropdownOpen])

  // Register/unregister completion provider based on setting
  useEffect(() => {
    if (!monaco) return
    if (sqlAutocomplete) {
      registerSqlCompletion(monaco)
    } else {
      unregisterSqlCompletion()
    }
  }, [monaco, sqlAutocomplete])

  // Keep the completion provider's active database in sync with this tab
  useEffect(() => {
    if (tabId === activeTabId && tab?.database) {
      setActiveDatabase(tab.database)
    }
  }, [tabId, activeTabId, tab?.database])

  const handleEditorMount: OnMount = (editor) => {
    editorRef.current = editor
    if (monaco && sqlDiagnostics) registerSqlDiagnostics(monaco, editor)

    // Expose the editor instance for E2E tests (MSW dev/test mode only).
    if (import.meta.env.VITE_ENABLE_MSW === 'true') {
      ;(window as unknown as Record<string, unknown>).__argus_editor = editor
    }

    // Highest-priority Space override: intercept at the keydown event level,
    // BEFORE Monaco's command/keybinding service routes the event to whatever
    // action might consume it (acceptSelectedSuggestion, snippet jump, inline
    // suggestion accept, parameter hint cycle, etc.). This is the only way to
    // be absolutely certain that an unmodified Space always inserts a literal
    // space character into the editor — addCommand registers at the LOWEST
    // priority and is overridden by context-bound actions like
    // suggestWidgetVisible → acceptSelectedSuggestion.
    editor.onKeyDown((e) => {
      const isPlainSpace =
        e.code === 'Space' &&
        !e.altKey &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.shiftKey
      if (!isPlainSpace) return
      e.preventDefault()
      e.stopPropagation()
      // Close the suggest widget so it doesn't reappear on the same character
      editor.trigger('keyboard', 'hideSuggestWidget', {})
      editor.trigger('keyboard', 'type', { text: ' ' })
    })
  }

  // Enable/disable diagnostics when setting changes
  useEffect(() => {
    if (!monaco || !editorRef.current) return
    if (sqlDiagnostics) {
      registerSqlDiagnostics(monaco, editorRef.current)
    } else {
      unregisterSqlDiagnostics(monaco, editorRef.current)
    }
  }, [monaco, sqlDiagnostics])

  // Insert text at cursor when this is the active tab and a pendingInsert is queued
  useEffect(() => {
    if (tabId !== activeTabId || !pendingInsert || !editorRef.current) return
    const editor = editorRef.current
    const selection = editor.getSelection()
    const model = editor.getModel()
    if (!model) return
    const pos = selection
      ? { lineNumber: selection.endLineNumber, column: selection.endColumn }
      : { lineNumber: 1, column: 1 }
    const range = { startLineNumber: pos.lineNumber, startColumn: pos.column, endLineNumber: pos.lineNumber, endColumn: pos.column }
    editor.executeEdits('navigator-insert', [{ range, text: pendingInsert, forceMoveMarkers: true }])
    editor.focus()
    setPendingInsert(null)
  }, [pendingInsert, activeTabId, tabId, setPendingInsert])

  const handleRun = async () => {
    if (!tab?.database || !tab?.sql.trim()) return

    // Use selected text if there's a non-empty selection, else full SQL
    const editor = editorRef.current
    const selection = editor?.getSelection()
    const selectedText = (selection && !selection.isEmpty())
      ? editor?.getModel()?.getValueInRange(selection)?.trim()
      : undefined
    const sqlToRun = selectedText || tab.sql

    const statements = splitSqlStatements(sqlToRun)
    if (statements.length === 0) return

    if (statements.length === 1) {
      // Single query — original path
      updateTab(tabId, {
        isLoading: true,
        queryExecutionId: undefined,
        queryExecutions: undefined,
        queryState: 'RUNNING',
        queryError: undefined,
        limitApplied: false,
        activeResultIdx: undefined,
      })
      try {
        const data = await api.executeQuery({ sql: statements[0], database: tab.database, auto_limit: autoLimit > 0 ? autoLimit : undefined })
        updateTab(tabId, { queryExecutionId: data.query_execution_id, limitApplied: data.limit_applied })
        if (tab.title) setName(data.query_execution_id, tab.title)
        const comment = extractSqlComment(sqlToRun)
        if (comment) setDescription(data.query_execution_id, comment)
        const poll = async () => {
          const detail = await api.getQuery(data.query_execution_id)
          const state = detail.status.state
          updateTab(tabId, { queryState: state })
          if (state === 'RUNNING' || state === 'QUEUED') {
            setTimeout(poll, 1500)
          } else {
            updateTab(tabId, {
              isLoading: false,
              queryError: state === 'FAILED' ? (detail.status.state_change_reason ?? 'Query failed') : undefined,
            })
            if (state === 'SUCCEEDED') {
              queryClient.invalidateQueries({ queryKey: ['queryHistory'] })
              queryClient.invalidateQueries({ queryKey: ['tables'] })
              queryClient.invalidateQueries({ queryKey: ['table'] })
              queryClient.invalidateQueries({ queryKey: ['queryResults', data.query_execution_id] })
            }
          }
        }
        poll()
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to submit query'
        updateTab(tabId, { isLoading: false, queryState: 'FAILED', queryError: msg })
      }
      return
    }

    // Multiple queries — fire all in parallel
    updateTab(tabId, {
      isLoading: true,
      queryExecutionId: undefined,
      queryState: 'RUNNING',
      queryError: undefined,
      limitApplied: false,
      activeResultIdx: 0,
      queryExecutions: statements.map(() => ({ id: '', state: 'QUEUED' })),
    })

    const submitted = await Promise.allSettled(
      statements.map(sql => api.executeQuery({ sql, database: tab.database, auto_limit: autoLimit > 0 ? autoLimit : undefined }))
    )

    const initialExecs = submitted.map((r, i) =>
      r.status === 'fulfilled'
        ? { id: r.value.query_execution_id, state: 'RUNNING', limitApplied: r.value.limit_applied }
        : { id: `err-${i}`, state: 'FAILED', error: 'Failed to submit' }
    )
    useEditorStore.getState().updateTab(tabId, { queryExecutions: initialExecs })

    const checkAllDone = () => {
      const t = useEditorStore.getState().tabs.find(x => x.id === tabId)
      if (!t?.queryExecutions) return
      const allDone = t.queryExecutions.every(e => e.state !== 'RUNNING' && e.state !== 'QUEUED')
      if (allDone) {
        useEditorStore.getState().updateTab(tabId, { isLoading: false })
        queryClient.invalidateQueries({ queryKey: ['queryHistory'] })
      }
    }

    initialExecs.forEach((exec, idx) => {
      if (exec.state === 'FAILED') { checkAllDone(); return }

      const pollOne = async () => {
        try {
          const detail = await api.getQuery(exec.id)
          const state = detail.status.state
          const t = useEditorStore.getState().tabs.find(x => x.id === tabId)
          if (!t) return
          useEditorStore.getState().updateTab(tabId, {
            queryExecutions: t.queryExecutions?.map((e, i) =>
              i === idx ? { ...e, state, error: state === 'FAILED' ? (detail.status.state_change_reason ?? 'Query failed') : undefined } : e
            ),
          })
          if (state === 'RUNNING' || state === 'QUEUED') {
            setTimeout(pollOne, 1500)
          } else {
            if (state === 'SUCCEEDED') queryClient.invalidateQueries({ queryKey: ['queryResults', exec.id] })
            checkAllDone()
          }
        } catch {
          const t = useEditorStore.getState().tabs.find(x => x.id === tabId)
          if (!t) return
          useEditorStore.getState().updateTab(tabId, {
            queryExecutions: t.queryExecutions?.map((e, i) => i === idx ? { ...e, state: 'FAILED', error: 'Poll error' } : e),
          })
          checkAllDone()
        }
      }
      pollOne()
    })
  }

  // Auto-run query when a tab opens with pendingRun: true (e.g., "Select top 100 rows")
  useEffect(() => {
    if (tabId !== activeTabId || !tab?.pendingRun) return
    updateTab(tabId, { pendingRun: false })
    handleRun()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabId, activeTabId, tab?.pendingRun])

  const handleCancel = useCallback(async (queryId: string) => {
    try {
      await api.cancelQuery(queryId)
    } catch { /* ignore */ }
    // Update state immediately in store; poll will confirm
    const t = useEditorStore.getState().tabs.find(x => x.id === tabId)
    if (!t) return
    if (t.queryExecutions) {
      updateTab(tabId, {
        queryExecutions: t.queryExecutions.map(e => e.id === queryId ? { ...e, state: 'CANCELLED' } : e),
        isLoading: t.queryExecutions.every(e => e.id === queryId || e.state === 'SUCCEEDED' || e.state === 'FAILED' || e.state === 'CANCELLED') ? false : t.isLoading,
      })
    } else {
      updateTab(tabId, { queryState: 'CANCELLED', isLoading: false })
    }
  }, [tabId, updateTab])

  const handleFormat = useCallback(() => {
    if (!tab?.sql.trim()) return
    try {
      const formatted = applyFormatStyle(tab.sql, formatStyle, { linesBetweenQueries: 2 })
      updateTab(tabId, { sql: formatted })
      editorRef.current?.setValue(formatted)
    } catch {
      // If formatter fails (e.g. incomplete SQL), leave as-is
    }
  }, [tab?.sql, tabId, updateTab, formatStyle])

  const handleExplain = useCallback(async (planType: ExplainPlanType) => {
    if (!tab?.database || !tab.sql.trim()) return
    setExplainPlanType(planType)
    setExplainDropdownOpen(false)
    setIsExplaining(true)
    const openPlanTab = (body: string, label: string) => {
      useEditorStore.getState().openTab({
        title: `${label} (${planType}): ${tab.database}`,
        sql: body,
        database: tab.database,
      })
    }
    try {
      const data = await api.explainQuery({ sql: tab.sql, database: tab.database, plan_type: planType })
      const poll = async () => {
        try {
          const detail = await api.getQuery(data.query_execution_id)
          const state = detail.status.state
          if (state === 'RUNNING' || state === 'QUEUED') {
            setTimeout(poll, 1500)
            return
          }
          setIsExplaining(false)
          if (state === 'SUCCEEDED') {
            const results = await api.getQueryResults(data.query_execution_id, 5000)
            // Athena returns the plan as one row per line in column 0
            const planText = results.rows.map(r => r[0] ?? '').join('\n')
            openPlanTab(planText || '(empty plan returned)', 'Plan')
          } else {
            const reason = detail.status.state_change_reason ?? `Query ${state}`
            openPlanTab(`-- EXPLAIN ${planType} failed (${state})\n-- ${reason}`, 'Plan error')
          }
        } catch (err) {
          setIsExplaining(false)
          const msg = err instanceof Error ? err.message : String(err)
          openPlanTab(`-- EXPLAIN ${planType} failed while fetching results\n-- ${msg}`, 'Plan error')
        }
      }
      poll()
    } catch (err) {
      setIsExplaining(false)
      const msg = err instanceof Error ? err.message : String(err)
      openPlanTab(`-- EXPLAIN ${planType} submission failed\n-- ${msg}`, 'Plan error')
    }
  }, [tab?.database, tab?.sql])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'Enter') handleRun()
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') { e.preventDefault(); handleFormat() }
  }

  if (!tab) return null

  const stateColor: Record<string, string> = {
    SUCCEEDED: 'var(--success)',
    FAILED: 'var(--error)',
    RUNNING: 'var(--accent)',
    QUEUED: 'var(--warning)',
  }

  return (
    <div className="flex flex-col h-full" onKeyDown={handleKeyDown}>
      <div
        className="flex items-center gap-2 px-3 py-1.5 shrink-0"
        style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}
      >
        <DatabasePicker
          value={tab.database}
          onChange={v => updateTab(tabId, { database: v, title: v || 'Query' })}
        />

        <button
          onClick={handleRun}
          disabled={!tab.database || !tab.sql.trim() || tab.isLoading}
          className="flex items-center gap-1.5 px-3 py-1 rounded text-xs transition-opacity"
          style={{
            background: 'var(--accent)',
            color: 'var(--bg-primary)',
            border: 'none',
            cursor: tab.isLoading ? 'not-allowed' : 'pointer',
            opacity: tab.isLoading ? 0.6 : 1,
          }}
          title="Run (Ctrl+Enter)"
        >
          <Play size={11} />
          Run
        </button>

        <button
          onClick={handleFormat}
          disabled={!tab.sql.trim()}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs"
          style={{
            background: 'var(--bg-panel)',
            color: 'var(--text-muted)',
            border: '1px solid var(--border)',
            cursor: 'pointer',
            opacity: tab.sql.trim() ? 1 : 0.4,
          }}
          title="Format query (Ctrl+Shift+F)"
        >
          <WandSparkles size={11} />
          Format
        </button>

        {/* Explain button with plan type dropdown */}
        <div ref={explainDropdownRef} style={{ position: 'relative' }}>
          <div className="flex" style={{ border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
            <button
              onClick={() => handleExplain(explainPlanType)}
              disabled={!tab.database || !tab.sql.trim() || isExplaining}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs"
              style={{
                background: 'var(--bg-panel)',
                color: 'var(--text-muted)',
                border: 'none',
                cursor: (!tab.database || !tab.sql.trim() || isExplaining) ? 'not-allowed' : 'pointer',
                opacity: (!tab.database || !tab.sql.trim() || isExplaining) ? 0.4 : 1,
              }}
              title={`Explain query (${explainPlanType})`}
            >
              {isExplaining ? <Loader size={11} className="animate-spin" /> : <FileSearch size={11} />}
              Explain
            </button>
            <button
              onClick={() => setExplainDropdownOpen(o => !o)}
              disabled={!tab.database || !tab.sql.trim() || isExplaining}
              className="flex items-center px-1 py-1 text-xs"
              style={{
                background: 'var(--bg-panel)',
                color: 'var(--text-muted)',
                borderLeft: '1px solid var(--border)',
                cursor: (!tab.database || !tab.sql.trim() || isExplaining) ? 'not-allowed' : 'pointer',
                opacity: (!tab.database || !tab.sql.trim() || isExplaining) ? 0.4 : 1,
              }}
              title="Select explain type"
            >
              <ChevronDown size={10} />
            </button>
          </div>
          {explainDropdownOpen && (
            <div
              className="absolute z-50 rounded shadow-lg"
              style={{ top: '100%', left: 0, marginTop: 2, background: 'var(--bg-panel)', border: '1px solid var(--border)', minWidth: 160 }}
            >
              {(['LOGICAL', 'DISTRIBUTED', 'IO', 'ANALYZE'] as const).map(type => (
                <button
                  key={type}
                  onClick={() => handleExplain(type)}
                  className="flex flex-col w-full px-3 py-2 text-left"
                  style={{
                    background: explainPlanType === type ? 'var(--bg-hover)' : 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--text-primary)',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = explainPlanType === type ? 'var(--bg-hover)' : 'transparent')}
                >
                  <span className="text-xs font-medium">{type}</span>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {type === 'LOGICAL' && 'Logical query plan tree'}
                    {type === 'DISTRIBUTED' && 'Distributed execution plan'}
                    {type === 'IO' && 'I/O cost and statistics'}
                    {type === 'ANALYZE' && 'Actual runtime stats (runs query)'}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* State badge — aggregate for multi-query */}
        {tab.queryExecutions ? (() => {
          const execs = tab.queryExecutions
          const failed = execs.filter(e => e.state === 'FAILED').length
          const running = execs.filter(e => e.state === 'RUNNING' || e.state === 'QUEUED').length
          const succeeded = execs.filter(e => e.state === 'SUCCEEDED').length
          const aggState = running > 0 ? 'RUNNING' : failed > 0 ? 'FAILED' : 'SUCCEEDED'
          const label = running > 0
            ? `RUNNING (${succeeded + failed}/${execs.length})`
            : `${aggState} (${execs.length})`
          return <span className="text-xs font-medium" style={{ color: stateColor[aggState] ?? 'var(--text-muted)' }}>● {label}</span>
        })() : tab.queryState ? (
          <span className="text-xs font-medium" style={{ color: stateColor[tab.queryState] ?? 'var(--text-muted)' }}>
            ● {tab.queryState}
          </span>
        ) : null}
      </div>

      <Allotment vertical defaultSizes={[300, 250]}>
        <Allotment.Pane minSize={80}>
          <Editor
            language="sql"
            theme={monacoTheme}
            value={tab.sql}
            onMount={handleEditorMount}
            onChange={val => { if (val !== undefined && val !== tab.sql) updateTab(tabId, { sql: val }) }}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              tabSize: 2,
              renderLineHighlight: 'line',
              quickSuggestions: sqlAutocomplete ? { other: true, comments: false, strings: false } : false,
              suggestOnTriggerCharacters: sqlAutocomplete,
              parameterHints: { enabled: sqlAutocomplete },
              // Spacebar must always insert a literal space, never accept the
              // highlighted completion. Monaco's default treats space as a
              // commit character which made typing inside SQL feel broken
              // (especially after keywords like SELECT, FROM).
              acceptSuggestionOnCommitCharacter: false,
              acceptSuggestionOnEnter: 'on',
              tabCompletion: 'off',
              inlineSuggest: { enabled: false },
              snippetSuggestions: 'none',
            }}
          />
        </Allotment.Pane>

        <Allotment.Pane minSize={60}>
          {tab.queryExecutions && tab.queryExecutions.length > 0 ? (
            <div className="flex flex-col h-full" style={{ background: 'var(--bg-panel)' }}>
              {/* Result tabs */}
              <div
                className="flex items-center gap-0 shrink-0 overflow-x-auto"
                style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}
              >
                {tab.queryExecutions.map((exec, idx) => {
                  const active = (tab.activeResultIdx ?? 0) === idx
                  const color = stateColor[exec.state] ?? 'var(--text-muted)'
                  return (
                    <button
                      key={idx}
                      onClick={() => updateTab(tabId, { activeResultIdx: idx })}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs shrink-0"
                      style={{
                        background: active ? 'var(--bg-panel)' : 'transparent',
                        color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                        border: 'none',
                        borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
                        cursor: 'pointer',
                        fontWeight: active ? 600 : 400,
                      }}
                    >
                      <span style={{ color, fontSize: 8 }}>●</span>
                      Result {idx + 1}
                    </button>
                  )
                })}
              </div>
              {/* Active result grid */}
              {(() => {
                const exec = tab.queryExecutions[tab.activeResultIdx ?? 0]
                if (!exec) return null
                if (exec.state === 'FAILED') {
                  return (
                    <div className="flex flex-col gap-2 p-4 overflow-auto" style={{ flex: 1 }}>
                      <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--error)' }}>
                        <span>✕</span> Query {(tab.activeResultIdx ?? 0) + 1} Failed
                      </div>
                      <pre className="text-xs rounded p-3 whitespace-pre-wrap" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--error)', fontFamily: 'monospace' }}>
                        {exec.error}
                      </pre>
                    </div>
                  )
                }
                if (exec.id && exec.state !== 'QUEUED') {
                  return <ResultsGrid
                    queryExecutionId={exec.id}
                    queryState={exec.state}
                    limitApplied={exec.limitApplied}
                    autoLimit={autoLimit}
                    tabId={tabId}
                    queryIndex={tab.activeResultIdx ?? 0}
                    onCancel={(exec.state === 'RUNNING' || exec.state === 'QUEUED') ? () => handleCancel(exec.id) : undefined}
                  />
                }
                return (
                  <div className="flex items-center justify-center h-full text-xs" style={{ color: 'var(--text-muted)' }}>
                    Waiting…
                  </div>
                )
              })()}
            </div>
          ) : tab.queryExecutionId ? (
            <ResultsGrid
              queryExecutionId={tab.queryExecutionId}
              queryState={tab.queryState}
              queryError={tab.queryError}
              limitApplied={tab.limitApplied}
              autoLimit={autoLimit}
              tabId={tabId}
              onCancel={(tab.queryState === 'RUNNING' || tab.queryState === 'QUEUED') && tab.queryExecutionId ? () => handleCancel(tab.queryExecutionId!) : undefined}
            />
          ) : tab.queryError ? (
            <div className="flex flex-col gap-2 p-4 h-full overflow-auto" style={{ background: 'var(--bg-panel)' }}>
              <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--error)' }}>
                <span>✕</span> Query Failed
              </div>
              <pre
                className="text-xs rounded p-3 whitespace-pre-wrap"
                style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--error)', fontFamily: 'monospace' }}
              >
                {tab.queryError}
              </pre>
            </div>
          ) : null}
        </Allotment.Pane>
      </Allotment>
    </div>
  )
}
