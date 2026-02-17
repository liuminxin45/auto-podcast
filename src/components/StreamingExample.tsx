import { useState } from 'react'
import { Card, Input, Button, Alert, Space } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { llmService } from '../services/llmService'
import { LLMError } from '../types/llm'

const { TextArea } = Input

export default function StreamingExample() {
  const [apiKey, setApiKey] = useState('')
  const [prompt, setPrompt] = useState('')
  const [response, setResponse] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string>()

  const handleStream = async () => {
    if (!prompt.trim() || !apiKey.trim()) return

    setIsStreaming(true)
    setResponse('')
    setError(undefined)

    try {
      await llmService.callStreaming(
        {
          apiBase: 'https://api.openai.com/v1',
          apiKey: apiKey.trim(),
          model: 'gpt-4',
          messages: [{ role: 'user', content: prompt }],
        },
        (chunk) => {
          setResponse(prev => prev + chunk)
        }
      )
    } catch (err: any) {
      const errorMsg = err instanceof LLMError ? err.message : String(err)
      setError(errorMsg)
    } finally {
      setIsStreaming(false)
    }
  }

  return (
    <Card
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ThunderboltOutlined style={{ color: '#155eef' }} />
          <span>Streaming API 示例</span>
        </div>
      }
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Alert
          message="安全提示"
          description="请勿在生产环境硬编码 API 密钥。建议使用环境变量或安全的配置管理系统。"
          type="warning"
          showIcon
        />
        
        <Input.Password
          placeholder="输入 OpenAI API Key"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          disabled={isStreaming}
        />

        <TextArea
          rows={3}
          placeholder="输入提示词..."
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          disabled={isStreaming}
        />

        <Button
          type="primary"
          onClick={handleStream}
          loading={isStreaming}
          disabled={!prompt.trim() || !apiKey.trim()}
        >
          {isStreaming ? '生成中...' : '开始生成'}
        </Button>
      </Space>

      {error && (
        <Alert
          type="error"
          message={error}
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setError(undefined)}
        />
      )}

      {response && (
        <Card
          size="small"
          title="实时响应"
          bodyStyle={{
            maxHeight: 400,
            overflowY: 'auto',
            fontFamily: 'monospace',
            fontSize: 12,
            whiteSpace: 'pre-wrap',
            backgroundColor: '#f9fafb',
          }}
        >
          {response}
        </Card>
      )}

      <div style={{ marginTop: 16, fontSize: 12, color: '#666' }}>
        <div>✓ 支持实时流式输出</div>
        <div>✓ 适用于长文本生成场景</div>
        <div>✓ 降低首字响应延迟</div>
      </div>
    </Card>
  )
}
