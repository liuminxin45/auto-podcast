import { Form, Input, InputNumber, Switch, Space, Button, Select } from 'antd'
import { useEffect, useState } from 'react'
import FetchSourcesConfig from './FetchSourcesConfig'
import LLMConfigFields from './LLMConfigFields'
import ManualNewsConfig from './ManualNewsConfig'

interface FieldSchema {
  type: string
  description?: string
  default?: any
  required?: boolean
  optional?: boolean
  min?: number
  max?: number
  minLength?: number
  maxLength?: number
  items?: FieldSchema
}

interface Props {
  nodeName: string
  initialValues?: Record<string, any>
  onSubmit?: (values: Record<string, any>) => void
  onChange?: (values: Record<string, any>) => void
}

export default function DynamicConfigForm({ nodeName, initialValues, onChange, onSubmit }: Props) {
  const [form] = Form.useForm()
  const [schema, setSchema] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadSchema()
  }, [nodeName])

  const loadSchema = async () => {
    try {
      setLoading(true)
      setError(null)
      const nodeSchema = await window.electronAPI.getNodeSchema(nodeName)
      
      if (nodeSchema.error) {
        setError(nodeSchema.error)
      } else {
        setSchema(nodeSchema)
        
        if (initialValues) {
          form.setFieldsValue(initialValues)
        } else if (nodeSchema.fields) {
          const defaults: Record<string, any> = {}
          Object.entries(nodeSchema.fields).forEach(([key, field]: [string, any]) => {
            if (field.default !== null && field.default !== undefined) {
              defaults[key] = field.default
            }
          })
          form.setFieldsValue(defaults)
        }
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleValuesChange = (_: any, allValues: any) => {
    if (onChange) {
      onChange(allValues)
    }
  }

  const handleSubmit = (values: any) => {
    if (onSubmit) {
      onSubmit(values)
    }
  }

  // 检测是否包含LLM配置字段组（llm_model, api_key, api_base）
  const hasLLMFields = () => {
    if (!schema || !schema.fields) return false
    const fields = Object.keys(schema.fields)
    return fields.includes('llm_model') && fields.includes('api_key') && fields.includes('api_base')
  }

  const renderField = (fieldName: string, fieldSchema: FieldSchema) => {
    const label = fieldName.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    const rules = [
      { required: fieldSchema.required && !fieldSchema.optional, message: `${label} is required` }
    ]

    // 特殊处理：fetch节点的enabled_sources字段使用专门的组件
    if (nodeName === 'fetch' && fieldName === 'enabled_sources') {
      return (
        <Form.Item
          key={fieldName}
          name={fieldName}
          label="数据源"
          tooltip={fieldSchema.description}
        >
          <FetchSourcesConfig />
        </Form.Item>
      )
    }

    // 特殊处理：manual节点的news_items字段使用专门的组件
    if (nodeName === 'manual' && fieldName === 'news_items') {
      return (
        <Form.Item
          key={fieldName}
          name={fieldName}
          label="新闻列表"
          tooltip={fieldSchema.description}
        >
          <ManualNewsConfig />
        </Form.Item>
      )
    }

    // 特殊处理：source_selector节点的source_type字段使用Select
    if (nodeName === 'source_selector' && fieldName === 'source_type') {
      return (
        <Form.Item
          key={fieldName}
          name={fieldName}
          label="内容来源"
          tooltip={fieldSchema.description}
        >
          <Select
            options={[
              { value: 'fetch', label: '🔍 自动抓取 (Fetch)' },
              { value: 'manual', label: '✍️ 手动输入 (Manual)' }
            ]}
          />
        </Form.Item>
      )
    }

    // 跳过LLM配置字段，它们会被LLMConfigFields组件统一处理
    if (hasLLMFields() && ['llm_model', 'api_key', 'api_base'].includes(fieldName)) {
      return null
    }

    switch (fieldSchema.type) {
      case 'boolean':
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            valuePropName="checked"
            tooltip={fieldSchema.description}
          >
            <Switch />
          </Form.Item>
        )

      case 'integer':
      case 'number':
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            rules={rules}
            tooltip={fieldSchema.description}
          >
            <InputNumber
              style={{ width: '100%' }}
              min={fieldSchema.min}
              max={fieldSchema.max}
              step={fieldSchema.type === 'integer' ? 1 : 0.1}
            />
          </Form.Item>
        )

      case 'string':
        if (fieldName.toLowerCase().includes('password') || fieldName.toLowerCase().includes('key')) {
          return (
            <Form.Item
              key={fieldName}
              name={fieldName}
              label={label}
              rules={rules}
              tooltip={fieldSchema.description}
            >
              <Input.Password />
            </Form.Item>
          )
        }
        
        if (fieldName.toLowerCase().includes('url') || fieldName.toLowerCase().includes('path')) {
          return (
            <Form.Item
              key={fieldName}
              name={fieldName}
              label={label}
              rules={rules}
              tooltip={fieldSchema.description}
            >
              <Input placeholder={`Enter ${label.toLowerCase()}`} />
            </Form.Item>
          )
        }

        if (fieldSchema.maxLength && fieldSchema.maxLength > 100) {
          return (
            <Form.Item
              key={fieldName}
              name={fieldName}
              label={label}
              rules={rules}
              tooltip={fieldSchema.description}
            >
              <Input.TextArea rows={4} maxLength={fieldSchema.maxLength} />
            </Form.Item>
          )
        }

        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            rules={rules}
            tooltip={fieldSchema.description}
          >
            <Input maxLength={fieldSchema.maxLength} />
          </Form.Item>
        )

      case 'array':
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            tooltip={fieldSchema.description}
          >
            <Input.TextArea 
              rows={3} 
              placeholder="Enter JSON array, e.g., [1, 2, 3]"
            />
          </Form.Item>
        )

      case 'object':
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            tooltip={fieldSchema.description}
          >
            <Input.TextArea 
              rows={4} 
              placeholder="Enter JSON object, e.g., {&quot;key&quot;: &quot;value&quot;}"
            />
          </Form.Item>
        )

      default:
        return (
          <Form.Item
            key={fieldName}
            name={fieldName}
            label={label}
            rules={rules}
            tooltip={fieldSchema.description}
          >
            <Input />
          </Form.Item>
        )
    }
  }

  if (loading) {
    return <div style={{ padding: 16, textAlign: 'center' }}>Loading configuration schema...</div>
  }

  if (error) {
    return (
      <div style={{ padding: 16, color: '#ff4d4f' }}>
        <p>Failed to load configuration schema:</p>
        <p style={{ fontSize: 12, fontFamily: 'monospace' }}>{error}</p>
      </div>
    )
  }

  if (!schema || !schema.fields) {
    return <div style={{ padding: 16 }}>No configuration available for this node.</div>
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      onValuesChange={handleValuesChange}
      style={{ padding: '16px 0' }}
    >
      {/* LLM配置字段组 */}
      {hasLLMFields() && <LLMConfigFields />}

      {/* 其他字段 */}
      {schema && schema.fields && Object.entries(schema.fields).map(([fieldName, fieldSchema]) => renderField(fieldName, fieldSchema as FieldSchema))}
      
      {onSubmit && (
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">
              Save Configuration
            </Button>
            <Button onClick={() => form.resetFields()}>
              Reset
            </Button>
          </Space>
        </Form.Item>
      )}
    </Form>
  )
}
