import { useEffect, useState } from 'react'
import { AppLayout } from './components/layout/AppLayout'
import { SsoLoginDialog } from './components/auth/SsoLoginDialog'
import { useAuthStore } from './stores/authStore'
import { api } from './api/client'

export default function App() {
  const { authenticated, profile, region, sessionExpired, setAuthenticated, setProfiles, setSessionExpired } = useAuthStore()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    // On load, verify stored credentials are still valid
    api.getAuthStatus(profile ?? undefined, region ?? undefined)
      .then(status => {
        setProfiles(status.profiles)
        setAuthenticated(status.authenticated)
      })
      .catch(() => setAuthenticated(false))
      .finally(() => setChecking(false))
  }, [])

  if (checking) {
    return (
      <div className="fixed inset-0 flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
        <span className="text-sm animate-pulse" style={{ color: 'var(--text-muted)' }}>Connecting…</span>
      </div>
    )
  }

  const showLogin = !authenticated || sessionExpired

  return (
    <>
      {showLogin && (
        <SsoLoginDialog
          expired={sessionExpired}
          onAuthenticated={() => { setAuthenticated(true); setSessionExpired(false) }}
        />
      )}
      <AppLayout />
    </>
  )
}

