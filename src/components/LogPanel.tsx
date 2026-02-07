import { Tabs, Badge } from 'antd'

interface Props {
  workflow: any
}

export default function LogPanel({ workflow }: Props) {
  const state = workflow?.state || {}
  const logs = state.logs || []
  const errors = state.errors || []

  return (
    <div style={{ height: '100%', background: '#1e1e1e' }}>
      <Tabs
        defaultActiveKey="logs"
        items={[
          {
            key: 'logs',
            label: <span style={{ color: '#d4d4d4' }}>📋 Logs</span>,
            children: (
              <div style={{ 
                height: '150px', 
                overflow: 'auto', 
                padding: '8px 12px',
                fontFamily: 'Consolas, Monaco, monospace',
                fontSize: 13,
                color: '#d4d4d4'
              }}>
                {logs.map((log: string, i: number) => (
                  <div key={i}>{log}</div>
                ))}
                {logs.length === 0 && <div style={{ color: '#666' }}>No logs</div>}
              </div>
            )
          },
          {
            key: 'errors',
            label: (
              <Badge count={errors.length} offset={[10, 0]}>
                <span style={{ color: '#d4d4d4' }}>❌ Errors</span>
              </Badge>
            ),
            children: (
              <div style={{ height: '150px', overflow: 'auto', padding: '8px 12px', color: '#f44336' }}>
                {errors.map((err: any, i: number) => (
                  <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid #333' }}>
                    <div><strong>[{err.node}]</strong> {err.message}</div>
                  </div>
                ))}
                {errors.length === 0 && <div style={{ color: '#666' }}>No errors</div>}
              </div>
            )
          }
        ]}
        style={{ height: '100%' }}
        tabBarStyle={{ background: '#252526', margin: 0, padding: '0 12px' }}
      />
    </div>
  )
}
