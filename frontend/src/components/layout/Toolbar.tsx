import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { Database, Settings } from 'lucide-react'
import { SettingsModal } from './SettingsModal'

export function Toolbar() {
  const [showSettings, setShowSettings] = useState(false)
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: api.getConfig,
    staleTime: 60000,
  })

  return (
    <>
      <header
        className="flex items-center justify-between px-4 h-10 shrink-0 border-b"
        style={{ background: 'var(--bg-secondary)', borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <Database size={18} style={{ color: 'var(--accent)' }} />
          <span className="font-bold text-sm" style={{ color: 'var(--text-primary)' }}>
            AthenaBeaver
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
          {config && (
            <>
              <span>Region: <strong style={{ color: 'var(--text-primary)' }}>{config.region}</strong></span>
              <span>Profile: <strong style={{ color: 'var(--text-primary)' }}>{config.profile ?? 'default'}</strong></span>
              <span>Schema: <strong style={{ color: 'var(--accent)' }}>{config.active_schema}</strong></span>
            </>
          )}
          <button
            onClick={() => setShowSettings(true)}
            title="Settings"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 2, display: 'flex', alignItems: 'center' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <Settings size={14} style={{ color: 'inherit' }} />
          </button>
        </div>
      </header>
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </>
  )
}
