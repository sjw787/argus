import { test, expect, Page } from '@playwright/test'

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Locate the Monaco editor's accessible textbox (native-edit-context API). */
function editorTextbox(page: Page) {
  return page.getByRole('textbox', { name: /editor content/i })
}

/** Wait for the editor to be ready and for __argus_editor to be populated. */
async function waitForEditor(page: Page) {
  await editorTextbox(page).waitFor({ state: 'visible', timeout: 30_000 })
  // Wait for the test handle to be set by handleEditorMount
  await page.waitForFunction(() => !!(window as unknown as Record<string, unknown>).__argus_editor, { timeout: 10_000 })
}

/**
 * Read the current editor content via Monaco's model API.
 * This is the authoritative source of truth — avoids DOM scraping of
 * .view-line elements, which suffers from virtual rendering, non-breaking
 * space normalization, and missing off-screen lines.
 */
async function getEditorValue(page: Page): Promise<string> {
  return page.evaluate(
    () =>
      (
        window as unknown as {
          __argus_editor?: { getValue(): string }
        }
      ).__argus_editor?.getValue() ?? ''
  )
}

/**
 * Set editor content via Monaco's model API, bypassing keyboard simulation.
 * This guarantees a clean, known starting state for each test regardless of
 * autocomplete, snippet state, or prior content.
 */
async function setEditorContent(page: Page, content: string) {
  await page.evaluate(
    (text) =>
      (
        window as unknown as {
          __argus_editor?: { setValue(v: string): void; focus(): void }
        }
      ).__argus_editor?.setValue(text),
    content
  )
  // Focus the editor so keyboard events land in the right target
  const tb = editorTextbox(page)
  await tb.click({ force: true })
}

/** Move the cursor to end of content so subsequent keystrokes append. */
async function moveCursorToEnd(page: Page) {
  await page.keyboard.press('ControlOrMeta+End')
}


async function triggerSuggest(page: Page) {
  await page.evaluate(() =>
    (
      window as unknown as {
        __argus_editor?: { trigger(s: string, h: string, p: unknown): void }
      }
    ).__argus_editor?.trigger('keyboard', 'editor.action.triggerSuggest', {})
  )
}

// ── Setup ─────────────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { localStorage.clear() })
  await page.goto('/')
  await waitForEditor(page)
})

// ── Spacebar tests ────────────────────────────────────────────────────────────

test('space inserts literal space in an empty editor', async ({ page }) => {
  await setEditorContent(page, '')
  await moveCursorToEnd(page)
  await page.keyboard.press('Space')

  const value = await getEditorValue(page)
  expect(value).toBe(' ')
})

test('space inserts literal space after a complete SQL keyword (SELECT)', async ({ page }) => {
  // This is the primary regression: typing "SELECT" opens the suggest widget;
  // space must insert a space, NOT collapse the keyword or accept a suggestion.
  await setEditorContent(page, 'SELECT')
  await moveCursorToEnd(page)

  // setValue() is programmatic so suggest doesn't auto-open — trigger it explicitly
  await triggerSuggest(page)
  const suggest = page.locator('.suggest-widget')
  await expect(suggest).toBeVisible({ timeout: 8_000 })

  await page.keyboard.press('Space')

  const value = await getEditorValue(page)
  // Must be exactly "SELECT " — no extra characters from an accepted suggestion
  expect(value).toBe('SELECT ')
  await expect(suggest).not.toBeVisible({ timeout: 1_500 })
})

test('space inserts literal space mid-token (SEL → SEL FROM)', async ({ page }) => {
  // Original regression: "SEL " produced "SELECT" or "SEL<keyword>" instead of "SEL ".
  await setEditorContent(page, 'SEL')
  await moveCursorToEnd(page)

  // setValue() is programmatic so suggest doesn't auto-open — trigger it explicitly
  await triggerSuggest(page)
  const suggest = page.locator('.suggest-widget')
  await expect(suggest).toBeVisible({ timeout: 8_000 })

  await page.keyboard.press('Space')
  await page.keyboard.type('FROM')

  const value = await getEditorValue(page)
  expect(value).toContain('SEL FROM')
  expect(value).not.toMatch(/SELECTFROM|SELECT FROM/)
})

test('multiple consecutive spaces all insert as literal spaces', async ({ page }) => {
  await setEditorContent(page, 'A')
  await moveCursorToEnd(page)

  await page.keyboard.press('Space')
  await page.keyboard.press('Space')
  await page.keyboard.press('Space')

  const value = await getEditorValue(page)
  expect(value).toBe('A   ')
})

test('space inserts correctly with no suggest widget open', async ({ page }) => {
  // "ZZZZ" triggers no SQL completions; space must still just insert a space.
  await setEditorContent(page, 'ZZZZ')
  await moveCursorToEnd(page)

  const suggest = page.locator('.suggest-widget')
  await expect(suggest).not.toBeVisible({ timeout: 2_000 })

  await page.keyboard.press('Space')

  const value = await getEditorValue(page)
  expect(value).toBe('ZZZZ ')
})

test('space inserts correctly at the start of a new line', async ({ page }) => {
  // Set a single-line query, then press Enter to open a new line, then Space.
  // Pressing Enter (not setValue with '\n') ensures the cursor is correctly
  // positioned on the new empty line before the Space keystroke.
  await setEditorContent(page, 'SELECT *')
  await moveCursorToEnd(page)
  await page.keyboard.press('Enter')
  await page.keyboard.press('Space')

  const value = await getEditorValue(page)
  // The second line must start with a space (indentation / alignment use case)
  const lines = value.split('\n')
  expect(lines.length).toBeGreaterThanOrEqual(2)
  expect(lines[1]).toMatch(/^\s/)
})

test('space in line comment inserts literal space and does not open autocomplete', async ({ page }) => {
  await setEditorContent(page, '-- comment')
  await moveCursorToEnd(page)
  await page.keyboard.press('Space')

  const value = await getEditorValue(page)
  expect(value).toBe('-- comment ')

  const suggest = page.locator('.suggest-widget')
  await expect(suggest).not.toBeVisible({ timeout: 1_500 })
})

test('space in block comment inserts literal space and does not open autocomplete', async ({ page }) => {
  await setEditorContent(page, '/* block comment')
  await moveCursorToEnd(page)
  await page.keyboard.press('Space')

  const value = await getEditorValue(page)
  expect(value).toBe('/* block comment ')

  const suggest = page.locator('.suggest-widget')
  await expect(suggest).not.toBeVisible({ timeout: 1_500 })
})

// ── Other editor tests ────────────────────────────────────────────────────────

test('autocomplete appears for SQL keywords', async ({ page }) => {
  await setEditorContent(page, 'SEL')
  await moveCursorToEnd(page)
  await triggerSuggest(page)

  const suggest = page.locator('.suggest-widget')
  await expect(suggest).toBeVisible({ timeout: 8_000 })
  await expect(suggest).toContainText('SELECT')
})

test('Format button reformats SQL', async ({ page }) => {
  const rawSql = 'select id,name,email,status,role,created_at from users where status=\'active\' and role=\'admin\' order by created_at desc'
  await setEditorContent(page, rawSql)

  const countBefore = await page.locator('.view-line').count()

  await expect(page.getByRole('button', { name: /format/i }).first()).not.toBeDisabled()
  await page.getByRole('button', { name: /format/i }).first().click()

  // After formatting, the visible Monaco editor gains more view-line elements
  // because the multi-line formatted output exceeds the phantom line buffer.
  await expect.poll(() => page.locator('.view-line').count(), { timeout: 5_000 })
    .toBeGreaterThan(countBefore)
})

test('export buttons visible when allow_download is true', async ({ page }) => {
  await page.locator('button:visible').filter({ hasText: /select database/i }).click()
  await page.waitForSelector('input[placeholder*="Search"]', { timeout: 5_000 })
  await page.waitForSelector('text=test_db', { timeout: 5_000 })
  await page.getByText('test_db').click()
  await expect(page.locator('button:visible').filter({ hasText: /test_db/ })).toBeVisible({ timeout: 3_000 })

  await setEditorContent(page, 'SELECT 1')

  await page.locator('button:visible').filter({ hasText: /^run$/i }).click()

  await expect(page.locator('button', { hasText: 'CSV' })).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('button', { hasText: 'JSON' })).toBeVisible()
})

