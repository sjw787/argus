import { create } from 'zustand'
import { api } from '../api/client'
import type { AuthConfig } from '../api/client'

interface AuthConfigStore {
  config: AuthConfig | null
  loaded: boolean
  fetchConfig: () => Promise<void>
}

export const useAuthConfigStore = create<AuthConfigStore>((set) => ({
  config: null,
  loaded: false,
  fetchConfig: async () => {
    try {
      const config = await api.getAuthConfig()
      set({ config, loaded: true })
    } catch {
      // If the endpoint is missing (old backend), default to sso + streaming
      set({ config: { mode: 'sso', streaming: true }, loaded: true })
    }
  },
}))
