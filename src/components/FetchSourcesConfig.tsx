import { Checkbox, Space, Spin, Alert, Typography, Divider } from 'antd'
import { useEffect, useState } from 'react'

const { Text } = Typography

interface FetchSource {
  id: string
  name: string
  description: string
}

interface Props {
  value?: string[]
  onChange?: (value: string[]) => void
}

export default function FetchSourcesConfig({ value = [], onChange }: Props) {
  const [sources, setSources] = useState<FetchSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSources, setSelectedSources] = useState<string[]>(value)

  useEffect(() => {
    loadSources()
  }, [])

  useEffect(() => {
    setSelectedSources(value)
  }, [value])

  const loadSources = async () => {
    try {
      setLoading(true)
      setError(null)
      const fetchedSources = await window.electronAPI.getFetchSources()
      setSources(fetchedSources)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCheckboxChange = (sourceId: string, checked: boolean) => {
    let newSelected: string[]
    if (checked) {
      newSelected = [...selectedSources, sourceId]
    } else {
      newSelected = selectedSources.filter(id => id !== sourceId)
    }
    setSelectedSources(newSelected)
    if (onChange) {
      onChange(newSelected)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin tip="加载数据源列表..." />
      </div>
    )
  }

  if (error) {
    return (
      <Alert
        message="加载失败"
        description={error}
        type="error"
        showIcon
        style={{ margin: 16 }}
      />
    )
  }

  if (sources.length === 0) {
    return (
      <Alert
        message="没有可用的数据源"
        description="请在 nodes/fetch/sources/ 目录下添加数据源文件"
        type="warning"
        showIcon
        style={{ margin: 16 }}
      />
    )
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <Text strong>选择要启用的数据源：</Text>
      <Divider style={{ margin: '12px 0' }} />
      
      <Space direction="vertical" style={{ width: '100%' }}>
        {sources.map(source => (
          <div
            key={source.id}
            style={{
              padding: 12,
              border: '1px solid #f0f0f0',
              borderRadius: 4,
              background: selectedSources.includes(source.id) ? '#f6ffed' : '#fafafa'
            }}
          >
            <Checkbox
              checked={selectedSources.includes(source.id)}
              onChange={(e) => handleCheckboxChange(source.id, e.target.checked)}
            >
              <Text strong>{source.name}</Text>
            </Checkbox>
            <div style={{ marginLeft: 24, marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {source.description}
              </Text>
            </div>
          </div>
        ))}
      </Space>

      <Divider style={{ margin: '12px 0' }} />
      <Text type="secondary" style={{ fontSize: 12 }}>
        已选择 {selectedSources.length} 个数据源
      </Text>
    </div>
  )
}
