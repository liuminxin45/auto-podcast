import { Drawer, Descriptions, Tag, Typography, Tabs, message, Button, Space } from 'antd'
import { useState, useEffect } from 'react'
import { CheckOutlined, CloseOutlined, CopyOutlined } from '@ant-design/icons'
import DynamicConfigForm from './DynamicConfigForm'

const { Title, Paragraph } = Typography

interface Props {
  nodeName: string
  workflow: any
  onClose: () => void
}

export default function NodeDetailPanel({ nodeName, workflow, onClose }: Props) {
  const execution = workflow?.nodeExecutions?.[nodeName]
  const state = workflow?.state || {}
  const [activeTab, setActiveTab] = useState('status')
  const [config, setConfig] = useState<Record<string, any>>({})
  const [configLoaded, setConfigLoaded] = useState(false)

  // 自动加载配置
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const savedConfig = await window.electronAPI.loadNodeConfig(nodeName)
        if (savedConfig) {
          setConfig(savedConfig)
        }
        setConfigLoaded(true)
      } catch (e: any) {
        console.error('Failed to load config:', e)
        setConfigLoaded(true)
      }
    }
    loadConfig()
  }, [nodeName])

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

  const handleConfigChange = (values: Record<string, any>) => {
    setConfig(values)
  }

  const handleConfigSave = async (values: Record<string, any>) => {
    try {
      const result = await window.electronAPI.saveNodeConfig(nodeName, values)
      if (result.success) {
        message.success('配置已保存到本地，下次运行时生效')
        setConfig(values)
      } else {
        message.error(`保存失败: ${result.error}`)
      }
    } catch (e: any) {
      message.error(`保存失败: ${e.message}`)
    }
  }

  const handleApprove = async () => {
    try {
      await window.electronAPI.approveNode(workflow.id, nodeName, true)
      message.success('已批准，工作流继续执行')
    } catch (e: any) {
      message.error(`批准失败: ${e.message}`)
    }
  }

  const handleReject = async () => {
    try {
      await window.electronAPI.approveNode(workflow.id, nodeName, false)
      message.warning('已拒绝，工作流已停止')
    } catch (e: any) {
      message.error(`拒绝失败: ${e.message}`)
    }
  }

  const handleCopyNodeInfo = async () => {
    try {
      const nodeInfo = {
        nodeName,
        status: execution?.status || 'not_executed',
        duration: execution?.duration || 0,
        config,
        input: getNodeInput(),
        output: getNodeOutput(),
        logs: state.logs?.filter((log: string) => 
          log.includes(`[${nodeName}]`) || log.includes(nodeName)
        ) || [],
        errors: state.errors?.filter((err: any) => err.node === nodeName) || [],
        error: execution?.error || null,
        timestamp: new Date().toISOString()
      }

      const formattedInfo = `# ${nodeName} 节点完整信息\n\n` +
        `## 基本信息\n` +
        `- 节点名称: ${nodeName}\n` +
        `- 状态: ${execution?.status || '未执行'}\n` +
        `- 耗时: ${execution?.duration ? execution.duration.toFixed(2) + 's' : '-'}\n` +
        `- 时间: ${nodeInfo.timestamp}\n\n` +
        `## 配置参数\n\`\`\`json\n${JSON.stringify(config, null, 2)}\n\`\`\`\n\n` +
        `## 输入数据\n\`\`\`json\n${JSON.stringify(nodeInfo.input, null, 2)}\n\`\`\`\n\n` +
        `## 输出数据\n\`\`\`json\n${JSON.stringify(nodeInfo.output, null, 2)}\n\`\`\`\n\n` +
        `## 日志\n\`\`\`\n${nodeInfo.logs.join('\n')}\n\`\`\`\n\n` +
        (execution?.error ? `## 错误信息\n\`\`\`\n${execution.error}\n\`\`\`\n\n` : '') +
        (nodeInfo.errors.length > 0 ? `## 错误列表\n\`\`\`json\n${JSON.stringify(nodeInfo.errors, null, 2)}\n\`\`\`\n` : '')

      await navigator.clipboard.writeText(formattedInfo)
      message.success('节点信息已复制到剪贴板')
    } catch (e: any) {
      message.error(`复制失败: ${e.message}`)
    }
  }

  const isWaitingApproval = execution?.status === 'waiting_approval'

  // 获取节点的输入数据
  const getNodeInput = () => {
    // 根据节点类型获取对应的输入数据
    const nodeInputMap: Record<string, string[]> = {
      'fetch': [],
      'preprocess': ['raw_contents'],
      'research': ['cleaned_contents'],
      'topic_selection': ['researched_contents'],
      'script': ['selected_topic', 'selected_materials'],
      'stages': ['script'],
      'tts': ['stages'],
      'audio_postprocess': ['audio_segments'],
      'assets': ['final_audio_path'],
      'store': ['final_audio_path', 'cover_path', 'audio_metadata'],
      'publish': ['storage_info', 'rss_path']
    }
    
    const inputKeys = nodeInputMap[nodeName] || []
    const inputData: Record<string, any> = {}
    
    inputKeys.forEach(key => {
      if (state[key] !== undefined) {
        inputData[key] = state[key]
      }
    })
    
    return inputData
  }

  // 获取节点的输出数据
  const getNodeOutput = () => {
    const nodeOutputMap: Record<string, string[]> = {
      'fetch': ['raw_contents'],
      'preprocess': ['cleaned_contents'],
      'research': ['researched_contents'],
      'topic_selection': ['selected_topic', 'selected_materials'],
      'script': ['script'],
      'stages': ['stages'],
      'tts': ['audio_segments'],
      'audio_postprocess': ['final_audio_path', 'audio_metadata'],
      'assets': ['cover_path', 'intro_outro_paths'],
      'store': ['storage_info'],
      'publish': ['publish_status']
    }
    
    const outputKeys = nodeOutputMap[nodeName] || []
    const outputData: Record<string, any> = {}
    
    outputKeys.forEach(key => {
      if (state[key] !== undefined) {
        outputData[key] = state[key]
      }
    })
    
    return outputData
  }

  // 渲染JSON数据
  const renderJsonData = (data: any, title: string) => {
    if (!data || Object.keys(data).length === 0) {
      return (
        <div style={{ padding: 16, textAlign: 'center', color: '#999' }}>
          {title === '输入' ? '节点尚未接收到输入数据' : '节点尚未产生输出数据'}
        </div>
      )
    }

    return (
      <div style={{ padding: '16px 0' }}>
        {Object.entries(data).map(([key, value]) => (
          <div key={key} style={{ marginBottom: 16 }}>
            <div style={{ 
              fontWeight: 'bold', 
              marginBottom: 8,
              padding: '4px 8px',
              background: '#f0f0f0',
              borderRadius: 4
            }}>
              {key}
            </div>
            <div style={{
              background: '#1e1e1e',
              color: '#d4d4d4',
              padding: 12,
              borderRadius: 4,
              maxHeight: 300,
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: 12,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word'
            }}>
              {typeof value === 'object' 
                ? JSON.stringify(value, null, 2)
                : String(value)
              }
            </div>
          </div>
        ))}
      </div>
    )
  }

  const tabItems = [
    {
      key: 'status',
      label: '状态',
      children: (
        <>
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

              {isWaitingApproval && (
                <div style={{ marginTop: 16, padding: 12, background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 4 }}>
                  <Title level={5} style={{ color: '#d48806' }}>等待审批</Title>
                  <Paragraph style={{ marginBottom: 12 }}>
                    此节点需要人工审批才能继续执行。请检查节点输出并决定是否继续。
                  </Paragraph>
                  <Space>
                    <Button 
                      type="primary" 
                      icon={<CheckOutlined />}
                      onClick={handleApprove}
                    >
                      批准继续
                    </Button>
                    <Button 
                      danger 
                      icon={<CloseOutlined />}
                      onClick={handleReject}
                    >
                      拒绝停止
                    </Button>
                  </Space>
                </div>
              )}

              {execution.error && (
                <div style={{ marginTop: 16, padding: 12, background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 4 }}>
                  <Title level={5} style={{ color: '#cf1322' }}>Error</Title>
                  <Paragraph style={{ fontFamily: 'monospace', fontSize: 12 }}>
                    {execution.error}
                  </Paragraph>
                </div>
              )}
            </>
          )}
          {!execution && (
            <div style={{ padding: 16, textAlign: 'center', color: '#999' }}>
              节点尚未执行
            </div>
          )}
        </>
      )
    },
    {
      key: 'input',
      label: '输入',
      children: renderJsonData(getNodeInput(), '输入')
    },
    {
      key: 'output',
      label: '输出',
      children: renderJsonData(getNodeOutput(), '输出')
    },
    {
      key: 'logs',
      label: '日志',
      children: (
        <div style={{ 
          background: '#1e1e1e', 
          color: '#d4d4d4', 
          padding: 12, 
          borderRadius: 4,
          maxHeight: 400,
          overflow: 'auto',
          fontFamily: 'monospace',
          fontSize: 12
        }}>
          {state.logs?.filter((log: string) => log.includes(`[${nodeName}]`) || log.includes(nodeName)).map((log: string, i: number) => (
            <div key={i}>{log}</div>
          )) || 'No logs'}
        </div>
      )
    },
    {
      key: 'config',
      label: '配置',
      children: configLoaded ? (
        <DynamicConfigForm
          nodeName={nodeName}
          initialValues={config}
          onChange={handleConfigChange}
          onSubmit={handleConfigSave}
        />
      ) : (
        <div style={{ padding: 16, textAlign: 'center' }}>加载配置中...</div>
      )
    }
  ]

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: 24 }}>
          <span>{nodeName} 节点</span>
          <Button 
            icon={<CopyOutlined />}
            onClick={handleCopyNodeInfo}
            size="small"
          >
            复制节点信息
          </Button>
        </div>
      }
      placement="right"
      onClose={onClose}
      open={true}
      width={600}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
      />
    </Drawer>
  )
}
