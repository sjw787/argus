import { describe, it, expect } from 'vitest'
import { isInComment } from '../../lib/sqlCompletion'

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Minimal Monaco ITextModel stub — only implements getValueInRange.
 * Line and column numbers are 1-based (matching Monaco's API).
 */
function mockModel(text: string) {
  const lines = text.split('\n')
  return {
    getValueInRange({ startLineNumber, startColumn, endLineNumber, endColumn }: {
      startLineNumber: number; startColumn: number
      endLineNumber: number; endColumn: number
    }): string {
      if (startLineNumber === endLineNumber) {
        return lines[startLineNumber - 1].slice(startColumn - 1, endColumn - 1)
      }
      let result = lines[startLineNumber - 1].slice(startColumn - 1)
      for (let i = startLineNumber; i < endLineNumber - 1; i++) {
        result += '\n' + lines[i]
      }
      result += '\n' + lines[endLineNumber - 1].slice(0, endColumn - 1)
      return result
    },
  }
}

function pos(lineNumber: number, column: number) {
  return { lineNumber, column } as any
}

// ── Line comment (--) ──────────────────────────────────────────────────────

describe('isInComment — line comment (--)', () => {
  it('returns true when cursor is after -- on the same line', () => {
    const model = mockModel('SELECT 1 -- this is a comment')
    // cursor at column 15 (inside the comment)
    expect(isInComment(model as any, pos(1, 15))).toBe(true)
  })

  it('returns true at the very start of the -- token', () => {
    const model = mockModel('-- comment')
    // column 3 = after the two dashes
    expect(isInComment(model as any, pos(1, 3))).toBe(true)
  })

  it('returns false when cursor is before -- on the same line', () => {
    const model = mockModel('SELECT 1 -- comment')
    // column 7 = inside "SELECT"
    expect(isInComment(model as any, pos(1, 7))).toBe(false)
  })

  it('returns false for normal SQL with no comment', () => {
    const model = mockModel('SELECT id FROM orders')
    expect(isInComment(model as any, pos(1, 10))).toBe(false)
  })

  it('returns false when -- appears inside a string literal', () => {
    // The '--' is inside a string, not a real comment
    const model = mockModel("SELECT '--not a comment' AS col")
    // cursor at column 12 (inside the string, after '--')
    expect(isInComment(model as any, pos(1, 12))).toBe(false)
  })

  it('handles -- comment on a second line', () => {
    const sql = 'SELECT 1\n-- second line comment'
    const model = mockModel(sql)
    // line 2, column 5 = inside the comment
    expect(isInComment(model as any, pos(2, 5))).toBe(true)
  })

  it('returns false on a line before a comment line', () => {
    const sql = 'SELECT 1\n-- comment'
    const model = mockModel(sql)
    // line 1 has no comment
    expect(isInComment(model as any, pos(1, 5))).toBe(false)
  })
})

// ── Block comment (/* */) ──────────────────────────────────────────────────

describe('isInComment — block comment (/* */)', () => {
  it('returns true when cursor is inside /* */', () => {
    const model = mockModel('SELECT /* comment */ 1')
    // column 12 = inside the block comment
    expect(isInComment(model as any, pos(1, 12))).toBe(true)
  })

  it('returns false when cursor is after a closed block comment', () => {
    const model = mockModel('SELECT /* comment */ 1')
    // column 22 = after the closing */
    expect(isInComment(model as any, pos(1, 22))).toBe(false)
  })

  it('returns true for unclosed block comment at end of text', () => {
    const model = mockModel('SELECT /* still open')
    // column 15 = well inside the unclosed comment
    expect(isInComment(model as any, pos(1, 15))).toBe(true)
  })

  it('handles multi-line block comment — cursor on second line', () => {
    const sql = '/*\n  multi-line comment\n*/ SELECT 1'
    const model = mockModel(sql)
    // line 2, column 5 = inside the block comment
    expect(isInComment(model as any, pos(2, 5))).toBe(true)
  })

  it('handles multi-line block comment — cursor after closing */', () => {
    const sql = '/*\n  multi-line comment\n*/ SELECT 1'
    const model = mockModel(sql)
    // line 3, column 10 = after */ which closes at col 3
    expect(isInComment(model as any, pos(3, 10))).toBe(false)
  })

  it('returns false when /* appears inside a string literal', () => {
    const model = mockModel("SELECT '/* not a comment */' AS col")
    // column 15 = inside the string
    expect(isInComment(model as any, pos(1, 15))).toBe(false)
  })

  it('returns false for a correctly closed /* */ with SQL after it', () => {
    const model = mockModel('/* header */ SELECT id FROM t')
    // column 20 = inside "SELECT"
    expect(isInComment(model as any, pos(1, 20))).toBe(false)
  })
})

// ── Edge cases ─────────────────────────────────────────────────────────────

describe('isInComment — edge cases', () => {
  it('returns false for an empty line', () => {
    const model = mockModel('')
    expect(isInComment(model as any, pos(1, 1))).toBe(false)
  })

  it('handles -- immediately preceded by a closed block comment', () => {
    const model = mockModel('/* block */ -- line')
    // column 16 = inside the line comment after the block comment
    expect(isInComment(model as any, pos(1, 16))).toBe(true)
  })

  it('handles nested-looking /* inside line comment (-- /* no block)', () => {
    const model = mockModel('-- /* this is still a line comment')
    // column 10 = inside line comment; /* should NOT open a block here
    expect(isInComment(model as any, pos(1, 10))).toBe(true)
  })
})
