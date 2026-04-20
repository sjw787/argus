import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface QueryExecution {
  id: string
  state: string
  error?: string
  limitApplied?: boolean
  reused?: boolean
}

export interface EditorTab {
  id: string
  title: string
  sql: string
  database: string
  type?: 'sql' | 'er-diagram' | 'plan'
  // Single-query (legacy / simple case)
  queryExecutionId?: string
  queryState?: string
  queryError?: string
  isLoading: boolean
  limitApplied?: boolean
  reusedPreviousResult?: boolean
  // Multi-query support
  queryExecutions?: QueryExecution[]
  activeResultIdx?: number
  // Set to true to auto-execute the query when the tab first becomes active
  pendingRun?: boolean
}

interface EditorStore {
  tabs: EditorTab[]
  activeTabId: string | null
  pendingInsert: string | null
  addTab: (database?: string) => void
  openTab: (opts: { title: string; sql: string; database: string; pendingRun?: boolean; type?: EditorTab['type'] }) => void
  openErDiagramTab: (database: string) => void
  closeTab: (id: string) => void
  closeOtherTabs: (id: string) => void
  closeAllTabs: () => void
  setActiveTab: (id: string) => void
  updateTab: (id: string, updates: Partial<EditorTab>) => void
  getActiveTab: () => EditorTab | undefined
  setPendingInsert: (text: string | null) => void
}

let tabCounter = 0

function newTabId() {
  return `tab-${Date.now()}-${++tabCounter}`
}

export const useEditorStore = create<EditorStore>()(
  persist(
    (set, get) => ({
      tabs: [],
      activeTabId: null,
      pendingInsert: null,

      addTab: (database = '') => {
        const id = newTabId()
        const newTab: EditorTab = {
          id,
          title: database ? `${database}` : `Query`,
          sql: '',
          database,
          isLoading: false,
        }
        set(state => ({ tabs: [...state.tabs, newTab], activeTabId: id }))
      },

      openTab: ({ title, sql, database, pendingRun, type }) => {
        const id = newTabId()
        const newTab: EditorTab = { id, title, sql, database, isLoading: false, pendingRun, type }
        set(state => ({ tabs: [...state.tabs, newTab], activeTabId: id }))
      },

      openErDiagramTab: (database: string) => {
        // Reuse an existing ER diagram tab for the same database if one is open
        const existing = get().tabs.find(t => t.type === 'er-diagram' && t.database === database)
        if (existing) {
          set({ activeTabId: existing.id })
          return
        }
        const id = newTabId()
        const newTab: EditorTab = {
          id,
          title: `ER: ${database}`,
          sql: '',
          database,
          type: 'er-diagram',
          isLoading: false,
        }
        set(state => ({ tabs: [...state.tabs, newTab], activeTabId: id }))
      },

      closeTab: (id: string) => {
        set(state => {
          const tabs = state.tabs.filter(t => t.id !== id)
          let activeTabId = state.activeTabId
          if (activeTabId === id) {
            const idx = state.tabs.findIndex(t => t.id === id)
            activeTabId = tabs[Math.max(0, idx - 1)]?.id ?? null
          }
          return { tabs, activeTabId }
        })
      },

      closeOtherTabs: (id: string) => {
        set(state => ({
          tabs: state.tabs.filter(t => t.id === id),
          activeTabId: id,
        }))
      },

      closeAllTabs: () => set({ tabs: [], activeTabId: null }),

      setActiveTab: (id: string) => set({ activeTabId: id }),

      updateTab: (id: string, updates: Partial<EditorTab>) => {
        set(state => ({
          tabs: state.tabs.map(t => t.id === id ? { ...t, ...updates } : t),
        }))
      },

      getActiveTab: () => {
        const { tabs, activeTabId } = get()
        return tabs.find(t => t.id === activeTabId)
      },

      setPendingInsert: (text) => set({ pendingInsert: text }),
    }),
    {
      name: 'argus-editor-tabs',
      // Don't persist transient loading/error state — reset those on restore
      partialize: (state) => ({
        tabs: state.tabs.map(t => ({
          ...t,
          isLoading: false,
          queryError: undefined,
          queryExecutions: undefined,
          activeResultIdx: undefined,
          queryState: t.queryState === 'RUNNING' || t.queryState === 'QUEUED' ? undefined : t.queryState,
        })),
        activeTabId: state.activeTabId,
      }),
    }
  )
)
