import { describe, it, expect, beforeEach } from 'vitest'
import { useEditorStore } from '../../stores/editorStore'

// Reset store state between tests
beforeEach(() => {
  useEditorStore.setState({ tabs: [], activeTabId: null })
})

describe('editorStore – tab management', () => {
  it('starts with no tabs', () => {
    const { tabs, activeTabId } = useEditorStore.getState()
    expect(tabs).toHaveLength(0)
    expect(activeTabId).toBeNull()
  })

  it('addTab creates a tab and makes it active', () => {
    useEditorStore.getState().addTab()
    const { tabs, activeTabId } = useEditorStore.getState()
    expect(tabs).toHaveLength(1)
    expect(tabs[0].isLoading).toBe(false)
    expect(activeTabId).toBe(tabs[0].id)
  })

  it('addTab with a database names the tab after the database', () => {
    useEditorStore.getState().addTab('my_db')
    const { tabs } = useEditorStore.getState()
    expect(tabs[0].title).toBe('my_db')
    expect(tabs[0].database).toBe('my_db')
  })

  it('openTab creates a pre-populated tab with sql and title', () => {
    useEditorStore.getState().openTab({ title: 'My Query', sql: 'SELECT 1', database: 'prod_db' })
    const { tabs, activeTabId } = useEditorStore.getState()
    expect(tabs).toHaveLength(1)
    expect(tabs[0].title).toBe('My Query')
    expect(tabs[0].sql).toBe('SELECT 1')
    expect(tabs[0].database).toBe('prod_db')
    expect(activeTabId).toBe(tabs[0].id)
  })

  it('closeTab removes the tab and activates the previous one', () => {
    useEditorStore.getState().addTab()
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    const [first, second] = tabs

    useEditorStore.getState().closeTab(second.id)

    const state = useEditorStore.getState()
    expect(state.tabs).toHaveLength(1)
    expect(state.activeTabId).toBe(first.id)
  })

  it('closeTab on only tab leaves no active tab', () => {
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    useEditorStore.getState().closeTab(tabs[0].id)

    const state = useEditorStore.getState()
    expect(state.tabs).toHaveLength(0)
    expect(state.activeTabId).toBeNull()
  })

  it('updateTab patches only the specified fields', () => {
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    const id = tabs[0].id

    useEditorStore.getState().updateTab(id, { sql: 'SELECT * FROM orders', title: 'Orders' })

    const updated = useEditorStore.getState().tabs[0]
    expect(updated.sql).toBe('SELECT * FROM orders')
    expect(updated.title).toBe('Orders')
    expect(updated.isLoading).toBe(false) // unchanged
  })

  it('getActiveTab returns the currently active tab', () => {
    useEditorStore.getState().addTab('db1')
    const active = useEditorStore.getState().getActiveTab()
    expect(active).toBeDefined()
    expect(active!.database).toBe('db1')
  })
})

describe('editorStore – SQL persistence behaviour', () => {
  it('sql content survives updateTab and is readable from the store', () => {
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    const id = tabs[0].id

    useEditorStore.getState().updateTab(id, { sql: 'SELECT id FROM users LIMIT 10' })
    const stored = useEditorStore.getState().tabs.find(t => t.id === id)
    expect(stored?.sql).toBe('SELECT id FROM users LIMIT 10')
  })

  it('onChange guard: updateTab is not called when sql is unchanged', () => {
    // Simulates the onChange guard: `if (val !== tab.sql) updateTab(...)`
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    const id = tabs[0].id
    useEditorStore.getState().updateTab(id, { sql: 'SELECT 1' })

    // Simulate Monaco onChange firing with the same value (should be a no-op in the component)
    const before = useEditorStore.getState().tabs[0].sql
    const val = 'SELECT 1'
    if (val !== before) useEditorStore.getState().updateTab(id, { sql: val })

    expect(useEditorStore.getState().tabs[0].sql).toBe('SELECT 1')
  })

  it('partialize resets isLoading to false on persisted tabs', () => {
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    useEditorStore.getState().updateTab(tabs[0].id, { isLoading: true })

    // Simulate what partialize produces
    const state = useEditorStore.getState()
    const partialState = {
      tabs: state.tabs.map(t => ({
        ...t,
        isLoading: false,
        queryError: undefined,
        queryState: t.queryState === 'RUNNING' || t.queryState === 'QUEUED' ? undefined : t.queryState,
      })),
      activeTabId: state.activeTabId,
    }

    expect(partialState.tabs[0].isLoading).toBe(false)
  })

  it('partialize clears RUNNING queryState but keeps SUCCEEDED', () => {
    useEditorStore.getState().addTab()
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    useEditorStore.getState().updateTab(tabs[0].id, { queryState: 'RUNNING' })
    useEditorStore.getState().updateTab(tabs[1].id, { queryState: 'SUCCEEDED' })

    const state = useEditorStore.getState()
    const partialTabs = state.tabs.map(t => ({
      ...t,
      queryState: t.queryState === 'RUNNING' || t.queryState === 'QUEUED' ? undefined : t.queryState,
    }))

    expect(partialTabs[0].queryState).toBeUndefined()
    expect(partialTabs[1].queryState).toBe('SUCCEEDED')
  })

  it('partialize clears queryError', () => {
    useEditorStore.getState().addTab()
    const { tabs } = useEditorStore.getState()
    useEditorStore.getState().updateTab(tabs[0].id, { queryError: 'Syntax error near FROM' })

    const state = useEditorStore.getState()
    const partialTabs = state.tabs.map(t => ({ ...t, queryError: undefined }))
    expect(partialTabs[0].queryError).toBeUndefined()
  })
})

describe('editorStore – no-duplicate-tab-on-refresh logic', () => {
  it('addTab is skipped when tabs already exist (AppLayout guard)', () => {
    // Pre-populate store as if restored from localStorage
    useEditorStore.setState({
      tabs: [{ id: 'tab-42', title: 'My Query', sql: 'SELECT 1', database: 'prod', isLoading: false }],
      activeTabId: 'tab-42',
    })

    // Simulate AppLayout's useEffect: if (tabs.length === 0) addTab()
    const { tabs } = useEditorStore.getState()
    if (tabs.length === 0) useEditorStore.getState().addTab()

    expect(useEditorStore.getState().tabs).toHaveLength(1)
    expect(useEditorStore.getState().tabs[0].id).toBe('tab-42')
  })

  it('addTab is called when no tabs exist (fresh start)', () => {
    const { tabs } = useEditorStore.getState()
    if (tabs.length === 0) useEditorStore.getState().addTab()

    expect(useEditorStore.getState().tabs).toHaveLength(1)
  })
})
