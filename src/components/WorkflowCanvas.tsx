import { useEffect, useCallback } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type ReactFlowInstance
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { Workflow } from '../types/workflow'

const NODE_SEQUENCE = [
  'fetch', 'preprocess', 'research', 'topic_selection',
  'script', 'stages', 'tts', 'audio_postprocess',
  'assets', 'store', 'publish'
]

const NODE_LABELS: Record<string, string> = {
  fetch: 'Fetch',
  preprocess: 'Preprocess',
  research: 'Research',
  topic_selection: 'Topic',
  script: 'Script',
  stages: 'Stages',
  tts: 'TTS',
  audio_postprocess: 'Audio',
  assets: 'Assets',
  store: 'Store',
  publish: 'Publish'
}

function getNodeStyle(status: string) {
  switch (status) {
    case 'completed':
      return { bg: '#d4edda', border: '#28a745', emoji: '✓' }
    case 'running':
      return { bg: '#fff3cd', border: '#ffc107', emoji: '⏳' }
    case 'failed':
      return { bg: '#f8d7da', border: '#dc3545', emoji: '❌' }
    case 'waiting_approval':
      return { bg: '#d1ecf1', border: '#17a2b8', emoji: '👤' }
    default:
      return { bg: '#f0f0f0', border: '#d9d9d9', emoji: '⏸' }
  }
}

function buildNodes(workflow: Workflow | null): Node[] {
  return NODE_SEQUENCE.map((name, index) => {
    const execution = workflow?.nodeExecutions?.[name]
    const status = execution?.status || 'pending'
    const { bg, border, emoji } = getNodeStyle(status)
    const durationText = execution?.duration
      ? `${execution.duration.toFixed(1)}s`
      : ''

    return {
      id: name,
      type: 'default',
      data: {
        label: `${emoji} ${NODE_LABELS[name]}${durationText ? '\n' + durationText : ''}`
      },
      position: { x: 50 + index * 160, y: 80 },
      style: {
        background: bg,
        border: `2px solid ${border}`,
        borderRadius: '8px',
        padding: '10px 16px',
        width: 120,
        fontSize: '13px',
        textAlign: 'center' as const,
      }
    }
  })
}

function buildEdges(workflow: Workflow | null): Edge[] {
  return NODE_SEQUENCE.slice(0, -1).map((name, i) => ({
    id: `${name}-${NODE_SEQUENCE[i + 1]}`,
    source: name,
    target: NODE_SEQUENCE[i + 1],
    animated: workflow?.currentNode === name,
    style: { stroke: '#999', strokeWidth: 2 }
  }))
}

const initialNodes = buildNodes(null)
const initialEdges = buildEdges(null)

interface Props {
  workflow: Workflow | null
  onNodeClick: (nodeName: string) => void
}

export default function WorkflowCanvas({ workflow, onNodeClick }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useEffect(() => {
    setNodes(buildNodes(workflow))
    setEdges(buildEdges(workflow))
  }, [workflow, setNodes, setEdges])

  const onInit = useCallback((instance: ReactFlowInstance) => {
    setTimeout(() => instance.fitView({ padding: 0.2 }), 100)
  }, [])

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onNodeClick(node.id)}
        onInit={onInit}
        minZoom={0.1}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  )
}
