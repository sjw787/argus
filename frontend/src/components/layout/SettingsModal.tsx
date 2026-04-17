import { useState } from 'react'
import { X, Moon, Sun, Zap, History, AlertCircle, Database, AlignLeft, Sliders, Palette, Plug, Lock, LogOut, User } from 'lucide-react'
import { useThemeStore } from '../../stores/themeStore'
import { useAuthStore } from '../../stores/authStore'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

interface Props {
  onClose: () => void
}

type Section = 'appearance' | 'editor' | 'connection' | 'account'

const NAV_ITEMS: { id: Section; label: string; icon: React.ReactNode }[] = [
  { id: 'appearance', label: 'Appearance', icon: <Palette size={15} /> },
  { id: 'editor', label: 'Editor', icon: <Sliders size={15} /> },
  { id: 'connection', label: 'AWS Connection', icon: <Plug size={15} /> },
  { id: 'account', label: 'Account', icon: <User size={15} /> },
]

function Toggle({ on, onToggle, locked }: { on: boolean; onToggle: () => void; locked?: boolean }) {
  return (
    <div
      onClick={locked ? undefined : onToggle}
      style={{
        width: 36, height: 20,
        background: on ? (locked ? 'var(--text-muted)' : 'var(--accent)') : 'var(--border)',
        borderRadius: 999,
        padding: '2px',
        cursor: locked ? 'not-allowed' : 'pointer',
        flexShrink: 0,
        opacity: locked ? 0.6 : 1,
        position: 'relative',
        transition: 'background 0.15s',
      }}
    >
      <div style={{
        width: 16, height: 16,
        borderRadius: '50%',
        background: '#fff',
        transition: 'transform 0.15s',
        transform: on ? 'translateX(16px)' : 'translateX(0)',
      }} />
    </div>
  )
}

function AdminBadge() {
  return (
    <span
      className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        color: 'var(--text-muted)',
        whiteSpace: 'nowrap',
      }}
      title="This setting is controlled by your administrator"
    >
      <Lock size={10} />
      Admin
    </span>
  )
}

function SettingRow({ icon, label, description, children, locked }: {
  icon?: React.ReactNode
  label: string
  description?: string
  children: React.ReactNode
  locked?: boolean
}) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className="flex items-center justify-between px-3 py-2.5 rounded-lg"
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
          opacity: locked ? 0.75 : 1,
        }}
      >
        <div className="flex items-center gap-2">
          {icon && <span style={{ color: locked ? 'var(--text-muted)' : 'var(--accent)' }}>{icon}</span>}
          <span className="text-sm" style={{ color: 'var(--text-primary)' }}>{label}</span>
        </div>
        <div className="flex items-center gap-2">
          {locked && <AdminBadge />}
          {children}
        </div>
      </div>
      {description && (
        <p className="text-xs px-1" style={{ color: 'var(--text-muted)' }}>
          {locked ? '🔒 This setting is controlled by your administrator.' : description}
        </p>
      )}
    </div>
  )
}

export function SettingsModal({ onClose }: Props) {
  const [section, setSection] = useState<Section>('appearance')
  const [signingOut, setSigningOut] = useState(false)
  const {
    theme, setTheme,
    sqlAutocomplete, setSqlAutocomplete,
    sqlDiagnostics, setSqlDiagnostics,
    showHistoryDefault, setShowHistoryDefault,
    showInformationSchema, setShowInformationSchema,
    autoLimit, setAutoLimit,
    formatStyle, setFormatStyle,
  } = useThemeStore()
  const { profile, region, clear: clearAuth } = useAuthStore()
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: api.getConfig, staleTime: 60000 })
  const locked = new Set(config?.locked_settings ?? [])
  const isLocked = (key: string) => locked.has(key)

  async function handleSignOut() {
    setSigningOut(true)
    try {
      await api.signOut()
    } catch {
      // best-effort: clear client state regardless
    }
    clearAuth()
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="rounded-lg shadow-xl flex flex-col"
        style={{
          background: 'var(--bg-panel)',
          border: '1px solid var(--border)',
          width: 680,
          maxWidth: '95vw',
          maxHeight: '90vh',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3 flex-shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>Settings</span>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body: sidenav + content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Side nav */}
          <nav
            className="flex flex-col gap-0.5 p-3 flex-shrink-0"
            style={{ width: 168, borderRight: '1px solid var(--border)', background: 'var(--bg-secondary)' }}
          >
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                onClick={() => setSection(item.id)}
                className="flex items-center gap-2.5 px-3 py-2 rounded-md text-xs text-left w-full transition-colors"
                style={{
                  background: section === item.id ? 'var(--accent)' : 'transparent',
                  color: section === item.id ? '#fff' : 'var(--text-muted)',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: section === item.id ? 600 : 400,
                }}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>

          {/* Content pane */}
          <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
            {section === 'appearance' && (
              <>
                <div className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>Theme</div>
                {isLocked('theme') ? (
                  <div
                    className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm"
                    style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', opacity: 0.75 }}
                  >
                    <Lock size={13} style={{ color: 'var(--text-muted)' }} />
                    <span style={{ color: 'var(--text-muted)' }}>Theme is controlled by your administrator.</span>
                  </div>
                ) : (
                  <div className="flex gap-3">
                    {(['dark', 'light'] as const).map(t => (
                      <button
                        key={t}
                        onClick={() => setTheme(t)}
                        className="flex-1 flex flex-col items-center gap-2 py-4 rounded-lg text-xs transition-all"
                        style={{
                          background: theme === t ? 'var(--accent)' : 'var(--bg-secondary)',
                          color: theme === t ? '#fff' : 'var(--text-muted)',
                          border: `2px solid ${theme === t ? 'var(--accent)' : 'var(--border)'}`,
                          cursor: 'pointer',
                          fontWeight: theme === t ? 600 : 400,
                        }}
                      >
                        {t === 'dark' ? <Moon size={22} /> : <Sun size={22} />}
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}

            {section === 'editor' && (
              <>
                <SettingRow
                  icon={<Zap size={14} />}
                  label="SQL Autocomplete"
                  description="Keywords, functions, and table/column names from the active database"
                  locked={isLocked('sqlAutocomplete')}
                >
                  <Toggle on={sqlAutocomplete} onToggle={() => setSqlAutocomplete(!sqlAutocomplete)} locked={isLocked('sqlAutocomplete')} />
                </SettingRow>

                <SettingRow
                  icon={<AlertCircle size={14} />}
                  label="SQL Syntax Checking"
                  description="Underlines SQL syntax errors as you type (600 ms delay)"
                  locked={isLocked('sqlDiagnostics')}
                >
                  <Toggle on={sqlDiagnostics} onToggle={() => setSqlDiagnostics(!sqlDiagnostics)} locked={isLocked('sqlDiagnostics')} />
                </SettingRow>

                <SettingRow
                  icon={<History size={14} />}
                  label="Show Query History by Default"
                  description="Whether the Query History panel is visible when the app loads"
                  locked={isLocked('showHistoryDefault')}
                >
                  <Toggle on={showHistoryDefault} onToggle={() => setShowHistoryDefault(!showHistoryDefault)} locked={isLocked('showHistoryDefault')} />
                </SettingRow>

                <SettingRow
                  icon={<Database size={14} />}
                  label="Show information_schema"
                  description="Pin the information_schema virtual database at the top of the navigator"
                  locked={isLocked('showInformationSchema')}
                >
                  <Toggle on={showInformationSchema} onToggle={() => setShowInformationSchema(!showInformationSchema)} locked={isLocked('showInformationSchema')} />
                </SettingRow>

                <SettingRow
                  icon={<AlignLeft size={14} />}
                  label="Format Style"
                  description="Standard: each clause on its own line. Compact: tabular layout, keywords left-aligned."
                  locked={isLocked('formatStyle')}
                >
                  <div className="flex rounded overflow-hidden" style={{ border: '1px solid var(--border)', pointerEvents: isLocked('formatStyle') ? 'none' : 'auto', opacity: isLocked('formatStyle') ? 0.5 : 1 }}>
                    {(['standard', 'tabularLeft'] as const).map(style => (
                      <button
                        key={style}
                        onClick={() => setFormatStyle(style)}
                        className="px-2.5 py-1 text-xs"
                        style={{
                          background: formatStyle === style ? 'var(--accent)' : 'var(--bg-panel)',
                          color: formatStyle === style ? '#fff' : 'var(--text-muted)',
                          border: 'none',
                          cursor: isLocked('formatStyle') ? 'not-allowed' : 'pointer',
                          fontWeight: formatStyle === style ? 600 : 400,
                        }}
                      >
                        {style === 'standard' ? 'Standard' : 'Compact'}
                      </button>
                    ))}
                  </div>
                </SettingRow>

                <SettingRow
                  label="Auto-limit rows"
                  description="Appended to SELECT queries with no LIMIT. Set to 0 to disable."
                  locked={isLocked('autoLimit')}
                >
                  <input
                    type="number"
                    min={0}
                    step={100}
                    value={autoLimit}
                    disabled={isLocked('autoLimit')}
                    onChange={e => setAutoLimit(Math.max(0, parseInt(e.target.value) || 0))}
                    className="text-xs text-right rounded px-2 py-0.5 w-24"
                    style={{
                      background: 'var(--bg-panel)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border)',
                      outline: 'none',
                      cursor: isLocked('autoLimit') ? 'not-allowed' : 'auto',
                      opacity: isLocked('autoLimit') ? 0.5 : 1,
                    }}
                  />
                </SettingRow>
              </>
            )}

            {section === 'connection' && (
              <>
                <div className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
                  AWS Connection
                </div>
                {config ? (
                  <div className="rounded-lg overflow-hidden text-xs" style={{ border: '1px solid var(--border)' }}>
                    {[
                      ['Region', config.region],
                      ['Profile', config.profile ?? 'default'],
                      ['Active Schema', config.active_schema],
                      ['Config file', 'argus.yaml'],
                    ].map(([label, value], i, arr) => (
                      <div
                        key={label}
                        className="flex items-center justify-between px-3 py-2.5"
                        style={{ borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none' }}
                      >
                        <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                        <span style={{ color: 'var(--text-primary)', fontFamily: 'monospace' }}>{value}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Loading connection info…</p>
                )}
              </>
            )}

            {section === 'account' && (
              <>
                <div className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
                  Session
                </div>
                <div className="rounded-lg overflow-hidden text-xs" style={{ border: '1px solid var(--border)' }}>
                  {[
                    ['Profile', profile ?? '—'],
                    ['Region', region ?? '—'],
                  ].map(([label, value], i) => (
                    <div
                      key={label}
                      className="flex items-center justify-between px-3 py-2.5"
                      style={{ borderBottom: i === 0 ? '1px solid var(--border)' : 'none' }}
                    >
                      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                      <span style={{ color: 'var(--text-primary)', fontFamily: 'monospace' }}>{value}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-2">
                  <button
                    onClick={handleSignOut}
                    disabled={signingOut}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm w-full"
                    style={{
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border)',
                      color: signingOut ? 'var(--text-muted)' : '#ef4444',
                      cursor: signingOut ? 'not-allowed' : 'pointer',
                      transition: 'opacity 0.15s',
                    }}
                  >
                    <LogOut size={14} />
                    {signingOut ? 'Signing out…' : 'Sign Out'}
                  </button>
                  <p className="text-xs mt-1.5 px-1" style={{ color: 'var(--text-muted)' }}>
                    Clears your credentials and returns to the login screen.
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          className="px-5 py-3 text-xs flex items-center justify-between flex-shrink-0"
          style={{ borderTop: '1px solid var(--border)', color: 'var(--text-muted)' }}
        >
          <span>Argus for Athena</span>
          <a
            href="https://github.com/sjw787/argus"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5"
            style={{ color: 'var(--text-muted)', textDecoration: 'none' }}
            onMouseEnter={e => ((e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-primary)')}
            onMouseLeave={e => ((e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-muted)')}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.605-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            GitHub
          </a>
        </div>
      </div>
    </div>
  )
}
