import { Parser } from 'node-sql-parser'
import type * as Monaco from 'monaco-editor'

const parser = new Parser()
const OWNER = 'sql-diagnostics'
let _debounceTimer: ReturnType<typeof setTimeout> | null = null
const _disposables = new Map<string, Monaco.IDisposable>()

/**
 * Split SQL on semicolons while ignoring semicolons inside string literals.
 * Returns an array of { sql, startLine } objects so we can map parse errors
 * back to their correct line numbers in the original document.
 */
function splitStatements(text: string): Array<{ sql: string; startLine: number }> {
  const statements: Array<{ sql: string; startLine: number }> = []
  let current = ''
  let startLine = 1
  let currentLine = 1
  let inString: "'" | '"' | null = null

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]

    if (inString) {
      current += ch
      if (ch === inString && text[i - 1] !== '\\') inString = null
    } else if (ch === "'" || ch === '"') {
      inString = ch
      current += ch
    } else if (ch === '-' && text[i + 1] === '-') {
      // line comment — consume until newline
      while (i < text.length && text[i] !== '\n') {
        current += text[i++]
      }
      if (i < text.length) { current += '\n'; currentLine++ }
    } else if (ch === ';') {
      const trimmed = current.trim()
      if (trimmed) statements.push({ sql: trimmed, startLine })
      startLine = currentLine
      current = ''
    } else {
      if (ch === '\n') currentLine++
      current += ch
    }
  }

  const trimmed = current.trim()
  if (trimmed) statements.push({ sql: trimmed, startLine })
  return statements
}

function lintSql(
  monaco: typeof Monaco,
  model: Monaco.editor.ITextModel,
): void {
  const text = model.getValue()
  const markers: Monaco.editor.IMarkerData[] = []

  const statements = splitStatements(text)
  for (const { sql, startLine } of statements) {
    // Skip pure comment blocks
    if (/^(--[^\n]*\n?)*$/.test(sql)) continue

    try {
      parser.astify(sql, { database: 'Trino' })
    } catch (err: unknown) {
      const e = err as { location?: { start?: { line?: number; column?: number }; end?: { line?: number; column?: number } }; message?: string }
      const errLine = (e.location?.start?.line ?? 1)
      const errCol = (e.location?.start?.column ?? 0) + 1
      const endLine = (e.location?.end?.line ?? errLine)
      const endCol = (e.location?.end?.column ?? errCol) + 1

      // Strip the "Expected …" long list from the message — keep first sentence only
      const raw = e.message ?? 'Syntax error'
      const short = raw.split('\n')[0].replace(/^Error:\s*/i, '').trim()

      markers.push({
        severity: monaco.MarkerSeverity.Error,
        startLineNumber: startLine + errLine - 1,
        startColumn: errLine === 1 ? errCol : errCol,
        endLineNumber: startLine + endLine - 1,
        endColumn: endLine === 1 ? endCol : endCol,
        message: short,
        source: 'SQL',
      })
    }
  }

  monaco.editor.setModelMarkers(model, OWNER, markers)
}

/** Register live syntax checking for a specific editor instance. */
export function registerSqlDiagnostics(
  monaco: typeof Monaco,
  editor: Monaco.editor.IStandaloneCodeEditor,
): void {
  const model = editor.getModel()
  if (!model) return
  const modelId = model.id

  // Avoid double-registering for the same model
  if (_disposables.has(modelId)) return

  // Run immediately on mount
  lintSql(monaco, model)

  const disposable = model.onDidChangeContent(() => {
    if (_debounceTimer) clearTimeout(_debounceTimer)
    _debounceTimer = setTimeout(() => lintSql(monaco, model), 600)
  })

  _disposables.set(modelId, disposable)
}

/** Unregister diagnostics for a specific editor instance and clear its markers. */
export function unregisterSqlDiagnostics(
  monaco: typeof Monaco,
  editor: Monaco.editor.IStandaloneCodeEditor,
): void {
  const model = editor.getModel()
  if (!model) return
  const modelId = model.id

  _disposables.get(modelId)?.dispose()
  _disposables.delete(modelId)
  monaco.editor.setModelMarkers(model, OWNER, [])
}
