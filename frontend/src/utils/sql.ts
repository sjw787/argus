/** Athena types stored as unquoted numeric literals in SQL. */
const NUMERIC_TYPES = new Set([
  'tinyint', 'smallint', 'int', 'integer', 'bigint',
  'float', 'real', 'double', 'decimal',
])
const BOOLEAN_TYPES = new Set(['boolean'])
/** Types that use keyword-prefixed date/timestamp literals (still quoted). */
const TEMPORAL_TYPES = new Set(['date', 'timestamp', 'time'])

/** Format a cell value into a SQL literal appropriate for its column type. */
export function formatSqlValue(value: string | null, colType?: string): string | null {
  if (value === null) return null
  const baseType = colType?.toLowerCase().replace(/\(.*\)/, '').trim()
  if (baseType && BOOLEAN_TYPES.has(baseType)) {
    const lower = value.toLowerCase()
    return lower === 'true' || lower === '1' ? 'true' : 'false'
  }
  if (baseType && NUMERIC_TYPES.has(baseType)) {
    return value
  }
  if (baseType && TEMPORAL_TYPES.has(baseType)) {
    const prefix = baseType === 'date' ? 'DATE' : baseType === 'time' ? 'TIME' : 'TIMESTAMP'
    return `${prefix} '${value.replace(/'/g, "''")}'`
  }
  // Fallback: heuristic for when no type metadata is available
  if (/^-?\d+(\.\d+)?$/.test(value)) return value
  return `'${value.replace(/'/g, "''")}'`
}

/** Append or inject a WHERE predicate into a SQL string.
 *  Always returns the statement with a trailing semicolon.
 *  Merges into an existing IN-list or converts an equality to IN when the
 *  same column is already filtered. */
export function addWhereCondition(sql: string, col: string, value: string | null, colType?: string): string {
  const upper = /\bSELECT\b/.test(sql) || /\bFROM\b/.test(sql)
  const kw = (s: string) => upper ? s.toUpperCase() : s.toLowerCase()

  const colRef = `"${col}"`
  const escapedCol = colRef.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  const formattedValue = formatSqlValue(value, colType)

  // Strip trailing semicolons/whitespace to manipulate cleanly
  const trimmed = sql.trimEnd().replace(/;+$/, '').trimEnd()

  const clauseIndentMatch = trimmed.match(/^([ \t]*)(?:FROM|WHERE|ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b/im)
  const clauseIndent = clauseIndentMatch?.[1] ?? ''

  const whereRe = /\bWHERE\b/i
  const clauseRe = /\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b/i

  if (whereRe.test(trimmed) && formattedValue !== null) {
    // Case 1: col IN (...) already exists — append to the IN list
    const inRe = new RegExp(`(${escapedCol}\\s+IN\\s*\\()([^)]*)(\\))`, 'i')
    const inMatch = inRe.exec(trimmed)
    if (inMatch) {
      const updated = trimmed.replace(inRe, (_, open, list, close) =>
        `${open}${list.trimEnd()}, ${formattedValue}${close}`
      )
      return updated + ';'
    }

    // Case 2: col = value exists — convert to col IN (old, new)
    const eqRe = new RegExp(
      `${escapedCol}\\s*=\\s*((?:DATE|TIMESTAMP|TIME)\\s+'(?:[^']|'')*'|'(?:[^']|'')*'|-?\\d+(?:\\.\\d+)?)`,
      'i'
    )
    const eqMatch = eqRe.exec(trimmed)
    if (eqMatch) {
      const existingVal = eqMatch[1]
      const updated = trimmed.replace(eqRe,
        `${colRef} ${kw('in')} (${existingVal}, ${formattedValue})`
      )
      return updated + ';'
    }
  }

  let predicate: string
  if (value === null) {
    predicate = `${colRef} ${kw('is null')}`
  } else {
    predicate = `${colRef} = ${formattedValue}`
  }

  if (whereRe.test(trimmed)) {
    const match = clauseRe.exec(trimmed)
    if (match) {
      const before = trimmed.slice(0, match.index).trimEnd()
      const after = trimmed.slice(match.index).trimStart()
      return `${before}\n${clauseIndent}${kw('and')} ${predicate}\n${clauseIndent}${after};`
    }
    return `${trimmed}\n${clauseIndent}${kw('and')} ${predicate};`
  }

  const match = clauseRe.exec(trimmed)
  if (match) {
    const before = trimmed.slice(0, match.index).trimEnd()
    const after = trimmed.slice(match.index).trimStart()
    return `${before}\n${clauseIndent}${kw('where')} ${predicate}\n${clauseIndent}${after};`
  }
  return `${trimmed}\n${clauseIndent}${kw('where')} ${predicate};`
}

/** Split a SQL string into individual statements on `;`, respecting
 *  single-quoted strings, single-line comments, and block comments. */
export function splitSqlStatements(sql: string): string[] {
  const stmts: string[] = []
  let cur = ''
  let i = 0
  while (i < sql.length) {
    const ch = sql[i]
    if (ch === '-' && sql[i + 1] === '-') {
      const end = sql.indexOf('\n', i)
      cur += end === -1 ? sql.slice(i) : sql.slice(i, end + 1)
      i = end === -1 ? sql.length : end + 1
      continue
    }
    if (ch === '/' && sql[i + 1] === '*') {
      const end = sql.indexOf('*/', i + 2)
      cur += end === -1 ? sql.slice(i) : sql.slice(i, end + 2)
      i = end === -1 ? sql.length : end + 2
      continue
    }
    if (ch === "'") {
      let j = i + 1
      while (j < sql.length) {
        if (sql[j] === "'" && sql[j + 1] === "'") { j += 2; continue }
        if (sql[j] === "'") { j++; break }
        j++
      }
      cur += sql.slice(i, j)
      i = j
      continue
    }
    if (ch === ';') {
      const stmt = cur.trim()
      if (stmt) stmts.push(stmt)
      cur = ''
      i++
      continue
    }
    cur += ch
    i++
  }
  const last = cur.trim()
  if (last) stmts.push(last)
  return stmts
}
