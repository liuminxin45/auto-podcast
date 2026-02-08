import { Input, Button, Space, Card, Typography, Divider } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useState } from 'react'

const { TextArea } = Input
const { Text } = Typography

interface NewsItem {
  title: string
  content: string
  url?: string
}

interface Props {
  value?: NewsItem[]
  onChange?: (value: NewsItem[]) => void
}

/**
 * Manual节点新闻列表配置组件
 * 提供友好的UI来添加、编辑、删除手动输入的新闻
 */
export default function ManualNewsConfig({ value = [], onChange }: Props) {
  const [newsItems, setNewsItems] = useState<NewsItem[]>(value.length > 0 ? value : [])

  const handleAdd = () => {
    const newItems = [...newsItems, { title: '', content: '', url: '' }]
    setNewsItems(newItems)
    if (onChange) {
      onChange(newItems)
    }
  }

  const handleRemove = (index: number) => {
    const newItems = newsItems.filter((_, i) => i !== index)
    setNewsItems(newItems)
    if (onChange) {
      onChange(newItems)
    }
  }

  const handleChange = (index: number, field: keyof NewsItem, fieldValue: string) => {
    const newItems = [...newsItems]
    newItems[index] = { ...newItems[index], [field]: fieldValue }
    setNewsItems(newItems)
    if (onChange) {
      onChange(newItems)
    }
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>手动输入新闻列表</Text>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleAdd}
          size="small"
        >
          添加新闻
        </Button>
      </div>

      {newsItems.length === 0 && (
        <Card style={{ textAlign: 'center', background: '#fafafa' }}>
          <Text type="secondary">暂无新闻，点击"添加新闻"按钮开始添加</Text>
        </Card>
      )}

      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {newsItems.map((item, index) => (
          <Card
            key={index}
            size="small"
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong>新闻 {index + 1}</Text>
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemove(index)}
                >
                  删除
                </Button>
              </div>
            }
            style={{ background: '#f9f9f9' }}
          >
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>标题 *</Text>
                <Input
                  value={item.title}
                  onChange={(e) => handleChange(index, 'title', e.target.value)}
                  placeholder="输入新闻标题"
                  style={{ marginTop: 4 }}
                />
              </div>

              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>内容 *</Text>
                <TextArea
                  value={item.content}
                  onChange={(e) => handleChange(index, 'content', e.target.value)}
                  placeholder="输入新闻内容"
                  rows={4}
                  style={{ marginTop: 4 }}
                />
              </div>

              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>链接（可选）</Text>
                <Input
                  value={item.url}
                  onChange={(e) => handleChange(index, 'url', e.target.value)}
                  placeholder="https://..."
                  style={{ marginTop: 4 }}
                />
              </div>
            </Space>
          </Card>
        ))}
      </Space>

      {newsItems.length > 0 && (
        <>
          <Divider style={{ margin: '16px 0' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            已添加 {newsItems.length} 条新闻
          </Text>
        </>
      )}
    </div>
  )
}
