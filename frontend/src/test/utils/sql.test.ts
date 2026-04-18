import { describe, it, expect } from 'vitest'
import { splitSqlStatements, addWhereCondition, formatSqlValue } from '../../utils/sql'

// ---------------------------------------------------------------------------
// splitSqlStatements
// ---------------------------------------------------------------------------

describe('splitSqlStatements', () => {
  it('returns a single statement without a semicolon', () => {
    expect(splitSqlStatements('SELECT 1')).toEqual(['SELECT 1'])
  })

  it('splits two semicolon-delimited statements', () => {
    const sql = 'SELECT 1;\nSELECT 2;'
    expect(splitSqlStatements(sql)).toEqual(['SELECT 1', 'SELECT 2'])
  })

  it('ignores semicolons inside single-quoted strings', () => {
    const sql = "SELECT 'a;b' FROM t;"
    expect(splitSqlStatements(sql)).toEqual(["SELECT 'a;b' FROM t"])
  })

  it('ignores semicolons inside line comments', () => {
    const sql = '-- SELECT 1;\nSELECT 2;'
    expect(splitSqlStatements(sql)).toEqual(['-- SELECT 1;\nSELECT 2'])
  })

  it('ignores semicolons inside block comments', () => {
    const sql = '/* SELECT 1; */ SELECT 2;'
    expect(splitSqlStatements(sql)).toEqual(['/* SELECT 1; */ SELECT 2'])
  })

  it('strips semicolons from returned statements', () => {
    const stmts = splitSqlStatements('SELECT 1;SELECT 2;')
    expect(stmts.every(s => !s.endsWith(';'))).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// formatSqlValue
// ---------------------------------------------------------------------------

describe('formatSqlValue', () => {
  it('returns null for null value', () => {
    expect(formatSqlValue(null)).toBeNull()
  })

  it('quotes string values', () => {
    expect(formatSqlValue('hello')).toBe("'hello'")
  })

  it('does not quote numeric strings', () => {
    expect(formatSqlValue('42')).toBe('42')
    expect(formatSqlValue('3.14')).toBe('3.14')
  })

  it('uses unquoted numeric literal for numeric column type', () => {
    expect(formatSqlValue('99', 'bigint')).toBe('99')
    expect(formatSqlValue('1.5', 'double')).toBe('1.5')
  })

  it('uses boolean keyword for boolean type', () => {
    expect(formatSqlValue('true', 'boolean')).toBe('true')
    expect(formatSqlValue('false', 'boolean')).toBe('false')
    expect(formatSqlValue('1', 'boolean')).toBe('true')
  })

  it('uses DATE prefix for date type', () => {
    expect(formatSqlValue('2024-01-15', 'date')).toBe("DATE '2024-01-15'")
  })

  it('uses TIMESTAMP prefix for timestamp type', () => {
    expect(formatSqlValue('2024-01-15 10:00:00', 'timestamp')).toBe("TIMESTAMP '2024-01-15 10:00:00'")
  })

  it('escapes single quotes in string values', () => {
    expect(formatSqlValue("it's")).toBe("'it''s'")
  })
})

// ---------------------------------------------------------------------------
// addWhereCondition — basic injection
// ---------------------------------------------------------------------------

describe('addWhereCondition – basic injection', () => {
  it('appends WHERE clause to a query with no WHERE', () => {
    const result = addWhereCondition('SELECT * FROM t', 'col', 'val')
    expect(result).toContain('WHERE')
    expect(result).toContain('"col"')
    expect(result).toContain("'val'")
    expect(result.trimEnd()).toMatch(/;$/)
  })

  it('appends AND when WHERE already exists', () => {
    const result = addWhereCondition('SELECT * FROM t WHERE a = 1', 'col', 'val')
    expect(result).toContain('AND')
    expect(result).toContain('"col"')
    expect(result.trimEnd()).toMatch(/;$/)
  })

  it('inserts IS NULL predicate for null value', () => {
    const result = addWhereCondition('SELECT * FROM t', 'col', null)
    expect(result).toContain('IS NULL')
    expect(result.trimEnd()).toMatch(/;$/)
  })

  it('inserts WHERE before ORDER BY', () => {
    const result = addWhereCondition('SELECT * FROM t ORDER BY id', 'col', 'val')
    const whereIdx = result.indexOf('WHERE')
    const orderIdx = result.indexOf('ORDER BY')
    expect(whereIdx).toBeGreaterThan(-1)
    expect(orderIdx).toBeGreaterThan(whereIdx)
    expect(result.trimEnd()).toMatch(/;$/)
  })

  it('always returns a trailing semicolon', () => {
    expect(addWhereCondition('SELECT 1', 'x', 'y').trimEnd()).toMatch(/;$/)
    expect(addWhereCondition('SELECT 1;', 'x', 'y').trimEnd()).toMatch(/;$/)
  })
})

// ---------------------------------------------------------------------------
// addWhereCondition — merge / IN-list logic
// ---------------------------------------------------------------------------

describe('addWhereCondition – IN-list merging', () => {
  it('converts equality to IN when the same column already has = filter', () => {
    const result = addWhereCondition("SELECT * FROM t WHERE \"col\" = 'a'", 'col', 'b')
    expect(result).toMatch(/IN\s*\('a',\s*'b'\)/i)
  })

  it('appends to existing IN list for the same column', () => {
    const result = addWhereCondition("SELECT * FROM t WHERE \"col\" IN ('a', 'b')", 'col', 'c')
    expect(result).toMatch(/IN\s*\('a', 'b',\s*'c'\)/i)
  })
})

// ---------------------------------------------------------------------------
// addWhereCondition — multi-query semicolon preservation (the fixed bug)
// ---------------------------------------------------------------------------

describe('addWhereCondition – semicolon preservation across multi-query tabs', () => {
  it('returns a statement with exactly one trailing semicolon', () => {
    // This is the atomic contract that the multi-query reassembly depends on
    const result = addWhereCondition('SELECT * FROM t', 'col', 'val')
    const trimmed = result.trimEnd()
    expect(trimmed.endsWith(';')).toBe(true)
    expect(trimmed.endsWith(';;')).toBe(false)
  })

  it('multi-query reassembly: all statements keep their semicolons after split-modify-join', () => {
    // Simulate what addToWhere does when queryIndex is set:
    //   1. split (strips semicolons)
    //   2. modify one statement (addWhereCondition re-adds ;)
    //   3. ensure ALL statements get ; before joining
    const originalSql = 'SELECT * FROM table1;\n\nSELECT * FROM table2;'
    const stmts = splitSqlStatements(originalSql)
    expect(stmts).toHaveLength(2)

    // Modify the second statement (queryIndex = 1)
    stmts[1] = addWhereCondition(stmts[1], 'id', '42', 'bigint')

    // Reassemble with the fix: ensure every statement gets a trailing semicolon
    const reassembled = stmts.map(s => s.trimEnd().replace(/;+$/, '') + ';').join('\n\n')

    // Both statements must end with a semicolon in the reassembled string
    const parts = reassembled.split('\n\n')
    expect(parts).toHaveLength(2)
    expect(parts[0].trimEnd()).toMatch(/;$/)
    expect(parts[1].trimEnd()).toMatch(/;$/)

    // The first statement must be unchanged
    expect(parts[0]).toBe('SELECT * FROM table1;')

    // The second statement must contain the injected WHERE clause
    expect(parts[1]).toContain('WHERE')
    expect(parts[1]).toContain('"id"')
    expect(parts[1]).toContain('42')
  })

  it('three-statement tab: only the target statement is modified, all keep semicolons', () => {
    const originalSql = 'SELECT * FROM a;\nSELECT * FROM b;\nSELECT * FROM c;'
    const stmts = splitSqlStatements(originalSql)
    expect(stmts).toHaveLength(3)

    // Modify the middle statement (queryIndex = 1)
    stmts[1] = addWhereCondition(stmts[1], 'name', 'Alice')

    const reassembled = stmts.map(s => s.trimEnd().replace(/;+$/, '') + ';').join('\n\n')
    const parts = reassembled.split('\n\n')

    expect(parts).toHaveLength(3)
    parts.forEach(p => expect(p.trimEnd()).toMatch(/;$/))
    expect(parts[0]).toBe('SELECT * FROM a;')
    expect(parts[1]).toContain('WHERE')
    expect(parts[1]).toContain('"name"')
    expect(parts[2]).toBe('SELECT * FROM c;')
  })

  it('first-statement target preserves subsequent statements', () => {
    const originalSql = 'SELECT * FROM first;\nSELECT * FROM second;'
    const stmts = splitSqlStatements(originalSql)

    stmts[0] = addWhereCondition(stmts[0], 'status', 'active')
    const reassembled = stmts.map(s => s.trimEnd().replace(/;+$/, '') + ';').join('\n\n')
    const parts = reassembled.split('\n\n')

    expect(parts[0]).toContain('WHERE')
    expect(parts[1]).toBe('SELECT * FROM second;')
  })
})
