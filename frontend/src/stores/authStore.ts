import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthStore {
  authenticated: boolean
  profile: string | null
  region: string | null
  profiles: string[]
  sessionExpired: boolean
  lastAuthTime: number
  credentialId: string | null  // Lambda SSO mode: sent as X-Credential-Id header
  setAuth: (profile: string | null, region: string | null, credentialId?: string | null) => void
  setAuthenticated: (v: boolean) => void
  setProfiles: (profiles: string[]) => void
  setSessionExpired: (v: boolean) => void
  clear: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      authenticated: false,
      profile: null,
      region: null,
      profiles: [],
      sessionExpired: false,
      lastAuthTime: 0,
      credentialId: null,
      setAuth: (profile, region, credentialId = null) =>
        set({ authenticated: true, profile, region, credentialId, sessionExpired: false, lastAuthTime: Date.now() }),
      setAuthenticated: (authenticated) => set({ authenticated }),
      setProfiles: (profiles) => set({ profiles }),
      setSessionExpired: (sessionExpired) => set({ sessionExpired }),
      clear: () => set({ authenticated: false, profile: null, region: null, credentialId: null, sessionExpired: false, lastAuthTime: 0 }),
    }),
    {
      name: 'argus-auth',
      partialize: (state) => ({
        authenticated: state.authenticated,
        profile: state.profile,
        region: state.region,
        profiles: state.profiles,
        sessionExpired: state.sessionExpired,
        credentialId: state.credentialId,
        // lastAuthTime is not persisted — always reset to 0 on page load
      }),
    }
  )
)
