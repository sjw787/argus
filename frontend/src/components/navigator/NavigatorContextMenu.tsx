import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

export interface MenuAction {
  label: string
  icon?: React.ReactNode
  onClick: () => void
  separator?: boolean
}

interface Props {
  x: number
  y: number
  actions: MenuAction[]
  onClose: () => void
}

export function NavigatorContextMenu({ x, y, actions, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [onClose])

  // Clamp to viewport so menu doesn't overflow the bottom/right
  const adjustedY = Math.min(y, window.innerHeight - actions.length * 32 - 16)
  const adjustedX = Math.min(x, window.innerWidth - 200)

  return createPortal(
    <div
      ref={ref}
      style={{
        position: 'fixed',
        top: adjustedY,
        left: adjustedX,
        zIndex: 9999,
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        minWidth: 190,
        padding: '4px 0',
        fontSize: 12,
      }}
    >
      {actions.map((action, i) =>
        action.separator ? (
          <div key={i} style={{ borderTop: '1px solid var(--border)', margin: '4px 0' }} />
        ) : (
          <button
            key={i}
            onClick={() => { action.onClick(); onClose() }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              width: '100%',
              padding: '6px 14px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-primary)',
              textAlign: 'left',
              fontSize: 12,
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            {action.icon && <span style={{ opacity: 0.7 }}>{action.icon}</span>}
            {action.label}
          </button>
        )
      )}
    </div>,
    document.body
  )
}
