import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { SsoAccount, SsoRole } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { AlertTriangle, CheckCircle, ExternalLink, Loader, LogIn } from 'lucide-react'

type Step = 'entry' | 'waiting' | 'accounts' | 'roles' | 'profile' | 'done'

interface Props {
  onAuthenticated: () => void
  expired?: boolean
}

const DEFAULT_REGIONS = [
  'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
  'eu-west-1', 'eu-west-2', 'eu-central-1',
  'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1',
]

export function SsoLoginDialog({ onAuthenticated, expired = false }: Props) {
  const setAuth = useAuthStore(s => s.setAuth)
  const setProfiles = useAuthStore(s => s.setProfiles)
  const storedProfile = useAuthStore(s => s.profile)

  // Entry state
  const [startUrl, setStartUrl] = useState('')
  const [region, setRegion] = useState('us-east-1')
  const [existingProfiles, setExistingProfiles] = useState<string[]>([])

  // SSO session state
  const [sessionId, setSessionId] = useState('')
  const [userCode, setUserCode] = useState('')
  const [verifyUrlComplete, setVerifyUrlComplete] = useState('')
  const [pollInterval, setPollInterval] = useState(5)

  // Account / role selection
  const [accounts, setAccounts] = useState<SsoAccount[]>([])
  const [selectedAccount, setSelectedAccount] = useState<SsoAccount | null>(null)
  const [roles, setRoles] = useState<SsoRole[]>([])
  const [selectedRole, setSelectedRole] = useState<SsoRole | null>(null)
  const [profileName, setProfileName] = useState(storedProfile ?? 'athena-beaver')

  const [step, setStep] = useState<Step>('entry')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load existing profiles and pre-fill SSO config on mount
  useEffect(() => {
    api.listProfiles().then(setExistingProfiles).catch(() => {})
    api.getSsoConfig().then(cfg => {
      if (cfg.start_url) setStartUrl(cfg.start_url)
      if (cfg.region) setRegion(cfg.region)
    }).catch(() => {})
  }, [])


  // Poll until user completes browser auth
  useEffect(() => {
    if (step !== 'waiting' || !sessionId) return

    pollRef.current = setInterval(async () => {
      try {
        const resp = await api.ssoPoll(sessionId)
        if (resp.status === 'success' && resp.access_token) {
          clearInterval(pollRef.current!)
          setLoading(true)
          const accts = await api.ssoListAccounts(sessionId)
          setAccounts(accts)
          setLoading(false)
          setStep('accounts')
        } else if (resp.status === 'expired' || resp.status === 'denied') {
          clearInterval(pollRef.current!)
          setError(resp.status === 'expired' ? 'Login expired. Please try again.' : 'Login was denied.')
          setStep('entry')
        }
      } catch {
        // ignore transient poll errors
      }
    }, pollInterval * 1000)

    return () => clearInterval(pollRef.current!)
  }, [step, sessionId, pollInterval])

  const handleStartSso = async () => {
    if (!startUrl.trim()) { setError('Enter your SSO start URL.'); return }
    setError('')
    setLoading(true)
    try {
      const resp = await api.ssoStart(startUrl.trim(), region)
      setSessionId(resp.session_id)
      setUserCode(resp.user_code)
      setVerifyUrlComplete(resp.verification_uri_complete)
      setPollInterval(resp.interval)
      setStep('waiting')
      // Auto-open browser
      window.open(resp.verification_uri_complete, '_blank')
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to start SSO.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectAccount = async (account: SsoAccount) => {
    setSelectedAccount(account)
    setLoading(true)
    try {
      const r = await api.ssoListRoles(sessionId, account.account_id)
      setRoles(r)
      if (r.length === 1) {
        setSelectedRole(r[0])
        setStep('profile')
      } else {
        setStep('roles')
      }
    } catch {
      setError('Failed to load roles.')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectRole = (role: SsoRole) => {
    setSelectedRole(role)
    setStep('profile')
  }

  const handleSaveProfile = async () => {
    if (!selectedAccount || !selectedRole) return
    setLoading(true)
    setError('')
    try {
      const resp = await api.ssoSelectRole(sessionId, selectedAccount.account_id, selectedRole.role_name, profileName)
      const profiles = await api.listProfiles()
      setProfiles(profiles)
      setAuth(resp.profile_name, region)
      setStep('done')
      setTimeout(onAuthenticated, 1200)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to save credentials.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleUseExistingProfile = async (profile: string) => {
    setLoading(true)
    setError('')
    try {
      await api.selectProfile(profile)
      setAuth(profile, region)
      const profiles = await api.listProfiles()
      setProfiles(profiles)
      onAuthenticated()
    } catch {
      setError(`Profile '${profile}' has no valid credentials. Try signing in again.`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'rgba(0,0,0,0.85)' }}
    >
      <div
        className="w-full max-w-md rounded-xl shadow-2xl p-0 overflow-hidden"
        style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)' }}
      >
        {/* Header */}
        <div className="px-6 py-4" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center gap-2">
            <LogIn size={18} style={{ color: 'var(--accent)' }} />
            <h2 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
              {expired ? 'Session Expired' : 'Sign in to AWS'}
            </h2>
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {step === 'entry' && (expired ? 'Your AWS session has expired — please sign in again' : 'Connect via AWS IAM Identity Center (SSO)')}
            {step === 'waiting' && 'Complete sign-in in your browser'}
            {step === 'accounts' && 'Select an AWS account'}
            {step === 'roles' && 'Select an IAM role'}
            {step === 'profile' && 'Save credentials as a profile'}
            {step === 'done' && 'Signed in successfully!'}
          </p>
        </div>

        <div className="px-6 py-5 space-y-4">

          {/* ── Expiry banner ── */}
          {expired && step === 'entry' && (
            <div
              className="flex items-start gap-2 px-3 py-2.5 rounded text-xs"
              style={{ background: 'color-mix(in srgb, var(--warning) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--warning) 40%, transparent)', color: 'var(--warning)' }}
            >
              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              <span>Your AWS credentials have expired. Sign in with SSO to continue.</span>
            </div>
          )}

          {/* ── Step: entry ── */}
          {step === 'entry' && (
            <>
              {existingProfiles.length > 0 && (
                <div>
                  <p className="text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
                    Existing profiles
                  </p>
                  <div className="space-y-1">
                    {existingProfiles.map(p => (
                      <button
                        key={p}
                        onClick={() => handleUseExistingProfile(p)}
                        disabled={loading}
                        className="w-full text-left px-3 py-2 rounded text-sm transition-colors"
                        style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border)', cursor: 'pointer' }}
                        onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
                        onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 my-3">
                    <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>or sign in fresh</span>
                    <div className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
                  SSO Start URL
                </label>
                <input
                  className="w-full px-3 py-2 rounded text-sm outline-none"
                  style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                  placeholder="https://my-org.awsapps.com/start"
                  value={startUrl}
                  onChange={e => setStartUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleStartSso()}
                  onFocus={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
                  onBlur={e => (e.currentTarget.style.borderColor = 'var(--border)')}
                />
              </div>

              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
                  AWS Region
                </label>
                <select
                  className="w-full px-3 py-2 rounded text-sm outline-none"
                  style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border)', cursor: 'pointer' }}
                  value={region}
                  onChange={e => setRegion(e.target.value)}
                >
                  {DEFAULT_REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>

              {error && <p className="text-xs" style={{ color: 'var(--error)' }}>{error}</p>}

              <button
                onClick={handleStartSso}
                disabled={loading}
                className="w-full py-2 rounded text-sm font-medium flex items-center justify-center gap-2"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)', border: 'none', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1 }}
              >
                {loading ? <Loader size={14} className="animate-spin" /> : <LogIn size={14} />}
                Sign in with SSO
              </button>
            </>
          )}

          {/* ── Step: waiting ── */}
          {step === 'waiting' && (
            <div className="space-y-4">
              <div className="text-center">
                <div
                  className="inline-block px-4 py-2 rounded font-mono text-lg font-bold tracking-widest mb-2"
                  style={{ background: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--accent)' }}
                >
                  {userCode}
                </div>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Enter this code in the browser window that opened
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Loader size={14} className="animate-spin shrink-0" style={{ color: 'var(--accent)' }} />
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Waiting for you to complete sign-in…
                </p>
              </div>

              <div className="flex gap-2">
                <a
                  href={verifyUrlComplete}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs underline"
                  style={{ color: 'var(--accent)' }}
                >
                  <ExternalLink size={11} /> Reopen browser
                </a>
                <span style={{ color: 'var(--text-muted)' }}>·</span>
                <button
                  onClick={() => { setStep('entry'); setError('') }}
                  className="text-xs"
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  Cancel
                </button>
              </div>

              {error && <p className="text-xs" style={{ color: 'var(--error)' }}>{error}</p>}
            </div>
          )}

          {/* ── Step: accounts ── */}
          {step === 'accounts' && (
            <div className="space-y-2">
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                {accounts.length} account{accounts.length !== 1 ? 's' : ''} available
              </p>
              <div className="space-y-1 max-h-56 overflow-y-auto">
                {accounts.map(a => (
                  <button
                    key={a.account_id}
                    onClick={() => handleSelectAccount(a)}
                    disabled={loading}
                    className="w-full text-left px-3 py-2.5 rounded text-sm transition-colors"
                    style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', cursor: 'pointer' }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
                  >
                    <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{a.account_name}</div>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{a.account_id} · {a.email}</div>
                  </button>
                ))}
              </div>
              {loading && <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}><Loader size={12} className="animate-spin" /> Loading roles…</div>}
              {error && <p className="text-xs" style={{ color: 'var(--error)' }}>{error}</p>}
            </div>
          )}

          {/* ── Step: roles ── */}
          {step === 'roles' && selectedAccount && (
            <div className="space-y-2">
              <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                Roles for <strong style={{ color: 'var(--text-primary)' }}>{selectedAccount.account_name}</strong>
              </p>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {roles.map(r => (
                  <button
                    key={r.role_name}
                    onClick={() => handleSelectRole(r)}
                    className="w-full text-left px-3 py-2 rounded text-sm"
                    style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border)', cursor: 'pointer' }}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
                  >
                    {r.role_name}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setStep('accounts')}
                className="text-xs"
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                ← Back
              </button>
            </div>
          )}

          {/* ── Step: profile name ── */}
          {step === 'profile' && selectedAccount && selectedRole && (
            <div className="space-y-3">
              <div className="p-3 rounded text-xs space-y-1" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                <div><span style={{ color: 'var(--text-muted)' }}>Account:</span> <strong style={{ color: 'var(--text-primary)' }}>{selectedAccount.account_name}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Role:</span> <strong style={{ color: 'var(--text-primary)' }}>{selectedRole.role_name}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Region:</span> <strong style={{ color: 'var(--text-primary)' }}>{region}</strong></div>
              </div>

              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
                  Save as profile name
                </label>
                <input
                  className="w-full px-3 py-2 rounded text-sm outline-none"
                  style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}
                  value={profileName}
                  onChange={e => setProfileName(e.target.value)}
                  onFocus={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
                  onBlur={e => (e.currentTarget.style.borderColor = 'var(--border)')}
                />
              </div>

              {error && <p className="text-xs" style={{ color: 'var(--error)' }}>{error}</p>}

              <div className="flex gap-2">
                <button
                  onClick={() => setStep(roles.length > 1 ? 'roles' : 'accounts')}
                  className="flex-1 py-2 rounded text-sm"
                  style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer' }}
                >
                  Back
                </button>
                <button
                  onClick={handleSaveProfile}
                  disabled={loading || !profileName.trim()}
                  className="flex-1 py-2 rounded text-sm font-medium flex items-center justify-center gap-2"
                  style={{ background: 'var(--accent)', color: 'var(--bg-primary)', border: 'none', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1 }}
                >
                  {loading ? <Loader size={14} className="animate-spin" /> : null}
                  Save & Connect
                </button>
              </div>
            </div>
          )}

          {/* ── Step: done ── */}
          {step === 'done' && (
            <div className="flex flex-col items-center py-4 gap-3">
              <CheckCircle size={36} style={{ color: 'var(--success)' }} />
              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Signed in!</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Opening AthenaBeaver…</p>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
