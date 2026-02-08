import { Modal, Typography, Divider, Space, Button } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { useState } from 'react'

const { Paragraph, Text } = Typography

interface ApprovalData {
  workflowId: string
  nodeName: string
  data: any
}

interface Props {
  visible: boolean
  approvalData: ApprovalData | null
  onApprove: () => void
  onReject: () => void
}

export default function ApprovalModal({ visible, approvalData, onApprove, onReject }: Props) {
  const [loading, setLoading] = useState(false)

  if (!approvalData) return null

  const handleApprove = async () => {
    setLoading(true)
    try {
      await onApprove()
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    setLoading(true)
    try {
      await onReject()
    } finally {
      setLoading(false)
    }
  }

  // 渲染脚本内容
  const renderScriptContent = () => {
    const script = approvalData.data.script
    
    if (!script) {
      return <Text type="secondary">脚本数据不可用</Text>
    }

    return (
      <div style={{ maxHeight: 400, overflow: 'auto' }}>
        {/* 脚本元数据 */}
        {script.metadata && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
            <Text strong>脚本信息</Text>
            <div style={{ marginTop: 8 }}>
              {script.metadata.title && <div><Text type="secondary">标题: </Text>{script.metadata.title}</div>}
              {script.metadata.duration && <div><Text type="secondary">时长: </Text>{script.metadata.duration}分钟</div>}
              {script.metadata.hosts && <div><Text type="secondary">主持人: </Text>{script.metadata.hosts.join(', ')}</div>}
            </div>
          </div>
        )}

        {/* 脚本内容 */}
        <div style={{
          background: '#1e1e1e',
          color: '#d4d4d4',
          padding: 16,
          borderRadius: 4,
          fontFamily: 'monospace',
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}>
          {typeof script === 'string' 
            ? script 
            : JSON.stringify(script, null, 2)
          }
        </div>
      </div>
    )
  }

  // 渲染主题和素材
  const renderTopicAndMaterials = () => {
    const { selected_topic, selected_materials } = approvalData.data

    return (
      <div style={{ marginBottom: 16 }}>
        {selected_topic && (
          <div style={{ marginBottom: 12 }}>
            <Text strong>选定主题：</Text>
            <div style={{ 
              marginTop: 8, 
              padding: 12, 
              background: '#f0f7ff', 
              borderRadius: 4,
              border: '1px solid #91d5ff'
            }}>
              <div><Text strong>{selected_topic.title || '无标题'}</Text></div>
              {selected_topic.description && (
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary">{selected_topic.description}</Text>
                </div>
              )}
            </div>
          </div>
        )}

        {selected_materials && selected_materials.length > 0 && (
          <div>
            <Text strong>素材列表 ({selected_materials.length}条)：</Text>
            <div style={{ marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
              {selected_materials.slice(0, 5).map((material: any, index: number) => (
                <div 
                  key={index}
                  style={{ 
                    marginBottom: 8, 
                    padding: 8, 
                    background: '#fafafa', 
                    borderRadius: 4,
                    fontSize: 12
                  }}
                >
                  <Text strong>{material.title || `素材 ${index + 1}`}</Text>
                  {material.content && (
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {material.content.substring(0, 100)}...
                      </Text>
                    </div>
                  )}
                </div>
              ))}
              {selected_materials.length > 5 && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  还有 {selected_materials.length - 5} 条素材...
                </Text>
              )}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <Modal
      title={
        <Space>
          <span style={{ fontSize: 18 }}>📝</span>
          <span>脚本审批</span>
        </Space>
      }
      open={visible}
      width={800}
      footer={null}
      closable={false}
      maskClosable={false}
    >
      <Divider style={{ margin: '12px 0' }} />

      <div style={{ marginBottom: 16 }}>
        <Paragraph>
          AI已完成脚本生成，请审核以下内容。批准后将继续执行后续流程，拒绝则停止工作流。
        </Paragraph>
      </div>

      {renderTopicAndMaterials()}
      
      <Divider>生成的脚本</Divider>
      
      {renderScriptContent()}

      <Divider style={{ margin: '16px 0' }} />

      <div style={{ textAlign: 'right' }}>
        <Space>
          <Button
            size="large"
            danger
            icon={<CloseOutlined />}
            onClick={handleReject}
            loading={loading}
          >
            拒绝
          </Button>
          <Button
            size="large"
            type="primary"
            icon={<CheckOutlined />}
            onClick={handleApprove}
            loading={loading}
          >
            批准继续
          </Button>
        </Space>
      </div>
    </Modal>
  )
}
