import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState, BackgroundVariant,
  Position,
} from '@xyflow/react'
import type { Node, Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import { api } from '../../api/client'
import type { ErDiagramData } from '../../api/client'
import { TableNode as TableNodeComponent } from './TableNode'

const nodeTypes = { tableNode: TableNodeComponent }

function buildLayout(data: ErDiagramData): { nodes: Node[]; edges: Edge[] } {
  // Approximate rendered sizes — match TableNode CSS
  const CARD_WIDTH = 280
  const HEADER_PX = 36
  const ROW_PX = 24
  const PARTITION_HEADER_PX = 24
  const FOOTER_PX = 16

  const heightOf = (n: ErDiagramData['nodes'][number]) =>
    HEADER_PX +
    n.columns.length * ROW_PX +
    (n.partition_keys.length > 0 ? PARTITION_HEADER_PX + n.partition_keys.length * ROW_PX : 0) +
    FOOTER_PX

  // Left-to-right dagre layout — routes edges around nodes rather than through
  // them, and places connected tables next to each other for readability.
  const g = new dagre.graphlib.Graph()
  g.setGraph({
    rankdir: 'LR',
    nodesep: 60,   // vertical spacing between nodes in the same rank
    ranksep: 140,  // horizontal spacing between ranks
    marginx: 40,
    marginy: 40,
  })
  g.setDefaultEdgeLabel(() => ({}))

  data.nodes.forEach((n) => {
    g.setNode(n.id, { width: CARD_WIDTH, height: heightOf(n) })
  })
  data.edges.forEach((e) => {
    g.setEdge(e.source_table, e.target_table)
  })

  dagre.layout(g)

  const nodes: Node[] = data.nodes.map((n) => {
    const pos = g.node(n.id)
    return {
      id: n.id,
      type: 'tableNode',
      // dagre returns the center; ReactFlow expects the top-left corner
      position: { x: pos.x - pos.width / 2, y: pos.y - pos.height / 2 },
      data: { name: n.name, columns: n.columns, partition_keys: n.partition_keys },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }
  })

  const edges: Edge[] = data.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source_table,
    target: e.target_table,
    label: `${e.source_column} → ${e.target_column}`,
    type: 'smoothstep',
    animated: false,
    // zIndex above nodes so edges never render behind a table card
    zIndex: 1000,
    style: { stroke: '#89b4fa', strokeWidth: 1.5 },
    labelStyle: { fill: '#6c7086', fontSize: 10 },
    labelBgStyle: { fill: 'var(--bg-panel)', fillOpacity: 0.85 },
    labelBgPadding: [4, 2],
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
