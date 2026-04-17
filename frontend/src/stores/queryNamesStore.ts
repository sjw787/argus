import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface QueryNamesStore {
  names: Record<string, string>
  descriptions: Record<string, string>
  setName: (queryExecutionId: string, name: string) => void
  getName: (queryExecutionId: string) => string | undefined
  setDescription: (queryExecutionId: string, description: string) => void
  getDescription: (queryExecutionId: string) => string | undefined
}

export const useQueryNamesStore = create<QueryNamesStore>()(
  persist(
    (set, get) => ({
      names: {},
      descriptions: {},
      setName: (queryExecutionId, name) =>
        set(state => ({ names: { ...state.names, [queryExecutionId]: name } })),
      getName: (queryExecutionId) => get().names[queryExecutionId],
      setDescription: (queryExecutionId, description) =>
        set(state => ({ descriptions: { ...state.descriptions, [queryExecutionId]: description } })),
      getDescription: (queryExecutionId) => get().descriptions[queryExecutionId],
    }),
    { name: 'argus-query-names' }
  )
)

/** Extract a description from the first line of SQL if it's a comment. */
export function extractSqlComment(sql: string): string | undefined {
  const firstLine = sql.trimStart().split('\n')[0].trim()
  if (firstLine.startsWith('--')) {
    const text = firstLine.slice(2).trim()
    return text || undefined
  }
  if (firstLine.startsWith('/*')) {
    const text = firstLine.replace(/^\/\*+/, '').replace(/\*+\/$/, '').trim()
    return text || undefined
  }
  return undefined
}
