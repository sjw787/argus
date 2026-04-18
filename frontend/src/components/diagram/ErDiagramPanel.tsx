import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState, BackgroundVariant,
} from '@xyflow/react'
import type { Node, Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api } from '../../api/client'
import type { ErDiagramData } from '../../api/client'
import { TableNode as TableNodeComponent } from './TableNode'

const nodeTypes = { tableNode: TableNodeComponent }

function buildLayout(data: ErDiagramData): { nodes: Node[]; edges: Edge[] } {
  const COLS = 3
  // Match TableNode: minWidth 200, but long type names ("varchar(255)", "decimal(38,10)")
  // and table names can push the rendered width well past that. Reserve generously.
  const CARD_WIDTH = 280
  // Per-row vertical sizing — header + 1 line per column + partition header + bottom padding.
  // The previous 80 + 20*N underestimated the rendered ~24px row + ~32px header,
  // so tables overlapped each other vertically.
  const HEADER_PX = 36
  const ROW_PX = 24
  const PARTITION_HEADER_PX = 24
  const FOOTER_PX = 16
  const GAP_X = 100
  const GAP_Y = 80

  const heightOf = (n: ErDiagramData['nodes'][number]) =>
    HEADER_PX +
    n.columns.length * ROW_PX +
    (n.partition_keys.length > 0 ? PARTITION_HEADER_PX + n.partition_keys.length * ROW_PX : 0) +
    FOOTER_PX

  // First pass: compute the max height per row so a single tall table doesn't
  // bleed into the row below it.
  const rowHeights: number[] = []
  data.nodes.forEach((n, i) => {
    const row = Math.floor(i / COLS)
    const h = heightOf(n)
    rowHeights[row] = Math.max(rowHeights[row] ?? 0, h)
  })

  // Cumulative Y offset for each row (sum of previous row heights + gaps).
  const rowOffsets: number[] = []
  rowHeights.reduce((acc, h, idx) => {
    rowOffsets[idx] = acc
    return acc + h + GAP_Y
  }, 0)

  const nodes: Node[] = data.nodes.map((n, i) => {
    const col = i % COLS
    const row = Math.floor(i / COLS)
    return {
      id: n.id,
      type: 'tableNode',
      position: { x: col * (CARD_WIDTH + GAP_X), y: rowOffsets[row] },
      data: { name: n.name, columns: n.columns, partition_keys: n.partition_keys },
    }
  })

  const edges: Edge[] = data.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source_table,
    target: e.target_table,
    label: `${e.source_column} → ${e.target_column}`,
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#89b4fa', strokeWidth: 1.5 },
    labelStyle: { fill: '#6c7086', fontSize: 10 },
  }))

  return { nodes, edges }
}

export function ErDiagramPanel({ databaseName }: { databaseName: string }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const { data, isFetching } = useQuery({
    queryKey: ['erDiagram', databaseName],
    queryFn: () => api.getErDiagram(databaseName),
    staleTime: 60000,
  })

  useEffect(() => {
    if (data) {
      const { nodes: n, edges: e } = buildLayout(data)
      setNodes(n)
      setEdges(e)
    }
  }, [data])

  if (isFetching) {
    return (
      <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--text-muted)' }}>
        Loading ER diagram...
      </div>
    )
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm" style={{ color: 'var(--text-muted)' }}>
        No tables found in {databaseName}
      </div>
    )
  }

  return (
    <div style={{ width: '100%', height: '100%', background: 'var(--bg-primary)' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} color="#3a3a55" gap={20} />
        <Controls style={{ bottom: 48 }} />
        <MiniMap style={{ background: 'var(--bg-secondary)' }} nodeColor="#89b4fa" />
      </ReactFlow>
    </div>
  )
}
