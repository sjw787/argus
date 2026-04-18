/**
 * Monaco SQL completion provider for Argus for Athena.
 * Registers once globally; dynamically resolves tables/columns from the active database.
 */
import type * as Monaco from 'monaco-editor'
import { api } from '../api/client'

// ── SQL keywords and Athena/Presto built-in functions ─────────────────────────

const KEYWORDS = [
  'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET',
  'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'FULL OUTER JOIN', 'CROSS JOIN',
  'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'IS NULL', 'IS NOT NULL',
  'AS', 'DISTINCT', 'ALL', 'UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT',
  'INSERT INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE FROM',
  'CREATE TABLE', 'CREATE TABLE IF NOT EXISTS', 'DROP TABLE', 'ALTER TABLE',
  'WITH', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
  'ASC', 'DESC', 'NULLS FIRST', 'NULLS LAST',
  'PARTITION BY', 'OVER', 'ROWS BETWEEN', 'RANGE BETWEEN', 'CURRENT ROW',
  'UNBOUNDED PRECEDING', 'UNBOUNDED FOLLOWING',
  'TRUE', 'FALSE', 'NULL',
  'CAST', 'TRY_CAST', 'TYPEOF',
  'TABLESAMPLE', 'BERNOULLI', 'SYSTEM',
]

const FUNCTIONS = [
  // Aggregate
  'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'APPROX_DISTINCT', 'APPROX_PERCENTILE',
  'ARBITRARY', 'ARRAY_AGG', 'BOOL_AND', 'BOOL_OR', 'CHECKSUM',
  'CORR', 'COVAR_POP', 'COVAR_SAMP', 'EVERY', 'GEOMETRIC_MEAN',
  'KURTOSIS', 'SKEWNESS', 'STDDEV', 'STDDEV_POP', 'STDDEV_SAMP',
  'VAR_POP', 'VAR_SAMP', 'VARIANCE',
  // String
  'CONCAT', 'LENGTH', 'LOWER', 'UPPER', 'TRIM', 'LTRIM', 'RTRIM',
  'SUBSTR', 'SUBSTRING', 'REPLACE', 'REGEXP_EXTRACT', 'REGEXP_LIKE',
  'REGEXP_REPLACE', 'SPLIT', 'SPLIT_PART', 'STRPOS', 'POSITION',
  'REVERSE', 'LPAD', 'RPAD', 'REPEAT', 'TRANSLATE', 'NORMALIZE',
  // Date/time
  'NOW', 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
  'DATE_FORMAT', 'DATE_PARSE', 'DATE_ADD', 'DATE_DIFF', 'DATE_TRUNC',
  'DAY', 'MONTH', 'YEAR', 'HOUR', 'MINUTE', 'SECOND', 'WEEK', 'QUARTER',
  'FROM_UNIXTIME', 'TO_UNIXTIME', 'AT_TIMEZONE', 'WITH_TIMEZONE',
  'FORMAT_DATETIME', 'PARSE_DATETIME', 'LOCALTIMESTAMP',
  // Math
  'ABS', 'CEIL', 'CEILING', 'FLOOR', 'ROUND', 'TRUNCATE', 'SIGN',
  'POWER', 'SQRT', 'EXP', 'LN', 'LOG', 'LOG2', 'LOG10',
  'MOD', 'RAND', 'RANDOM', 'PI',
  // Array/Map
  'ARRAY', 'CARDINALITY', 'ELEMENT_AT', 'FLATTEN', 'ARRAY_DISTINCT',
  'ARRAY_EXCEPT', 'ARRAY_INTERSECT', 'ARRAY_JOIN', 'ARRAY_MAX', 'ARRAY_MIN',
  'ARRAY_POSITION', 'ARRAY_REMOVE', 'ARRAY_SORT', 'ARRAY_UNION',
  'MAP', 'MAP_KEYS', 'MAP_VALUES', 'MAP_ENTRIES', 'MAP_FROM_ENTRIES',
  // JSON
  'JSON_EXTRACT', 'JSON_EXTRACT_SCALAR', 'JSON_ARRAY_GET', 'JSON_ARRAY_LENGTH',
  'JSON_PARSE', 'TO_UTF8', 'FROM_UTF8',
  // Window
  'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'NTILE', 'PERCENT_RANK', 'CUME_DIST',
  'FIRST_VALUE', 'LAST_VALUE', 'NTH_VALUE', 'LAG', 'LEAD',
  // Type conversion
  'TO_CHAR', 'TO_DATE', 'TO_TIMESTAMP', 'PARSE_DURATION',
  // Conditional
  'IF', 'NULLIF', 'COALESCE', 'GREATEST', 'LEAST', 'TRY',
]

// ── Schema cache ──────────────────────────────────────────────────────────────

interface DbSchema {
  tables: string[]
  columns: Record<string, string[]>  // table → column names
}

const schemaCache = new Map<string, DbSchema>()

async function getSchema(database: string): Promise<DbSchema> {
  if (schemaCache.has(database)) return schemaCache.get(database)!

  const schema: DbSchema = { tables: [], columns: {} }
  try {
    const tables = await api.listTables(database)
    schema.tables = tables.map(t => t.name)

    await Promise.all(
      tables.map(async t => {
        try {
          const detail = await api.getTable(database, t.name)
          schema.columns[t.name] = (detail.columns ?? []).map((c: { name: string }) => c.name)
        } catch { /* ignore individual table errors */ }
      })
    )
  } catch { /* ignore — return empty schema */ }

  schemaCache.set(database, schema)
  // Expire after 2 minutes so schema changes are picked up
  setTimeout(() => schemaCache.delete(database), 120_000)
  return schema
}

// ── Registration ──────────────────────────────────────────────────────────────

let _disposable: Monaco.IDisposable | null = null
let _activeDatabase = ''

export function setActiveDatabase(database: string) {
  _activeDatabase = database
}

/** Return true if the cursor position is inside a SQL line or block comment. */
export function isInComment(model: Monaco.editor.ITextModel, position: Monaco.Position): boolean {
  const lineUpToCursor = model.getValueInRange({
    startLineNumber: position.lineNumber, startColumn: 1,
    endLineNumber: position.lineNumber, endColumn: position.column,
  })

  // Line comment: find first `--` that isn't inside a string literal
  let inString = false
  for (let i = 0; i < lineUpToCursor.length - 1; i++) {
    if (lineUpToCursor[i] === "'") { inString = !inString; continue }
    if (!inString && lineUpToCursor[i] === '-' && lineUpToCursor[i + 1] === '-') return true
  }

  // Block comment: scan full text up to cursor for /* ... */
  const fullTextToCursor = model.getValueInRange({
    startLineNumber: 1, startColumn: 1,
    endLineNumber: position.lineNumber, endColumn: position.column,
  })
  let depth = 0
  let j = 0
  while (j < fullTextToCursor.length) {
    if (fullTextToCursor[j] === "'" && depth === 0) {
      // Skip string literal
      j++
      while (j < fullTextToCursor.length) {
        if (fullTextToCursor[j] === "'" && fullTextToCursor[j + 1] === "'") { j += 2; continue }
        if (fullTextToCursor[j] === "'") { j++; break }
        j++
      }
      continue
    }
    if (fullTextToCursor[j] === '/' && fullTextToCursor[j + 1] === '*') { depth++; j += 2; continue }
    if (fullTextToCursor[j] === '*' && fullTextToCursor[j + 1] === '/') { depth = Math.max(0, depth - 1); j += 2; continue }
    j++
  }
  return depth > 0
}

export function registerSqlCompletion(monaco: typeof Monaco) {
  if (_disposable) return  // already registered

  _disposable = monaco.languages.registerCompletionItemProvider('sql', {
    // Only trigger on `.` for table.column completions.
    // Keywords/tables/columns are still suggested as the user types letters
    // via Monaco's built-in word-based trigger — no need to intercept space,
    // which causes the dropdown to open inside comments and string literals.
    triggerCharacters: ['.'],

    async provideCompletionItems(model, position) {
      // Don't suggest inside comments — this was causing spacebar to be
      // intercepted when typing comment text.
      if (isInComment(model, position)) return { suggestions: [] }

      const word = model.getWordUntilPosition(position)
      const range: Monaco.IRange = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: position.column,
      }

      const items: Monaco.languages.CompletionItem[] = []
      const { CompletionItemKind, CompletionItemInsertTextRule } = monaco.languages

      // Check if we're after a dot (table.column context)
      const lineUpToCursor = model.getValueInRange({
        startLineNumber: position.lineNumber, startColumn: 1,
        endLineNumber: position.lineNumber, endColumn: position.column,
      })
      const dotMatch = lineUpToCursor.match(/(\w+)\.\w*$/)

      if (dotMatch) {
        const tableName = dotMatch[1]
        if (_activeDatabase) {
          const schema = await getSchema(_activeDatabase)
          const cols = schema.columns[tableName] ?? schema.columns[tableName.toLowerCase()] ?? []
          for (const col of cols) {
            items.push({
              label: col,
              kind: CompletionItemKind.Field,
              insertText: col,
              range,
              detail: `column of ${tableName}`,
            })
          }
        }
        return { suggestions: items }
      }

      // Keywords
      for (const kw of KEYWORDS) {
        items.push({
          label: kw,
          kind: CompletionItemKind.Keyword,
          insertText: kw,
          range,
          sortText: `1_${kw}`,
        })
      }

      // Functions with snippet parens
      for (const fn of FUNCTIONS) {
        items.push({
          label: fn + '()',
          kind: CompletionItemKind.Function,
          insertText: `${fn}($1)`,
          insertTextRules: CompletionItemInsertTextRule.InsertAsSnippet,
          range,
          detail: 'function',
          sortText: `2_${fn}`,
        })
      }

      // Tables and columns from active database
      if (_activeDatabase) {
        const schema = await getSchema(_activeDatabase)
        for (const table of schema.tables) {
          items.push({
            label: table,
            kind: CompletionItemKind.Class,
            insertText: table,
            range,
            detail: _activeDatabase,
            sortText: `0_${table}`,
          })
        }
        for (const [table, cols] of Object.entries(schema.columns)) {
          for (const col of cols) {
            items.push({
              label: col,
              kind: CompletionItemKind.Field,
              insertText: col,
              range,
              detail: `${table}.${col}`,
              sortText: `0_${col}`,
            })
          }
        }
      }

      return { suggestions: items }
    },
  })
}

export function unregisterSqlCompletion() {
  _disposable?.dispose()
  _disposable = null
}
