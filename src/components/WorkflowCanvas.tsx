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
  Position,
  MarkerType
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
  const baseStyle = {
    background: 'var(--bg-secondary)',
    borderRadius: '12px',
    padding: '12px 16px',
    width: 160,
    color: 'var(--text-primary)',
    fontSize: '13px',
    fontWeight: 500,
    boxShadow: 'var(--shadow-md)',
    transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
    textAlign: 'left' as const,
  }

  switch (status) {
    case 'completed':
      return { 
        ...baseStyle, 
        border: '1px solid var(--success-color)',
        boxShadow: '0 4px 12px rgba(16, 185, 129, 0.15)',
        statusColor: 'var(--success-color)',
        icon: '✓'
      }
    case 'running':
      return { 
        ...baseStyle, 
        border: '1px solid var(--accent-primary)',
        boxShadow: '0 4px 15px rgba(37, 99, 235, 0.2)',
        statusColor: 'var(--accent-primary)',
        icon: '⚡'
      }
    case 'failed':
      return { 
        ...baseStyle, 
        border: '1px solid var(--error-color)',
        boxShadow: '0 4px 12px rgba(239, 68, 68, 0.15)',
        statusColor: 'var(--error-color)',
        icon: '✕'
      }
    case 'waiting_approval':
      return { 
        ...baseStyle, 
        border: '1px solid var(--warning-color)',
        boxShadow: '0 4px 12px rgba(245, 158, 11, 0.15)',
        statusColor: 'var(--warning-color)',
        icon: '👤'
      }
    default:
      return { 
        ...baseStyle, 
        border: '1px solid var(--border-color)',
        statusColor: 'var(--text-tertiary)',
        icon: '○'
      }
  }
}

function buildNodes(workflow: Workflow | null): Node[] {
  const nodes: Node[] = []
  let xPos = 50
  const yBase = 200
  const xSpacing = 240 // Wider spacing for cleaner look

  for (let i = 0; i < NODE_SEQUENCE.length; i++) {
    const name = NODE_SEQUENCE[i]
    const execution = workflow?.nodeExecutions?.[name]
    const status = execution?.status || 'pending'
    const { statusColor, icon, ...style } = getNodeStyle(status)
    const durationText = execution?.duration
      ? `${execution.duration.toFixed(1)}s`
      : ''

    let yPos = yBase
    
    // Parallel branches
    if (name === 'fetch') {
      yPos = yBase - 100 
    } else if (name === 'manual') {
      yPos = yBase + 100
      xPos -= xSpacing 
    }

    nodes.push({
      id: name,
      type: 'default',
      data: {
        label: (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ 
              width: '32px', 
              height: '32px', 
              borderRadius: '8px', 
              background: `${statusColor}15`, // 10% opacity
              color: statusColor,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '16px',
              flexShrink: 0
            }}>
              {icon}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                {NODE_LABELS[name]}
              </div>
              {durationText && (
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                  {durationText}
                </div>
              )}
            </div>
          </div>
        )
      },
      position: { x: xPos, y: yPos },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      style: style
    })

    xPos += xSpacing
  }

  return nodes
}

function buildEdges(workflow: Workflow | null): Edge[] {
  const edges: Edge[] = []
  
  const commonEdgeStyle = { stroke: 'var(--border-color)', strokeWidth: 1.5 }
  const activeEdgeStyle = { stroke: 'var(--accent-primary)', strokeWidth: 2 }
  
  // Custom marker
  const markerEnd = {
    type: MarkerType.ArrowClosed,
    width: 20,
    height: 20,
    color: 'var(--border-color)',
  }
  
  const activeMarkerEnd = {
    ...markerEnd,
    color: 'var(--accent-primary)',
  }

  const addEdge = (source: string, target: string) => {
    const isActive = workflow?.currentNode === source || 
                    (workflow?.nodeExecutions?.[source]?.status === 'completed' && workflow?.currentNode === target)
    
    edges.push({
      id: `${source}-${target}`,
      source,
      target,
      animated: isActive,
      style: isActive ? activeEdgeStyle : commonEdgeStyle,
      type: 'smoothstep', // Cleaner lines (n8n style)
      markerEnd: isActive ? activeMarkerEnd : markerEnd,
    })
  }

  // Define connections
  addEdge('source_selector', 'fetch')
  addEdge('source_selector', 'manual')
  addEdge('fetch', 'preprocess')
  addEdge('manual', 'preprocess')
  
  // Linear sequence
  const remainingNodes = NODE_SEQUENCE.slice(3) // From preprocess
  for (let i = 0; i < remainingNodes.length - 1; i++) {
    addEdge(remainingNodes[i], remainingNodes[i+1])
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
    setTimeout(() => instance.fitView({ padding: 0.2, duration: 800 }), 100)
  }, [])

  return (
    <div style={{ position: 'absolute', inset: 0, background: 'var(--bg-primary)' }}>
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
        defaultEdgeOptions={{ type: 'smoothstep' }}
        fitView
      >
        <Background color="var(--border-color)" gap={20} size={1} />
        <Controls 
          style={{ 
            background: 'var(--bg-secondary)', 
            border: '1px solid var(--border-color)',
            boxShadow: 'var(--shadow-md)',
            borderRadius: '8px',
            padding: '4px'
          }} 
          showInteractive={false}
        />
        <MiniMap 
          style={{ 
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            boxShadow: 'var(--shadow-md)'
          }}
          maskColor="var(--bg-primary)"
          nodeColor={(n) => {
             // simplified color mapping for minimap
             const style = n.style || {}
             if (style.border && (style.border as string).includes('success')) return 'var(--success-color)'
             if (style.border && (style.border as string).includes('accent')) return 'var(--accent-primary)'
             if (style.border && (style.border as string).includes('error')) return 'var(--error-color)'
             return 'var(--border-color)'
          }}
        />
      </ReactFlow>
    </div>
  )
}
