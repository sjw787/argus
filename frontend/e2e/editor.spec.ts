import { test, expect, Page } from '@playwright/test'

// Locate the Monaco editor's accessible textbox (native-edit-context API)
function editorTextbox(page: Page) {
  return page.getByRole('textbox', { name: /editor content/i })
}

// Wait for the editor to be ready
async function waitForEditor(page: Page) {
  await editorTextbox(page).waitFor({ state: 'visible', timeout: 30_000 })
}

// Focus the editor and set content (select all, then type)
async function setEditorContent(page: Page, content: string) {
  const tb = editorTextbox(page)
  // Monaco's view-line divs intercept pointer events; force the click to bypass
  await tb.click({ force: true })
  await page.keyboard.press('ControlOrMeta+A')
  await page.keyboard.type(content)
}

test.beforeEach(async ({ page }) => {
  // Clear persisted Zustand editor state (localStorage) so each test starts
  // with a single empty tab regardless of what previous tests left behind.
  await page.addInitScript(() => {
    localStorage.clear()
  })
  await page.goto('/')
  await waitForEditor(page)
})

test('spacebar in line comment does not open autocomplete', async ({ page }) => {
  await setEditorContent(page, '-- this is a comment')

  // Dismiss any autocomplete that may have opened while typing
  await page.keyboard.press('Escape')

  await page.keyboard.press('Space')

  // Suggest widget must not be visible after typing a space in a comment
  const suggest = page.locator('.suggest-widget')
  await expect(suggest).not.toBeVisible({ timeout: 2_000 })
})

test('spacebar in block comment does not open autocomplete', async ({ page }) => {
  await setEditorContent(page, '/* block comment')

  await page.keyboard.press('Escape')
  await page.keyboard.press('Space')

  const suggest = page.locator('.suggest-widget')
  await expect(suggest).not.toBeVisible({ timeout: 2_000 })
})

test('spacebar always inserts a literal space, even when suggest widget is open', async ({ page }) => {
  // Regression: Monaco's default `acceptSuggestionOnCommitCharacter: true` made
  // space accept the highlighted SQL keyword instead of inserting a space, so
  // typing "SEL " produced "SELECT" or "SEL<keyword>" instead of "SEL ".
  await setEditorContent(page, 'SEL')

  // Wait for the suggest widget to appear so we exercise the commit-character path
  const suggest = page.locator('.suggest-widget')
  await expect(suggest).toBeVisible({ timeout: 8_000 })

  // Now press space — it must insert a literal space, NOT accept the highlighted suggestion
  await page.keyboard.press('Space')
  await page.keyboard.type('FROM')

  // Read the editor's full text via DOM (concatenate all .view-line spans).
  // Use evaluate so we can wait for Monaco to render after the keystrokes.
  const editorValue = await page.evaluate(() => {
    const lines = Array.from(document.querySelectorAll('.view-line'))
    // Monaco renders spaces as non-breaking spaces (U+00A0) for layout; normalize.
    return lines.map(l => (l as HTMLElement).innerText.replace(/\u00A0/g, ' ')).join('\n').trim()
  })
  expect(editorValue).toContain('SEL FROM')
  expect(editorValue).not.toMatch(/SELECTFROM|SELECT FROM/)
})

test('autocomplete appears for SQL keywords', async ({ page }) => {
  await setEditorContent(page, 'SEL')

  const suggest = page.locator('.suggest-widget')
  await expect(suggest).toBeVisible({ timeout: 8_000 })
  await expect(suggest).toContainText('SELECT')
})

test('Format button reformats SQL', async ({ page }) => {
  // Use a multi-column query so the formatted output has 10+ lines,
  // guaranteeing it exceeds Monaco's pre-rendered phantom line count (~8).
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
  // With React StrictMode the store may contain 2 tabs; the inactive tab's
  // elements are inside display:none. Use :visible to find only the rendered one.
  await page.locator('button:visible').filter({ hasText: /select database/i }).click()
  // Wait for the dropdown's search input to appear
  await page.waitForSelector('input[placeholder*="Search"]', { timeout: 5_000 })
  // Wait for test_db to load from the mocked API
  await page.waitForSelector('text=test_db', { timeout: 5_000 })
  await page.getByText('test_db').click()
  // Confirm picker now shows the selected database
  await expect(page.locator('button:visible').filter({ hasText: /test_db/ })).toBeVisible({ timeout: 3_000 })

  await setEditorContent(page, 'SELECT 1')

  // Run button should now be enabled (database + SQL set)
  await page.locator('button:visible').filter({ hasText: /^run$/i }).click()

  // MSW returns SUCCEEDED immediately so export buttons appear quickly
  await expect(page.locator('button', { hasText: 'CSV' })).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('button', { hasText: 'JSON' })).toBeVisible()
})
