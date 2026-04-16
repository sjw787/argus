import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EditorTabs } from '../../components/editor/EditorTabs'
import { useEditorStore } from '../../stores/editorStore'

// Lucide icons use SVG — no mocking needed for these tests

beforeEach(() => {
  useEditorStore.setState({ tabs: [], activeTabId: null })
  // Add a default tab to work with
  useEditorStore.getState().addTab()
})

describe('EditorTabs – rendering', () => {
  it('renders a tab with its title', () => {
    useEditorStore.getState().updateTab(useEditorStore.getState().tabs[0].id, { title: 'My Query' })
    render(<EditorTabs />)
    expect(screen.getByText('My Query')).toBeInTheDocument()
  })

  it('renders a + button to add a new tab', () => {
    render(<EditorTabs />)
    // The Plus button has a title attribute
    expect(screen.getByTitle('New Tab')).toBeInTheDocument()
  })

  it('clicking + adds a new tab', async () => {
    render(<EditorTabs />)
    const addBtn = screen.getByTitle('New Tab')
    await userEvent.click(addBtn)
    expect(useEditorStore.getState().tabs).toHaveLength(2)
  })
})

describe('EditorTabs – tab rename', () => {
  it('double-clicking a tab title shows an input', async () => {
    useEditorStore.getState().updateTab(useEditorStore.getState().tabs[0].id, { title: 'Original' })
    render(<EditorTabs />)

    const title = screen.getByText('Original')
    await userEvent.dblClick(title)

    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('committing with Enter saves the new title', async () => {
    useEditorStore.getState().updateTab(useEditorStore.getState().tabs[0].id, { title: 'Original' })
    render(<EditorTabs />)

    const title = screen.getByText('Original')
    await userEvent.dblClick(title)

    const input = screen.getByRole('textbox')
    await userEvent.clear(input)
    await userEvent.type(input, 'Renamed Tab{Enter}')

    expect(useEditorStore.getState().tabs[0].title).toBe('Renamed Tab')
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('pressing Escape cancels the rename without saving', async () => {
    useEditorStore.getState().updateTab(useEditorStore.getState().tabs[0].id, { title: 'Original' })
    render(<EditorTabs />)

    await userEvent.dblClick(screen.getByText('Original'))
    const input = screen.getByRole('textbox')
    await userEvent.clear(input)
    await userEvent.type(input, 'Discarded{Escape}')

    expect(useEditorStore.getState().tabs[0].title).toBe('Original')
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('blurring the input commits the rename', async () => {
    useEditorStore.getState().updateTab(useEditorStore.getState().tabs[0].id, { title: 'Original' })
    render(<EditorTabs />)

    await userEvent.dblClick(screen.getByText('Original'))
    const input = screen.getByRole('textbox')
    await userEvent.clear(input)
    await userEvent.type(input, 'Blur Saved')
    fireEvent.blur(input)

    expect(useEditorStore.getState().tabs[0].title).toBe('Blur Saved')
  })

  it('an empty rename is not committed — title stays unchanged', async () => {
    useEditorStore.getState().updateTab(useEditorStore.getState().tabs[0].id, { title: 'Original' })
    render(<EditorTabs />)

    await userEvent.dblClick(screen.getByText('Original'))
    const input = screen.getByRole('textbox')
    await userEvent.clear(input)
    fireEvent.blur(input)

    expect(useEditorStore.getState().tabs[0].title).toBe('Original')
  })
})

describe('EditorTabs – close tab', () => {
  it('clicking × removes the tab', async () => {
    render(<EditorTabs />)
    const tabDiv = screen.getByText(/Query/).closest('div')!
    const xBtn = tabDiv.querySelector('button')!
    await userEvent.click(xBtn)

    expect(useEditorStore.getState().tabs).toHaveLength(0)
  })
})
