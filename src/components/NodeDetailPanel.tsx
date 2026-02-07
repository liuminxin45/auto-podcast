import { Drawer, Descriptions, Tag, Typography } from 'antd'

const { Title, Paragraph } = Typography

interface Props {
  nodeName: string
  workflow: any
  onClose: () => void
}

export default function NodeDetailPanel({ nodeName, workflow, onClose }: Props) {
  const execution = workflow?.nodeExecutions?.[nodeName]
  const state = workflow?.state || {}

  const getStatusTag = (status: string) => {
    const colors: Record<string, string> = {
      completed: 'success',
      running: 'processing',
      failed: 'error',
      waiting_approval: 'warning',
      pending: 'default'
    }
    return <Tag color={colors[status] || 'default'}>{status}</Tag>
  }

  return (
    <Drawer
      title={`${nodeName} 节点`}
      placement="right"
      onClose={onClose}
      open={true}
      width={500}
    >
      {execution && (
        <>
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="状态">
              {getStatusTag(execution.status)}
            </Descriptions.Item>
            <Descriptions.Item label="耗时">
              {execution.duration ? `${execution.duration.toFixed(2)}s` : '-'}
            </Descriptions.Item>
          </Descriptions>

          {execution.error && (
            <div style={{ marginTop: 16, padding: 12, background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4 }}>
              <Title level={5} style={{ color: '#cf1322' }}>Error</Title>
              <Paragraph style={{ fontFamily: 'monospace', fontSize: 12 }}>
                {execution.error}
              </Paragraph>
            </div>
          )}

          <div style={{ marginTop: 16 }}>
            <Title level={5}>Logs</Title>
            <div style={{ 
              background: '#1e1e1e', 
              color: '#d4d4d4', 
              padding: 12, 
              borderRadius: 4,
              maxHeight: 300,
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: 12
            }}>
              {state.logs?.filter((log: string) => log.includes(`[${nodeName}]`)).map((log: string, i: number) => (
                <div key={i}>{log}</div>
              )) || 'No logs'}
            </div>
          </div>
        </>
      )}
    </Drawer>
  )
}
