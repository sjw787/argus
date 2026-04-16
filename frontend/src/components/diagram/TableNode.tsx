import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { ColumnItem } from '../../api/client'

interface TableNodeData {
  name: string
  columns: ColumnItem[]
  partition_keys: ColumnItem[]
  [key: string]: unknown
}

export function TableNode({ data }: NodeProps) {
  const d = data as TableNodeData
  return (
    <div
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        minWidth: 200,
        fontSize: 11,
        boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#89b4fa' }} />
      <div
        className="px-3 py-1.5 font-bold text-xs"
        style={{ background: 'var(--accent)', color: 'var(--bg-primary)', borderRadius: '5px 5px 0 0' }}
      >
        {d.name}
      </div>
      <div className="px-2 py-1">
        {d.columns.map(col => (
          <div key={col.name} className="flex items-center gap-2 py-0.5" style={{ color: 'var(--text-primary)' }}>
            <span className="flex-1 truncate">{col.name}</span>
            <span className="text-xs opacity-50">{col.type}</span>
          </div>
        ))}
        {d.partition_keys.length > 0 && (
          <>
            <div className="text-xs font-medium mt-1 mb-0.5" style={{ color: 'var(--warning)' }}>Partitions</div>
            {d.partition_keys.map(col => (
              <div key={col.name} className="flex items-center gap-2 py-0.5" style={{ color: 'var(--warning)' }}>
                <span className="flex-1 truncate">{col.name}</span>
                <span className="text-xs opacity-50">{col.type}</span>
              </div>
            ))}
          </>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ background: '#89b4fa' }} />
    </div>
  )
}
