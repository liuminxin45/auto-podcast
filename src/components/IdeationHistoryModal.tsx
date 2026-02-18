import { useState, useEffect } from 'react'
import { Modal, List, Tag, Button, Space, Empty, Tooltip, message, Popconfirm } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
  HistoryOutlined,
  ClearOutlined,
} from '@ant-design/icons'
import { ideationHistoryService, type IdeationHistoryRecord } from '../services/ideation/historyService'

interface IdeationHistoryModalProps {
  visible: boolean
  onClose: () => void
  onSelect?: (record: IdeationHistoryRecord) => void
}

export default function IdeationHistoryModal({
  visible,
  onClose,
  onSelect,
}: IdeationHistoryModalProps) {
  const [records, setRecords] = useState<IdeationHistoryRecord[]>([])
  const [selectedRecord, setSelectedRecord] = useState<IdeationHistoryRecord | null>(null)

  useEffect(() => {
    if (visible) {
      loadRecords()
    }
  }, [visible])

  const loadRecords = () => {
    setRecords(ideationHistoryService.getAll())
  }

  const handleDelete = (id: string) => {
    ideationHistoryService.delete(id)
    message.success('已删除')
    loadRecords()
    if (selectedRecord?.id === id) {
      setSelectedRecord(null)
    }
  }

  const handleClearAll = () => {
    ideationHistoryService.clear()
    message.success('已清空所有记录')
    loadRecords()
    setSelectedRecord(null)
  }

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)

    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes}分钟前`
    if (hours < 24) return `${hours}小时前`
    if (days < 7) return `${days}天前`
    return date.toLocaleDateString('zh-CN')
  }

  return (
    <Modal
      title={
        <Space>
          <HistoryOutlined />
          <span>构思历史记录</span>
          <Tag color="blue">{records.length}条</Tag>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={1200}
      footer={
        <Space>
          <Popconfirm
            title="确定清空所有历史记录？"
            onConfirm={handleClearAll}
            disabled={records.length === 0}
          >
            <Button
              icon={<ClearOutlined />}
              danger
              disabled={records.length === 0}
            >
              清空全部
            </Button>
          </Popconfirm>
          <Button onClick={onClose}>关闭</Button>
        </Space>
      }
      styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}
    >
      {records.length === 0 ? (
        <Empty description="暂无构思记录" />
      ) : (
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <List
              dataSource={records}
              renderItem={(record) => (
                <List.Item
                  key={record.id}
                  style={{
                    padding: 12,
                    background: selectedRecord?.id === record.id ? 'var(--bg-tertiary)' : 'transparent',
                    borderRadius: 8,
                    cursor: 'pointer',
                  }}
                  onClick={() => setSelectedRecord(record)}
                  actions={[
                    <Tooltip title="查看详情">
                      <Button
                        type="text"
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedRecord(record)
                        }}
                      />
                    </Tooltip>,
                    <Popconfirm
                      title="确定删除这条记录？"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        handleDelete(record.id)
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      record.success ? (
                        <CheckCircleOutlined style={{ fontSize: 24, color: '#10b981' }} />
                      ) : (
                        <CloseCircleOutlined style={{ fontSize: 24, color: '#ef4444' }} />
                      )
                    }
                    title={
                      <Space>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>
                          {record.output?.topic.title || '未生成标题'}
                        </span>
                        <Tag bordered={false} style={{ fontSize: 10 }}>
                          {record.input.materialCount} 条素材
                        </Tag>
                      </Space>
                    }
                    description={
                      <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                        <div>{formatDate(record.timestamp)}</div>
                        {record.error && (
                          <div style={{ color: '#ef4444', marginTop: 2 }}>{record.error}</div>
                        )}
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </div>

          {selectedRecord && (
            <div style={{
              width: 400,
              padding: 16,
              background: 'var(--bg-tertiary)',
              borderRadius: 12,
              maxHeight: '60vh',
              overflow: 'auto',
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>
                记录详情
              </div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                  状态
                </div>
                <Tag color={selectedRecord.success ? 'success' : 'error'}>
                  {selectedRecord.success ? '成功' : '失败'}
                </Tag>
              </div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                  时间
                </div>
                <div style={{ fontSize: 12 }}>
                  {new Date(selectedRecord.timestamp).toLocaleString('zh-CN')}
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                  输入素材 ({selectedRecord.input.materialCount}条)
                </div>
                <div style={{
                  maxHeight: 150,
                  overflow: 'auto',
                  fontSize: 11,
                  background: 'var(--bg-primary)',
                  padding: 8,
                  borderRadius: 6,
                }}>
                  {selectedRecord.input.materials.slice(0, 10).map((m, idx) => (
                    <div key={idx} style={{ marginBottom: 4 }}>
                      {idx + 1}. {m.title}
                    </div>
                  ))}
                  {selectedRecord.input.materialCount > 10 && (
                    <div style={{ color: 'var(--text-tertiary)' }}>
                      ... 还有 {selectedRecord.input.materialCount - 10} 条
                    </div>
                  )}
                </div>
              </div>

              {selectedRecord.output && (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                      主题
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>
                      {selectedRecord.output.topic.title}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                      {selectedRecord.output.topic.description}
                    </div>
                  </div>

                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                      节目结构
                    </div>
                    <div style={{ fontSize: 11 }}>
                      {selectedRecord.output.blocks.length} 个段落
                    </div>
                  </div>

                  {selectedRecord.output.quality_score && (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                        质量评分
                      </div>
                      <Tag color={selectedRecord.output.quality_score.overall >= 70 ? 'success' : 'warning'}>
                        {selectedRecord.output.quality_score.overall}分
                      </Tag>
                    </div>
                  )}
                </>
              )}

              {selectedRecord.error && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                    错误信息
                  </div>
                  <div style={{
                    fontSize: 11,
                    color: '#ef4444',
                    background: 'rgba(239, 68, 68, 0.1)',
                    padding: 8,
                    borderRadius: 6,
                  }}>
                    {selectedRecord.error}
                  </div>
                </div>
              )}

              {selectedRecord.warnings && selectedRecord.warnings.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 4 }}>
                    警告
                  </div>
                  <div style={{ fontSize: 11 }}>
                    {selectedRecord.warnings.map((w, i) => (
                      <div key={i} style={{ marginBottom: 2 }}>• {w}</div>
                    ))}
                  </div>
                </div>
              )}

              {onSelect && selectedRecord.success && (
                <Button
                  type="primary"
                  block
                  style={{ marginTop: 16 }}
                  onClick={() => {
                    onSelect(selectedRecord)
                    onClose()
                  }}
                >
                  应用此记录
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
