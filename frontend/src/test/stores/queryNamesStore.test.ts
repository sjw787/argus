import { describe, it, expect, beforeEach } from 'vitest'
import { useQueryNamesStore, extractSqlComment } from '../../stores/queryNamesStore'

beforeEach(() => {
  useQueryNamesStore.setState({ names: {}, descriptions: {} })
})

describe('extractSqlComment', () => {
  it('extracts text after -- on the first line', () => {
    expect(extractSqlComment('-- Find all active users\nSELECT * FROM users')).toBe('Find all active users')
  })

  it('strips extra dashes and whitespace from -- comments', () => {
    expect(extractSqlComment('--  Monthly revenue report  ')).toBe('Monthly revenue report')
  })

  it('extracts text from /* */ block comment on first line', () => {
    expect(extractSqlComment('/* Revenue by region */\nSELECT region, SUM(amount) FROM orders')).toBe('Revenue by region')
  })

  it('returns undefined when first line has no comment', () => {
    expect(extractSqlComment('SELECT * FROM users')).toBeUndefined()
  })

  it('returns undefined for empty sql', () => {
    expect(extractSqlComment('')).toBeUndefined()
  })

  it('returns undefined for -- with no text', () => {
    expect(extractSqlComment('--\nSELECT 1')).toBeUndefined()
  })

  it('ignores comments on subsequent lines', () => {
    expect(extractSqlComment('SELECT 1\n-- this is a comment')).toBeUndefined()
  })

  it('handles leading whitespace before the comment', () => {
    expect(extractSqlComment('  -- Trimmed comment\nSELECT 1')).toBe('Trimmed comment')
  })
})

describe('queryNamesStore', () => {
  it('setName stores a name for a query execution id', () => {
    useQueryNamesStore.getState().setName('exec-123', 'User Growth Query')
    expect(useQueryNamesStore.getState().names['exec-123']).toBe('User Growth Query')
  })

  it('getName retrieves a stored name', () => {
    useQueryNamesStore.getState().setName('exec-456', 'Revenue Report')
    expect(useQueryNamesStore.getState().getName('exec-456')).toBe('Revenue Report')
  })

  it('getName returns undefined for unknown id', () => {
    expect(useQueryNamesStore.getState().getName('does-not-exist')).toBeUndefined()
  })

  it('setDescription stores a description for a query execution id', () => {
    useQueryNamesStore.getState().setDescription('exec-789', 'Finds all active users')
    expect(useQueryNamesStore.getState().descriptions['exec-789']).toBe('Finds all active users')
  })

  it('getDescription retrieves a stored description', () => {
    useQueryNamesStore.getState().setDescription('exec-abc', 'Monthly totals')
    expect(useQueryNamesStore.getState().getDescription('exec-abc')).toBe('Monthly totals')
  })

  it('getDescription returns undefined for unknown id', () => {
    expect(useQueryNamesStore.getState().getDescription('unknown')).toBeUndefined()
  })

  it('stores names and descriptions independently', () => {
    useQueryNamesStore.getState().setName('exec-1', 'Query A')
    useQueryNamesStore.getState().setDescription('exec-2', 'Description for B')

    expect(useQueryNamesStore.getState().names['exec-1']).toBe('Query A')
    expect(useQueryNamesStore.getState().descriptions['exec-2']).toBe('Description for B')
    expect(useQueryNamesStore.getState().names['exec-2']).toBeUndefined()
    expect(useQueryNamesStore.getState().descriptions['exec-1']).toBeUndefined()
  })

  it('overwrites existing name on second setName', () => {
    useQueryNamesStore.getState().setName('exec-1', 'Old Name')
    useQueryNamesStore.getState().setName('exec-1', 'New Name')
    expect(useQueryNamesStore.getState().getName('exec-1')).toBe('New Name')
  })
})
