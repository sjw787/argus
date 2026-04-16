import { create } from 'zustand'

interface UIStore {
  sidebarWidth: number
  bottomPanelHeight: number
  bottomTab: 'history' | 'active' | 'messages'
  showErDiagram: boolean
  selectedDatabase: string | null
  selectedTable: string | null
  setSidebarWidth: (w: number) => void
  setBottomPanelHeight: (h: number) => void
  setBottomTab: (tab: 'history' | 'active' | 'messages') => void
  setShowErDiagram: (show: boolean) => void
  setSelectedDatabase: (db: string | null) => void
  setSelectedTable: (table: string | null) => void
}

export const useUIStore = create<UIStore>(set => ({
  sidebarWidth: 280,
  bottomPanelHeight: 200,
  bottomTab: 'history',
  showErDiagram: false,
  selectedDatabase: null,
  selectedTable: null,
  setSidebarWidth: sidebarWidth => set({ sidebarWidth }),
  setBottomPanelHeight: bottomPanelHeight => set({ bottomPanelHeight }),
  setBottomTab: bottomTab => set({ bottomTab }),
  setShowErDiagram: showErDiagram => set({ showErDiagram }),
  setSelectedDatabase: selectedDatabase => set({ selectedDatabase }),
  setSelectedTable: selectedTable => set({ selectedTable }),
}))
