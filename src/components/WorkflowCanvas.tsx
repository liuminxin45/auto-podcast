import { useEffect, useCallback } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type ReactFlowInstance,
  Position
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { Workflow } from '../types/workflow'

const NODE_SEQUENCE = [
  'source_selector', 'fetch', 'manual', 'preprocess', 'research', 'topic_selection',
  'script', 'stages', 'tts', 'audio_postprocess',
  'assets', 'store', 'publish'
]

const NODE_LABELS: Record<string, string> = {
  source_selector: 'Source',
  fetch: 'Fetch',
  manual: 'Manual',
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
  const nodes: Node[] = []
  let xPos = 50
  const yBase = 80
  const xSpacing = 160

  for (let i = 0; i < NODE_SEQUENCE.length; i++) {
    const name = NODE_SEQUENCE[i]
    const execution = workflow?.nodeExecutions?.[name]
    const status = execution?.status || 'pending'
    const { bg, border, emoji } = getNodeStyle(status)
    const durationText = execution?.duration
      ? `${execution.duration.toFixed(1)}s`
      : ''

    let yPos = yBase
    
    // fetch和manual并行显示
    if (name === 'fetch') {
      yPos = yBase - 60  // fetch在上方
    } else if (name === 'manual') {
      yPos = yBase + 60  // manual在下方
      xPos -= xSpacing  // manual与fetch同一个x坐标
    }

    nodes.push({
      id: name,
      type: 'default',
      data: {
        label: `${emoji} ${NODE_LABELS[name]}${durationText ? '\n' + durationText : ''}`
      },
      position: { x: xPos, y: yPos },
      sourcePosition: Position.Right,  // 连线从右侧出发
      targetPosition: Position.Left,   // 连线从左侧进入
      style: {
        background: bg,
        border: `2px solid ${border}`,
        borderRadius: '8px',
        padding: '10px 16px',
        width: 120,
        fontSize: '13px',
        textAlign: 'center' as const,
      }
    })

    xPos += xSpacing
  }

  return nodes
}

function buildEdges(workflow: Workflow | null): Edge[] {
  const edges: Edge[] = []
  
  // source_selector 分支到 fetch 和 manual
  edges.push({
    id: 'source_selector-fetch',
    source: 'source_selector',
    target: 'fetch',
    animated: workflow?.currentNode === 'source_selector',
    style: { stroke: '#999', strokeWidth: 2 }
  })
  
  edges.push({
    id: 'source_selector-manual',
    source: 'source_selector',
    target: 'manual',
    animated: workflow?.currentNode === 'source_selector',
    style: { stroke: '#999', strokeWidth: 2 }
  })
  
  // fetch 和 manual 都连接到 preprocess
  edges.push({
    id: 'fetch-preprocess',
    source: 'fetch',
    target: 'preprocess',
    animated: workflow?.currentNode === 'fetch',
    style: { stroke: '#999', strokeWidth: 2 }
  })
  
  edges.push({
    id: 'manual-preprocess',
    source: 'manual',
    target: 'preprocess',
    animated: workflow?.currentNode === 'manual',
    style: { stroke: '#999', strokeWidth: 2 }
  })
  
  // preprocess 之后的节点顺序连接
  const remainingNodes = NODE_SEQUENCE.slice(3)  // 从 preprocess 开始
  for (let i = 0; i < remainingNodes.length - 1; i++) {
    edges.push({
      id: `${remainingNodes[i]}-${remainingNodes[i + 1]}`,
      source: remainingNodes[i],
      target: remainingNodes[i + 1],
      animated: workflow?.currentNode === remainingNodes[i],
      style: { stroke: '#999', strokeWidth: 2 }
    })
  }
  
  return edges
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
