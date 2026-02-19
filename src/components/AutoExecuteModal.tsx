import { useState } from 'react'
import { Modal, Input, Select, Radio, Button, Space, Typography, Alert } from 'antd'
import { PlayCircleOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { CONTENT_TYPE_META } from '../constants/contentCreation'
import type { ContentCreationType } from '../types/workflow'

const { TextArea } = Input
const { Text } = Typography

type VoiceProvider = 'edge_tts' | 'doubao_tts' | 'voice_clone'

export interface AutoExecuteConfig {
  coreTheme: string
  contentType: ContentCreationType
  voiceProvider: VoiceProvider
  timeRangeHours: number
}

interface Props {
  visible: boolean
  onClose: () => void
  onConfirm: (config: AutoExecuteConfig) => void
}

export default function AutoExecuteModal({ visible, onClose, onConfirm }: Props) {
  const [coreTheme, setCoreTheme] = useState('')
  const [contentType, setContentType] = useState<ContentCreationType>('story')
  const [voiceProvider, setVoiceProvider] = useState<VoiceProvider>('edge_tts')
  const [timeRangeHours, setTimeRangeHours] = useState<number>(72)

  const handleConfirm = () => {
    if (!coreTheme.trim()) {
      return
    }
    onConfirm({
      coreTheme: coreTheme.trim(),
      contentType,
      voiceProvider,
      timeRangeHours,
    })
    setCoreTheme('')
    setContentType('story')
    setVoiceProvider('edge_tts')
    setTimeRangeHours(72)
  }

  const handleCancel = () => {
    onClose()
  }

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <PlayCircleOutlined style={{ color: '#155eef', marginRight: 8 }} />
          <span>创建新节目 - 自动执行配置</span>
        </div>
      }
      open={visible}
      onCancel={handleCancel}
      width={600}
      footer={[
        <Button key="cancel" onClick={handleCancel}>
          取消
        </Button>,
        <Button
          key="start"
          type="primary"
          icon={<ThunderboltOutlined />}
          disabled={!coreTheme.trim()}
          onClick={handleConfirm}
        >
          开始创作
        </Button>,
      ]}
      maskClosable={false}
    >
      <div style={{ padding: '24px 0' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            type="info"
            message="全自动模式"
            description="系统将自动执行发现、整理、构思、写作、制作等所有环节，使用 AI 默认参数完成创作流程。"
            showIcon
          />

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              核心主题 <span style={{ color: '#ff4d4f' }}>*</span>
            </Text>
            <TextArea
              rows={3}
              placeholder="例如：DeepSeek 发布的最新影响"
              value={coreTheme}
              onChange={e => setCoreTheme(e.target.value)}
              style={{ fontSize: '14px' }}
            />
            <Text type="secondary" style={{ fontSize: '12px' }}>
              这将用于发现层的自动选题
            </Text>
          </div>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              新闻时效性
            </Text>
            <Select
              value={timeRangeHours}
              onChange={setTimeRangeHours}
              style={{ width: '100%' }}
              size="large"
              options={[
                {
                  value: 24,
                  label: (
                    <div>
                      <div style={{ fontWeight: 500 }}>⚡ 最近 24 小时</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        最新热点，实时性最强
                      </div>
                    </div>
                  ),
                },
                {
                  value: 72,
                  label: (
                    <div>
                      <div style={{ fontWeight: 500 }}>🔥 最近 3 天</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        平衡热度与深度，推荐选项
                      </div>
                    </div>
                  ),
                },
                {
                  value: 168,
                  label: (
                    <div>
                      <div style={{ fontWeight: 500 }}>📅 最近 7 天</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        覆盖面更广，适合深度话题
                      </div>
                    </div>
                  ),
                },
                {
                  value: 720,
                  label: (
                    <div>
                      <div style={{ fontWeight: 500 }}>🌐 最近 30 天</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        全面回顾，适合月度总结
                      </div>
                    </div>
                  ),
                },
              ]}
            />
            <Text type="secondary" style={{ fontSize: '12px', display: 'block', marginTop: 4 }}>
              控制抓取新闻的时间范围，影响内容的新鲜度
            </Text>
          </div>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              内容类型
            </Text>
            <Radio.Group
              value={contentType}
              onChange={e => setContentType(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Radio value="story" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '18px' }}>{CONTENT_TYPE_META.story.icon}</span>
                    <div>
                      <div style={{ fontWeight: 500 }}>{CONTENT_TYPE_META.story.label}</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        {CONTENT_TYPE_META.story.desc}
                      </div>
                    </div>
                  </div>
                </Radio>
                <Radio value="news_brief" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '18px' }}>{CONTENT_TYPE_META.news_brief.icon}</span>
                    <div>
                      <div style={{ fontWeight: 500 }}>{CONTENT_TYPE_META.news_brief.label}</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        {CONTENT_TYPE_META.news_brief.desc}
                      </div>
                    </div>
                  </div>
                </Radio>
              </Space>
            </Radio.Group>
          </div>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              声音创作方式
            </Text>
            <Select
              value={voiceProvider}
              onChange={setVoiceProvider}
              style={{ width: '100%' }}
              size="large"
              options={[
                {
                  value: 'edge_tts',
                  label: (
                    <div>
                      <div style={{ fontWeight: 500 }}>🎙️ Edge TTS</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        微软云端语音合成，快速且质量稳定
                      </div>
                    </div>
                  ),
                },
                {
                  value: 'doubao_tts',
                  label: (
                    <div>
                      <div style={{ fontWeight: 500 }}>🔊 豆包 TTS</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        字节跳动豆包语音，自然度更高
                      </div>
                    </div>
                  ),
                },
                {
                  value: 'voice_clone',
                  label: (
                    <div>
                      <div style={{ fontWeight: 500 }}>✨ 声音克隆</div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        使用预设或自定义音色进行克隆合成
                      </div>
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </Space>
      </div>
    </Modal>
  )
}
