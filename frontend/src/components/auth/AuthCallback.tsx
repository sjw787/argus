import { useEffect } from 'react'
import { useAuthStore } from '../../stores/authStore'

/**
 * Handles the Cognito hosted UI redirect back to /auth/callback.
 * The access token is in the URL hash: #access_token=...&token_type=Bearer&...
 * On success, marks authenticated and navigates to the root.
 */
export function AuthCallback() {
  const { setAuthenticated } = useAuthStore()

  useEffect(() => {
    const hash = window.location.hash.slice(1)
    const params = new URLSearchParams(hash)
    const token = params.get('access_token')
    if (token) {
      // Store the Cognito token so axios interceptor can attach it if needed.
      sessionStorage.setItem('cognito_access_token', token)
      setAuthenticated(true)
    }
    // Navigate to root regardless — if no token, App will show login again
    window.history.replaceState(null, '', '/')
  }, [setAuthenticated])

  return (
    <div className="fixed inset-0 flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <span className="text-sm animate-pulse" style={{ color: 'var(--text-muted)' }}>Completing sign-in…</span>
    </div>
  )
}
