import { useEffect, useState } from 'react'
import { AppLayout } from './components/layout/AppLayout'
import { SsoLoginDialog } from './components/auth/SsoLoginDialog'
import { CognitoLoginDialog } from './components/auth/CognitoLoginDialog'
import { AuthCallback } from './components/auth/AuthCallback'
import { useAuthStore } from './stores/authStore'
import { useAuthConfigStore } from './hooks/useAuthConfig'
import { api } from './api/client'

export default function App() {
  const { authenticated, profile, region, sessionExpired, setAuthenticated, setProfiles, setSessionExpired } = useAuthStore()
  const { config: authConfig, loaded: configLoaded, fetchConfig } = useAuthConfigStore()
  const [checking, setChecking] = useState(true)

  // Fetch auth/feature config first, then verify credentials
  useEffect(() => {
    fetchConfig().finally(() => {
      api.getAuthStatus(profile ?? undefined, region ?? undefined)
        .then(status => {
          setProfiles(status.profiles)
          setAuthenticated(status.authenticated)
        })
        .catch(() => setAuthenticated(false))
        .finally(() => setChecking(false))
    })
  }, [])

  // Handle Cognito /auth/callback route before rendering anything else
  if (window.location.pathname === '/auth/callback') {
    return <AuthCallback />
  }

  if (checking || !configLoaded) {
    return (
      <div className="fixed inset-0 flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
        <span className="text-sm animate-pulse" style={{ color: 'var(--text-muted)' }}>Connecting…</span>
      </div>
    )
  }

  const mode = authConfig?.mode ?? 'sso'

  // mode=none: skip login entirely — user is pre-authenticated
  if (mode === 'none') {
    return <AppLayout />
  }

  // mode=cognito: show Cognito hosted UI redirect button
  if (mode === 'cognito' && (!authenticated || sessionExpired)) {
    return <CognitoLoginDialog config={authConfig!} />
  }

  // mode=sso (default): original SSO login dialog
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

