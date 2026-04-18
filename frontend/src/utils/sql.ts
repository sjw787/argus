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
