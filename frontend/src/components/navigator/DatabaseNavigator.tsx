import { useState, useRef, useCallback } from 'react'
import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format as formatSql } from 'sql-formatter'
import { api } from '../../api/client'
import { useEditorStore } from '../../stores/editorStore'
import { useUIStore } from '../../stores/uiStore'
import { useThemeStore } from '../../stores/themeStore'
import {
  Database, Table, Columns, ChevronRight, ChevronDown,
  Search, RefreshCw, GitBranch, Layers, MoreHorizontal,
  Play, ClipboardCopy, MousePointerClick, AlignLeft, Lock, ArrowRightLeft, Plus, Eye, Loader
} from 'lucide-react'
import type { DatabaseItem } from '../../api/client'
import { NavigatorContextMenu, type MenuAction } from './NavigatorContextMenu'

interface MenuState {
  x: number
  y: number
  actions: MenuAction[]
}

interface AssignModalState {
  database: string
  currentWorkgroup: string | null
}

const UNASSIGNED = 'Unassigned'
const DEFAULT_DB = 'default'
const PAGE_LIMIT = 50

function buildSelectTop100(qualifiedName: string, formatStyle: import('../../stores/themeStore').FormatStyle = 'standard') {
  const raw = `SELECT * FROM ${qualifiedName} LIMIT 100`
  try {
    return formatSql(raw, { language: 'trino', tabWidth: 2, keywordCase: 'upper', indentStyle: formatStyle }) + ';'
  } catch {
    return `SELECT *\nFROM ${qualifiedName}\nLIMIT 100;`
  }
}

export function DatabaseNavigator() {
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [expandedWorkgroups, setExpandedWorkgroups] = useState<Set<string>>(new Set())
  const [expandedDbs, setExpandedDbs] = useState<Set<string>>(new Set())
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set())
  const [menu, setMenu] = useState<MenuState | null>(null)
  const [assignModal, setAssignModal] = useState<AssignModalState | null>(null)
  const [showCreateWorkgroup, setShowCreateWorkgroup] = useState(false)
  const addTab = useEditorStore(s => s.addTab)
  const openTab = useEditorStore(s => s.openTab)
  const openErDiagramTab = useEditorStore(s => s.openErDiagramTab)
  const setPendingInsert = useEditorStore(s => s.setPendingInsert)
  const { setSelectedDatabase, setSelectedTable } = useUIStore()
  const { showInformationSchema, formatStyle } = useThemeStore()
  const queryClient = useQueryClient()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearchChange = useCallback((value: string) => {
    setSearchTerm(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedSearch(value), 300)
  }, [])

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['databases', debouncedSearch],
    queryFn: ({ pageParam = 0 }) =>
      api.listDatabases({ search: debouncedSearch, limit: PAGE_LIMIT, offset: pageParam as number }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    staleTime: 30000,
  })

  const allDbs = data?.pages.flatMap(p => p.items) ?? []
  const totalLoaded = allDbs.length
  const totalAvailable = data?.pages[0]?.total ?? 0

  const assignMutation = useMutation({
    mutationFn: ({ database, workgroup }: { database: string; workgroup: string }) =>
      api.assignDatabase(database, workgroup),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['databases'] })
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
  })

  const unassignMutation = useMutation({
    mutationFn: (database: string) => api.unassignDatabase(database),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['databases'] })
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
  })

  const groups = allDbs.reduce<Record<string, DatabaseItem[]>>((acc, db) => {
    const key = db.workgroup ?? UNASSIGNED
    ;(acc[key] ??= []).push(db)
    return acc
  }, {})

  const sortedGroups = Object.entries(groups).sort(([a], [b]) =>
    a === UNASSIGNED ? 1 : b === UNASSIGNED ? -1 : a.localeCompare(b)
  )

  const toggleWorkgroup = (name: string) => {
    setExpandedWorkgroups(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  const toggleDb = (name: string) => {
    setExpandedDbs(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
    setSelectedDatabase(name)
  }

  const toggleTable = (key: string) => {
    setExpandedTables(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const openWorkgroupMenu = (e: React.MouseEvent, workgroup: string) => {
    e.stopPropagation()
    setMenu({
      x: e.clientX,
      y: e.clientY,
      actions: [
        {
          label: 'Copy workgroup name',
          icon: <ClipboardCopy size={13} />,
          onClick: () => navigator.clipboard.writeText(workgroup),
        },
      ],
    })
  }

  const openDbMenu = (e: React.MouseEvent, db: DatabaseItem) => {
    e.stopPropagation()
    const isUnassigned = !db.workgroup
    const isDefault = db.name === DEFAULT_DB
    const actions: MenuAction[] = []

    if (!isUnassigned || isDefault) {
      actions.push(
        { label: 'Open new tab', icon: <AlignLeft size={13} />, onClick: () => addTab(db.name) },
        { label: 'View ER diagram', icon: <GitBranch size={13} />, onClick: () => openErDiagramTab(db.name) },
        { separator: true, label: '', onClick: () => {} },
        { label: 'Insert name at cursor', icon: <MousePointerClick size={13} />, onClick: () => setPendingInsert(`"${db.name}"`) },
        { label: 'Copy name', icon: <ClipboardCopy size={13} />, onClick: () => navigator.clipboard.writeText(db.name) },
      )
      if (!isDefault) {
        actions.push(
          { separator: true, label: '', onClick: () => {} },
          {
            label: 'Change workgroup…',
            icon: <ArrowRightLeft size={13} />,
            onClick: () => setAssignModal({ database: db.name, currentWorkgroup: db.workgroup ?? null }),
          },
          {
            label: 'Unassign workgroup',
            icon: <Lock size={13} />,
            onClick: () => unassignMutation.mutate(db.name),
          },
        )
      }
    } else {
      actions.push(
        {
          label: 'Assign to workgroup…',
          icon: <Lock size={13} />,
          onClick: () => setAssignModal({ database: db.name, currentWorkgroup: null }),
        },
        { separator: true, label: '', onClick: () => {} },
        { label: 'Copy name', icon: <ClipboardCopy size={13} />, onClick: () => navigator.clipboard.writeText(db.name) },
      )
    }

    setMenu({ x: e.clientX, y: e.clientY, actions })
  }

  const openTableMenu = (e: React.MouseEvent, dbName: string, tableName: string, dbIsUnassigned: boolean) => {
    e.stopPropagation()
    const qualifiedName = `"${dbName}"."${tableName}"`
    const actions: MenuAction[] = []

    if (!dbIsUnassigned || dbName === DEFAULT_DB) {
      actions.push({
        label: 'Select top 100 rows',
        icon: <Play size={13} />,
        onClick: () => openTab({ title: tableName, sql: buildSelectTop100(qualifiedName, formatStyle), database: dbName, pendingRun: true }),
      })
      actions.push({ separator: true, label: '', onClick: () => {} })
    }

    actions.push(
      { label: 'Insert table name at cursor', icon: <MousePointerClick size={13} />, onClick: () => setPendingInsert(`"${tableName}"`) },
      { label: 'Insert full name at cursor', icon: <MousePointerClick size={13} />, onClick: () => setPendingInsert(qualifiedName) },
      { separator: true, label: '', onClick: () => {} },
      { label: 'Copy table name', icon: <ClipboardCopy size={13} />, onClick: () => navigator.clipboard.writeText(tableName) },
      { label: 'Copy full name', icon: <ClipboardCopy size={13} />, onClick: () => navigator.clipboard.writeText(qualifiedName) },
    )

    setMenu({ x: e.clientX, y: e.clientY, actions })
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-panel)', borderRight: '1px solid var(--border)' }}>
      <div className="px-2 py-2 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded" style={{ background: 'var(--bg-secondary)' }}>
          <Search size={12} style={{ color: 'var(--text-muted)' }} />
          <input
            className="flex-1 text-xs bg-transparent outline-none"
            style={{ color: 'var(--text-primary)' }}
            placeholder="Search databases..."
            value={searchTerm}
            onChange={e => handleSearchChange(e.target.value)}
          />
          <button
            onClick={() => {
              refetch()
              queryClient.invalidateQueries({ queryKey: ['tables'] })
              queryClient.invalidateQueries({ queryKey: ['table'] })
            }}
            title="Refresh"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} style={{ color: 'var(--text-muted)' }} />
          </button>
          <button onClick={() => setShowCreateWorkgroup(true)} title="New workgroup" style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0 }}>
            <Plus size={12} style={{ color: 'var(--text-muted)' }} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto scrollbar-thin py-1">
        {showInformationSchema && (
          <InformationSchemaNode
            onOpenTab={sql => openTab({ title: 'information_schema', sql, database: 'information_schema', pendingRun: true })}
            onInsert={setPendingInsert}
          />
        )}
        {sortedGroups.map(([workgroup, dbs]) => (
          <WorkgroupRow
            key={workgroup}
            workgroup={workgroup}
            dbs={dbs}
            expanded={expandedWorkgroups.has(workgroup)}
            expandedDbs={expandedDbs}
            expandedTables={expandedTables}
            onToggle={() => toggleWorkgroup(workgroup)}
            onToggleDb={toggleDb}
            onToggleTable={toggleTable}
            onShowEr={(dbName) => openErDiagramTab(dbName)}
            onSelectTable={setSelectedTable}
            onDbMenu={openDbMenu}
            onTableMenu={openTableMenu}
            onWorkgroupMenu={openWorkgroupMenu}
          />
        ))}

        {hasNextPage && (
          <button
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            className="w-full text-xs flex items-center justify-center gap-1.5 py-2"
            style={{ background: 'transparent', border: 'none', cursor: isFetchingNextPage ? 'default' : 'pointer', color: 'var(--text-muted)' }}
          >
            {isFetchingNextPage
              ? <><Loader size={11} className="animate-spin" /> Loading…</>
              : `Load more (${totalLoaded} of ${totalAvailable})`}
          </button>
        )}
      </div>

      <div className="px-2 py-2 shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {totalLoaded}{totalAvailable > totalLoaded ? ` of ${totalAvailable}` : ''} database{totalLoaded !== 1 ? 's' : ''} · {sortedGroups.length} group{sortedGroups.length !== 1 ? 's' : ''}
        </div>
      </div>

      {menu && (
        <NavigatorContextMenu
          x={menu.x}
          y={menu.y}
          actions={menu.actions}
          onClose={() => setMenu(null)}
        />
      )}

      {assignModal && (
        <AssignWorkgroupModal
          database={assignModal.database}
          currentWorkgroup={assignModal.currentWorkgroup}
          onAssign={(wg) => { assignMutation.mutate({ database: assignModal.database, workgroup: wg }); setAssignModal(null) }}
          onUnassign={() => { unassignMutation.mutate(assignModal.database); setAssignModal(null) }}
          onClose={() => setAssignModal(null)}
        />
      )}

      {showCreateWorkgroup && (
        <CreateWorkgroupModal
          onClose={() => setShowCreateWorkgroup(false)}
        />
      )}
    </div>
  )
}

interface WorkgroupRowProps {
  workgroup: string
  dbs: DatabaseItem[]
  expanded: boolean
  expandedDbs: Set<string>
  expandedTables: Set<string>
  onToggle: () => void
  onToggleDb: (name: string) => void
  onToggleTable: (key: string) => void
  onShowEr: (dbName: string) => void
  onSelectTable: (table: string | null) => void
  onDbMenu: (e: React.MouseEvent, db: DatabaseItem) => void
  onTableMenu: (e: React.MouseEvent, dbName: string, tableName: string, dbIsUnassigned: boolean) => void
  onWorkgroupMenu: (e: React.MouseEvent, workgroup: string) => void
}

function WorkgroupRow({
  workgroup, dbs, expanded, expandedDbs, expandedTables,
  onToggle, onToggleDb, onToggleTable, onShowEr,
  onSelectTable, onDbMenu, onTableMenu, onWorkgroupMenu,
}: WorkgroupRowProps) {
  const [hovered, setHovered] = useState(false)
  const isUnassigned = workgroup === UNASSIGNED

  return (
    <div>
      <div
        className="flex items-center gap-1.5 px-2 py-1 cursor-pointer text-xs select-none"
        style={{ color: isUnassigned ? 'var(--warning)' : 'var(--text-muted)', background: hovered ? 'var(--bg-hover)' : 'transparent' }}
        onClick={onToggle}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {isUnassigned
          ? <Lock size={12} style={{ color: 'var(--warning)', opacity: 0.8 }} />
          : <Layers size={13} style={{ color: 'var(--accent)', opacity: 0.7 }} />}
        <span className="font-semibold uppercase tracking-wide truncate" style={{ fontSize: 10 }}>
          {workgroup}
        </span>
        <span style={{ fontSize: 10 }}>{dbs.length}</span>
        {hovered && !isUnassigned && (
          <button
            onClick={e => onWorkgroupMenu(e, workgroup)}
            title="More options"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 2px', lineHeight: 1, borderRadius: 3, marginLeft: 'auto' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <MoreHorizontal size={13} />
          </button>
        )}
        {(!hovered || isUnassigned) && <span className="ml-auto" />}
      </div>

      {expanded && (
        <div className="ml-2">
          {dbs.map(db => (
            <DatabaseNode
              key={db.name}
              db={db}
              isUnassigned={isUnassigned}
              expanded={expandedDbs.has(db.name)}
              expandedTables={expandedTables}
              onToggle={() => onToggleDb(db.name)}
              onToggleTable={onToggleTable}
              onShowEr={onShowEr}
              onSelectTable={onSelectTable}
              onDbMenu={onDbMenu}
              onTableMenu={onTableMenu}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface DatabaseNodeProps {
  db: DatabaseItem
  isUnassigned: boolean
  expanded: boolean
  expandedTables: Set<string>
  onToggle: () => void
  onToggleTable: (key: string) => void
  onShowEr: (dbName: string) => void
  onSelectTable: (table: string | null) => void
  onDbMenu: (e: React.MouseEvent, db: DatabaseItem) => void
  onTableMenu: (e: React.MouseEvent, dbName: string, tableName: string, dbIsUnassigned: boolean) => void
}

function DatabaseNode({ db, isUnassigned, expanded, expandedTables, onToggle, onToggleTable, onSelectTable, onDbMenu, onTableMenu }: DatabaseNodeProps) {
  const [hovered, setHovered] = useState(false)
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['tables']))

  const isDefault = db.name === DEFAULT_DB
  // The "default" AWS database is always queryable via the primary workgroup
  const effectivelyUnassigned = isUnassigned && !isDefault

  const { data: tables, isError, error } = useQuery({
    queryKey: ['tables', db.name],
    queryFn: () => api.listTables(db.name),
    enabled: expanded,
    staleTime: 30000,
    retry: 1,
  })

  const toggleFolder = (folder: string) =>
    setExpandedFolders(prev => {
      const next = new Set(prev)
      next.has(folder) ? next.delete(folder) : next.add(folder)
      return next
    })

  const tableItems = (tables ?? []).filter(t => t.table_type !== 'VIRTUAL_VIEW')
  const viewItems  = (tables ?? []).filter(t => t.table_type === 'VIRTUAL_VIEW')

  return (
    <div>
      <div
        className="flex items-center gap-1 px-2 py-1 cursor-pointer text-xs rounded mx-1"
        style={{
          color: effectivelyUnassigned ? 'var(--text-muted)' : 'var(--text-primary)',
          background: hovered ? 'var(--bg-hover)' : 'transparent',
          opacity: effectivelyUnassigned ? 0.7 : 1,
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={onToggle}
        title={effectivelyUnassigned ? 'Unassigned — assign to a workgroup to query' : (db.description ?? db.name)}
      >
        {expanded ? <ChevronDown size={12} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={12} style={{ color: 'var(--text-muted)' }} />}
        {effectivelyUnassigned
          ? <Lock size={12} style={{ color: 'var(--warning)' }} />
          : <Database size={13} style={{ color: 'var(--accent)' }} />}
        <span className="flex-1 truncate">{db.name}</span>
        {hovered && (
          <button
            onClick={e => onDbMenu(e, db)}
            title="More options"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 2px', lineHeight: 1, borderRadius: 3 }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <MoreHorizontal size={13} />
          </button>
        )}
      </div>
      {expanded && isError && (
        <div className="ml-4 px-2 py-1 text-xs" style={{ color: 'var(--error)' }}
          title={(error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? String(error)}>
          ⚠ Failed to load tables
        </div>
      )}
      {expanded && tables && (
        <div className="ml-4">
          {/* Tables folder */}
          <FolderRow
            label="Tables"
            count={tableItems.length}
            expanded={expandedFolders.has('tables')}
            onToggle={() => toggleFolder('tables')}
          />
          {expandedFolders.has('tables') && (
            <div className="ml-4">
              {tableItems.map(t => (
                <TableNode
                  key={t.name}
                  dbName={db.name}
                  dbIsUnassigned={effectivelyUnassigned}
                  table={t}
                  isView={false}
                  expanded={expandedTables.has(`${db.name}.${t.name}`)}
                  onToggle={() => { onToggleTable(`${db.name}.${t.name}`); onSelectTable(t.name) }}
                  onTableMenu={onTableMenu}
                />
              ))}
            </div>
          )}

          {/* Views folder — only shown if there are any */}
          {viewItems.length > 0 && (
            <>
              <FolderRow
                label="Views"
                count={viewItems.length}
                expanded={expandedFolders.has('views')}
                onToggle={() => toggleFolder('views')}
              />
              {expandedFolders.has('views') && (
                <div className="ml-4">
                  {viewItems.map(t => (
                    <TableNode
                      key={t.name}
                      dbName={db.name}
                      dbIsUnassigned={effectivelyUnassigned}
                      table={t}
                      isView={true}
                      expanded={expandedTables.has(`${db.name}.${t.name}`)}
                      onToggle={() => { onToggleTable(`${db.name}.${t.name}`); onSelectTable(t.name) }}
                      onTableMenu={onTableMenu}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function FolderRow({ label, count, expanded, onToggle }: {
  label: string
  count: number
  expanded: boolean
  onToggle: () => void
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      className="flex items-center gap-1 px-2 py-0.5 cursor-pointer text-xs rounded mx-1 select-none"
      style={{ color: 'var(--text-muted)', background: hovered ? 'var(--bg-hover)' : 'transparent' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onToggle}
    >
      {expanded
        ? <ChevronDown size={11} style={{ color: 'var(--text-muted)' }} />
        : <ChevronRight size={11} style={{ color: 'var(--text-muted)' }} />}
      <Layers size={11} style={{ color: 'var(--text-muted)' }} />
      <span>{label}</span>
      <span className="ml-auto opacity-50">{count}</span>
    </div>
  )
}

function TableNode({ dbName, dbIsUnassigned, table, isView, expanded, onToggle, onTableMenu }: {
  dbName: string
  dbIsUnassigned: boolean
  table: { name: string; table_type?: string }
  isView: boolean
  expanded: boolean
  onToggle: () => void
  onTableMenu: (e: React.MouseEvent, dbName: string, tableName: string, dbIsUnassigned: boolean) => void
}) {
  const [hovered, setHovered] = useState(false)

  const { data: tableDetail } = useQuery({
    queryKey: ['table', dbName, table.name],
    queryFn: () => api.getTable(dbName, table.name),
    enabled: expanded,
    staleTime: 60000,
  })

  return (
    <div>
      <div
        className="flex items-center gap-1 px-2 py-0.5 cursor-pointer text-xs rounded mx-1"
        style={{ color: 'var(--text-primary)', background: hovered ? 'var(--bg-hover)' : 'transparent', opacity: dbIsUnassigned ? 0.6 : 1 }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={onToggle}
      >
        {expanded ? <ChevronDown size={11} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={11} style={{ color: 'var(--text-muted)' }} />}
        {isView
          ? <Eye size={12} style={{ color: dbIsUnassigned ? 'var(--text-muted)' : '#a78bfa' }} />
          : <Table size={12} style={{ color: dbIsUnassigned ? 'var(--text-muted)' : 'var(--accent-hover)' }} />}
        <span className="flex-1 truncate">{table.name}</span>
        {hovered && (
          <button
            onClick={e => onTableMenu(e, dbName, table.name, dbIsUnassigned)}
            title="More options"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 2px', lineHeight: 1, borderRadius: 3 }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <MoreHorizontal size={12} />
          </button>
        )}
      </div>
      {expanded && tableDetail && (
        <div className="ml-6">
          {tableDetail.columns.map(col => (
            <div key={col.name} className="flex items-center gap-1 px-2 py-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
              <Columns size={10} />
              <span className="truncate">{col.name}</span>
              <span className="ml-auto text-xs opacity-60">{col.type}</span>
            </div>
          ))}
          {tableDetail.partition_keys.length > 0 && (
            <>
              <div className="px-2 py-0.5 text-xs font-medium" style={{ color: 'var(--warning)' }}>Partitions</div>
              {tableDetail.partition_keys.map(col => (
                <div key={col.name} className="flex items-center gap-1 px-2 py-0.5 text-xs" style={{ color: 'var(--warning)' }}>
                  <Columns size={10} />
                  <span>{col.name}</span>
                  <span className="ml-auto opacity-60">{col.type}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function InfoSchemaTableRow({ tableName, expanded, onToggle, onMenuOpen }: {
  tableName: string
  expanded: boolean
  onToggle: () => void
  onMenuOpen: (x: number, y: number) => void
}) {
  const [hovered, setHovered] = useState(false)
  const { data: tableDetail } = useQuery({
    queryKey: ['table', 'information_schema', tableName],
    queryFn: () => api.getTable('information_schema', tableName),
    enabled: expanded,
    staleTime: 300000,
  })
  return (
    <div>
      <div
        className="flex items-center gap-1 px-2 py-0.5 cursor-pointer text-xs rounded mx-1"
        style={{ color: 'var(--text-primary)', background: hovered || expanded ? 'var(--bg-hover)' : 'transparent' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={onToggle}
        onContextMenu={e => { e.preventDefault(); onMenuOpen(e.clientX, e.clientY) }}
      >
        {expanded ? <ChevronDown size={11} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={11} style={{ color: 'var(--text-muted)' }} />}
        <Eye size={12} style={{ color: '#818cf8' }} />
        <span className="flex-1 truncate">{tableName}</span>
        {hovered && (
          <button
            onClick={e => { e.stopPropagation(); onMenuOpen(e.clientX, e.clientY) }}
            title="More options"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 2px', lineHeight: 1, borderRadius: 3 }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <MoreHorizontal size={12} />
          </button>
        )}
      </div>
      {expanded && tableDetail && (
        <div className="ml-6">
          {tableDetail.columns.map(col => (
            <div key={col.name} className="flex items-center gap-1 px-2 py-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
              <Columns size={10} />
              <span className="truncate">{col.name}</span>
              <span className="ml-auto opacity-60">{col.type}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function InformationSchemaNode({ onOpenTab, onInsert }: {
  onOpenTab: (sql: string) => void
  onInsert: (text: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set())
  const [hovered, setHovered] = useState(false)
  const [menu, setMenu] = useState<{ x: number; y: number; tableName: string } | null>(null)
  const { formatStyle } = useThemeStore()

  const { data: tables, isError, isFetching } = useQuery({
    queryKey: ['tables', 'information_schema'],
    queryFn: () => api.listTables('information_schema'),
    enabled: expanded,
    staleTime: 300000, // 5 min — rarely changes
  })

  const toggleTable = (name: string) => {
    setExpandedTables(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      {/* Header row */}
      <div
        className="flex items-center gap-1.5 px-2 py-1 cursor-pointer text-xs select-none"
        style={{ color: 'var(--text-muted)', background: hovered ? 'var(--bg-hover)' : 'transparent' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => setExpanded(e => !e)}
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Database size={12} style={{ color: '#60a5fa', opacity: 0.8 }} />
        <span className="font-semibold" style={{ fontSize: 11, color: '#60a5fa', opacity: 0.9 }}>information_schema</span>
        {isFetching && <span className="ml-auto text-xs opacity-50">…</span>}
      </div>

      {expanded && (
        <div className="ml-2">
          {isError && (
            <div className="px-3 py-1 text-xs" style={{ color: 'var(--error)' }}>⚠ Failed to load</div>
          )}
          {(tables ?? []).map(t => (
            <InfoSchemaTableRow
              key={t.name}
              tableName={t.name}
              expanded={expandedTables.has(t.name)}
              onToggle={() => toggleTable(t.name)}
              onMenuOpen={(x, y) => setMenu({ x, y, tableName: t.name })}
            />
          ))}
        </div>
      )}

      {menu && (
        <NavigatorContextMenu
          x={menu.x}
          y={menu.y}
          actions={[
            {
              label: 'Select top 100 rows',
              icon: <Play size={13} />,
              onClick: () => onOpenTab(buildSelectTop100(`information_schema.${menu.tableName}`, formatStyle)),
            },
            { separator: true, label: '', onClick: () => {} },
            {
              label: 'Insert table name at cursor',
              icon: <MousePointerClick size={13} />,
              onClick: () => onInsert(`"${menu.tableName}"`),
            },
            {
              label: 'Insert full name at cursor',
              icon: <MousePointerClick size={13} />,
              onClick: () => onInsert(`information_schema.${menu.tableName}`),
            },
            {
              label: 'Copy table name',
              icon: <ClipboardCopy size={13} />,
              onClick: () => navigator.clipboard.writeText(menu.tableName),
            },
            {
              label: 'Copy full name',
              icon: <ClipboardCopy size={13} />,
              onClick: () => navigator.clipboard.writeText(`information_schema.${menu.tableName}`),
            },
          ]}
          onClose={() => setMenu(null)}
        />
      )}
    </div>
  )
}

function AssignWorkgroupModal({ database, currentWorkgroup, onAssign, onUnassign, onClose }: {
  database: string
  currentWorkgroup: string | null
  onAssign: (workgroup: string) => void
  onUnassign: () => void
  onClose: () => void
}) {
  const [selected, setSelected] = useState<string>(currentWorkgroup ?? '')
  const [search, setSearch] = useState('')
  const isUnassigning = selected === '__unassign__'

  const { data: allWorkgroups = [], isLoading } = useQuery({
    queryKey: ['workgroup-names'],
    queryFn: () => api.listWorkgroupNames(),
    staleTime: 60000,
  })

  const filtered = allWorkgroups.filter(wg =>
    wg !== 'primary' && wg.toLowerCase().includes(search.toLowerCase())
  )

  const canConfirm = isUnassigning || (!!selected && selected !== '__unassign__' && selected !== currentWorkgroup)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="rounded-lg shadow-xl flex flex-col"
        style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', width: 360, maxHeight: '70vh' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-3 shrink-0">
          <div className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
            {currentWorkgroup ? 'Change Workgroup' : 'Assign to Workgroup'}
          </div>
          <div className="text-xs mb-3 truncate" style={{ color: 'var(--text-muted)' }}>{database}</div>
          <div className="flex items-center gap-1.5 px-2 py-1.5 rounded" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
            <Search size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input
              autoFocus
              className="flex-1 text-xs bg-transparent outline-none"
              style={{ color: 'var(--text-primary)' }}
              placeholder={`Search ${allWorkgroups.length} workgroups…`}
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button onClick={() => setSearch('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, lineHeight: 1 }}>
                ✕
              </button>
            )}
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto px-5 pb-2" style={{ minHeight: 0 }}>
          {isLoading ? (
            <div className="text-xs py-4 text-center" style={{ color: 'var(--text-muted)' }}>Loading workgroups…</div>
          ) : filtered.length === 0 ? (
            <div className="text-xs py-4 text-center" style={{ color: 'var(--text-muted)' }}>No workgroups match "{search}"</div>
          ) : (
            <div className="flex flex-col gap-0.5">
              {filtered.map(wg => (
                <button
                  key={wg}
                  onClick={() => setSelected(wg)}
                  className="flex items-center gap-2 px-3 py-2 rounded text-xs text-left w-full"
                  style={{
                    background: selected === wg ? 'var(--accent)' : 'transparent',
                    color: selected === wg ? 'var(--bg-primary)' : wg === currentWorkgroup ? 'var(--text-muted)' : 'var(--text-primary)',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => { if (selected !== wg) e.currentTarget.style.background = 'var(--bg-hover)' }}
                  onMouseLeave={e => { if (selected !== wg) e.currentTarget.style.background = 'transparent' }}
                >
                  <Layers size={12} style={{ flexShrink: 0 }} />
                  <span className="flex-1 truncate">{wg}</span>
                  {wg === currentWorkgroup && <span className="text-xs opacity-60 ml-auto">current</span>}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
          {currentWorkgroup && (
            <button
              onClick={() => setSelected(isUnassigning ? (currentWorkgroup ?? '') : '__unassign__')}
              className="flex items-center gap-2 w-full px-3 py-1.5 rounded text-xs mb-2"
              style={{
                background: isUnassigning ? 'var(--bg-hover)' : 'transparent',
                color: 'var(--warning)',
                border: '1px solid ' + (isUnassigning ? 'var(--warning)' : 'var(--border)'),
                cursor: 'pointer',
              }}
            >
              <Lock size={12} />
              Unassign (uses primary workgroup)
            </button>
          )}
          <div className="flex gap-2 justify-end">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded text-xs"
              style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}
            >
              Cancel
            </button>
            <button
              onClick={() => isUnassigning ? onUnassign() : onAssign(selected)}
              disabled={!canConfirm}
              className="px-3 py-1.5 rounded text-xs"
              style={{
                background: isUnassigning ? 'var(--warning)' : 'var(--accent)',
                color: 'var(--bg-primary)',
                border: 'none',
                cursor: canConfirm ? 'pointer' : 'not-allowed',
                opacity: canConfirm ? 1 : 0.4,
              }}
            >
              {isUnassigning ? 'Unassign' : 'Assign'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function CreateWorkgroupModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [outputLocation, setOutputLocation] = useState('')
  const [engineVersion, setEngineVersion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [s3Status, setS3Status] = useState<'idle' | 'checking' | 'ok' | 'error'>('idle')
  const [s3Message, setS3Message] = useState<string | null>(null)

  const handleVerifyS3 = async () => {
    if (!outputLocation.trim()) return
    setS3Status('checking')
    setS3Message(null)
    try {
      const result = await api.validateS3Location(outputLocation.trim())
      if (result.valid) {
        setS3Status('ok')
        setS3Message(`Bucket '${result.bucket}' is accessible and writable`)
      } else {
        setS3Status('error')
        setS3Message(result.error ?? 'Location is not accessible')
      }
    } catch {
      setS3Status('error')
      setS3Message('Could not reach the server to validate')
    }
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.createWorkgroup({
        name: name.trim(),
        description: description.trim() || undefined,
        output_location: outputLocation.trim() || undefined,
        engine_version: engineVersion.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workgroup-names'] })
      queryClient.invalidateQueries({ queryKey: ['workgroups'] })
      onClose()
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create workgroup'
      setError(msg)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!name.trim()) { setError('Name is required'); return }
    createMutation.mutate()
  }

  const inputStyle = {
    width: '100%',
    background: 'var(--bg-secondary)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    padding: '6px 10px',
    fontSize: 13,
    outline: 'none',
  }

  const labelStyle = { fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, display: 'block' as const }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--bg-panel)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          width: 420,
          padding: 24,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div className="flex items-center justify-between">
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>New Workgroup</span>
          <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>✕</button>
        </div>

        <div>
          <label style={labelStyle}>Name <span style={{ color: 'var(--error)' }}>*</span></label>
          <input
            autoFocus
            style={inputStyle}
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. client-acme-prod"
          />
        </div>

        <div>
          <label style={labelStyle}>Description</label>
          <input
            style={inputStyle}
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div>
          <label style={labelStyle}>Output location (S3)</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              style={{ ...inputStyle, flex: 1 }}
              value={outputLocation}
              onChange={e => { setOutputLocation(e.target.value); setS3Status('idle'); setS3Message(null) }}
              placeholder="s3://my-bucket/athena-results/"
            />
            <button
              type="button"
              onClick={handleVerifyS3}
              disabled={!outputLocation.trim() || s3Status === 'checking'}
              style={{
                padding: '6px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                background: 'var(--bg-secondary)', color: 'var(--text-muted)',
                border: '1px solid var(--border)', whiteSpace: 'nowrap',
                opacity: !outputLocation.trim() ? 0.5 : 1,
              }}
            >
              {s3Status === 'checking' ? '…' : 'Verify'}
            </button>
          </div>
          {s3Message && (
            <div style={{
              marginTop: 5, fontSize: 11, padding: '5px 8px', borderRadius: 5,
              color: s3Status === 'ok' ? '#16a34a' : 'var(--error)',
              background: s3Status === 'ok' ? 'rgba(22,163,74,0.08)' : 'rgba(239,68,68,0.08)',
            }}>
              {s3Status === 'ok' ? '✓ ' : '✗ '}{s3Message}
            </div>
          )}
        </div>

        <div>
          <label style={labelStyle}>Engine version</label>
          <select
            style={{ ...inputStyle, cursor: 'pointer' }}
            value={engineVersion}
            onChange={e => setEngineVersion(e.target.value)}
          >
            <option value="">Default (AUTO)</option>
            <option value="Athena engine version 3">Athena engine version 3</option>
            <option value="Athena engine version 2">Athena engine version 2</option>
          </select>
        </div>

        {error && (
          <div style={{ fontSize: 12, color: 'var(--error)', background: 'rgba(239,68,68,0.08)', padding: '8px 10px', borderRadius: 6 }}>
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2" style={{ marginTop: 4 }}>
          <button
            type="button"
            onClick={onClose}
            style={{ padding: '6px 14px', borderRadius: 6, fontSize: 13, cursor: 'pointer', background: 'var(--bg-secondary)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending || !name.trim()}
            style={{
              padding: '6px 16px', borderRadius: 6, fontSize: 13, cursor: 'pointer',
              background: 'var(--accent)', color: '#fff', border: 'none',
              opacity: createMutation.isPending || !name.trim() ? 0.6 : 1,
            }}
          >
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  )
}
