import { Form, Input, AutoComplete, Button, message } from 'antd'
import { useState } from 'react'
import { ApiOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { fetchModels } from '../utils/modelFetcher'

/**
 * LLM配置字段组件
 * 封装API Base、API Key、LLM Model三个字段及其联动逻辑
 * 注意：此组件不接收props，直接使用Form.useFormInstance()获取表单实例
 */
export default function LLMConfigFields() {
  const form = Form.useFormInstance()
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)

  // 拉取模型列表
  const handleFetchModels = async () => {
    const apiBase = form.getFieldValue('api_base')?.trim()
    const apiKey = form.getFieldValue('api_key')?.trim()

    if (!apiBase || !apiKey) {
      message.warning('请先填写API Base和API Key')
      return
    }

    setLoadingModels(true)
    try {
      const models = await fetchModels(apiBase, apiKey)
      setAvailableModels(models)
      message.success(`成功拉取${models.length}个模型`)
    } catch (e: any) {
      message.error(`拉取模型失败: ${e.message}`)
      setAvailableModels([])
    } finally {
      setLoadingModels(false)
    }
  }

  // 测试连通性
  const handleTestConnection = async () => {
    const apiBase = form.getFieldValue('api_base')?.trim()
    const apiKey = form.getFieldValue('api_key')?.trim()
    const llmModel = form.getFieldValue('llm_model')?.trim()

    if (!apiBase || !apiKey || !llmModel) {
      message.warning('请先填写完整的LLM配置（API Base、API Key、LLM Model）')
      return
    }

    setTestingConnection(true)
    try {
      // 调用测试API
      const testUrl = `${apiBase.replace(/\/$/, '')}/chat/completions`
      const response = await fetch(testUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: llmModel,
          messages: [{ role: 'user', content: 'test' }],
          max_tokens: 5
        })
      })

      if (response.ok) {
        message.success('✅ LLM配置测试成功，连接正常')
      } else {
        const errorData = await response.json().catch(() => ({}))
        message.error(`❌ 连接失败: ${response.status} ${errorData.error?.message || response.statusText}`)
      }
    } catch (e: any) {
      message.error(`❌ 连接测试失败: ${e.message}`)
    } finally {
      setTestingConnection(false)
    }
  }

  return (
    <>
      <Form.Item
        name="api_base"
        label="API Base"
        tooltip="API基础URL，例如 https://api.openai.com/v1"
      >
        <Input placeholder="https://api.openai.com/v1" />
      </Form.Item>

      <Form.Item
        label="API Key"
        tooltip="API密钥（留空则使用环境变量OPENAI_API_KEY）"
        style={{ marginBottom: 0 }}
      >
        <Form.Item
          name="api_key"
          style={{ display: 'inline-block', width: 'calc(100% - 100px)', marginBottom: 0 }}
        >
          <Input.Password placeholder="sk-..." />
        </Form.Item>
        <Button
          icon={<ApiOutlined />}
          onClick={handleFetchModels}
          loading={loadingModels}
          style={{ marginLeft: 8 }}
        >
          拉取模型
        </Button>
      </Form.Item>

      <Form.Item
        name="llm_model"
        label="LLM Model"
        tooltip="选择或输入模型名称，点击'拉取模型'按钮可自动获取可用模型列表"
      >
        <AutoComplete
          options={availableModels.map(model => ({ value: model, label: model }))}
          placeholder={availableModels.length > 0 ? '选择或输入模型名称' : '请先拉取模型列表或手动输入'}
          filterOption={(inputValue, option) =>
            option?.value.toLowerCase().includes(inputValue.toLowerCase()) || false
          }
          notFoundContent="无匹配模型"
        />
      </Form.Item>

      <Form.Item>
        <Button
          type="dashed"
          icon={<CheckCircleOutlined />}
          onClick={handleTestConnection}
          loading={testingConnection}
          block
        >
          测试LLM连通性
        </Button>
      </Form.Item>
    </>
  )
}
