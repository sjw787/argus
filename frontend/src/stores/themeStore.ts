import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'dark' | 'light'
export type FormatStyle = 'standard' | 'tabularLeft'

interface ThemeStore {
  theme: Theme
  sqlAutocomplete: boolean
  sqlDiagnostics: boolean
  showHistoryDefault: boolean
  showInformationSchema: boolean
  autoLimit: number
  formatStyle: FormatStyle
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  setSqlAutocomplete: (v: boolean) => void
  setSqlDiagnostics: (v: boolean) => void
  setShowHistoryDefault: (v: boolean) => void
  setShowInformationSchema: (v: boolean) => void
  setAutoLimit: (v: number) => void
  setFormatStyle: (v: FormatStyle) => void
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      sqlAutocomplete: true,
      sqlDiagnostics: true,
      showHistoryDefault: true,
      showInformationSchema: true,
      autoLimit: 500,
      formatStyle: 'standard' as FormatStyle,
      setTheme: (theme) => {
        set({ theme })
        document.documentElement.setAttribute('data-theme', theme)
      },
      toggleTheme: () => {
        const next = get().theme === 'dark' ? 'light' : 'dark'
        get().setTheme(next)
      },
      setSqlAutocomplete: (sqlAutocomplete) => set({ sqlAutocomplete }),
      setSqlDiagnostics: (sqlDiagnostics) => set({ sqlDiagnostics }),
      setShowHistoryDefault: (showHistoryDefault) => set({ showHistoryDefault }),
      setShowInformationSchema: (showInformationSchema) => set({ showInformationSchema }),
      setAutoLimit: (autoLimit) => set({ autoLimit }),
      setFormatStyle: (formatStyle) => set({ formatStyle }),
    }),
    { name: 'argus-theme' }
  )
)

/** Call once on app init to apply the persisted theme before first render. */
export function applyPersistedTheme() {
  const stored = localStorage.getItem('argus-theme')
  if (stored) {
    try {
      const { state } = JSON.parse(stored)
      if (state?.theme) document.documentElement.setAttribute('data-theme', state.theme)
    } catch { /* ignore */ }
  }
}
