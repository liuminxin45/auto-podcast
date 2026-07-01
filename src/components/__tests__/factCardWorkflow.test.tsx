import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import CreationStudio from '../CreationStudio'
import PublishLayer from '../PublishLayer'
import WritingLayer from '../writing'
import type { FactCard, PodcastState, Workflow } from '../../types/workflow'

function createWorkflow(state: Partial<PodcastState>): Workflow {
  return {
    id: 'workflow_test',
    status: 'draft',
    currentNode: null,
    nodeExecutions: {},
    state: {
      episode_id: 'episode_test',
      created_at: '2026-07-01T00:00:00.000Z',
      schema_version: 1,
      preset: {},
      source_inputs: [],
      runtime_config: {},
      logs: [],
      errors: [],
      fetch_contents: [],
      manual_contents: [],
      raw_contents: [],
      cleaned_contents: [],
      researched_contents: [],
      facts: [],
      selected_topic: {},
      selected_topics: [],
      selected_materials: [],
      script: {},
      edited_script: {},
      stages: [],
      voice_segments: [],
      audio_segments: [],
      final_audio_path: '',
      audio_metadata: {},
      audio_outputs: {},
      audio_report_path: '',
      cover_path: '',
      intro_outro_paths: {},
      review_summary: {},
      storage_info: {},
      rss_path: '',
      publish_status: {},
      publish_outputs: {},
      subtitle_path: '',
      run_report: {},
      migration_warnings: [],
      tts_source: '',
      ...state,
    },
  }
}

const facts: FactCard[] = [
  {
    id: 'fact_001',
    title: '央行发布流动性操作',
    summary: '央行公告公开市场操作，维持市场流动性合理充裕。',
    source_title: '财经日报',
    source_url: 'https://example.com/a',
    published_at: '2026-07-01T07:00:00.000Z',
    claim: '央行公告公开市场操作。',
    confidence: 'high',
  },
  {
    id: 'fact_002',
    title: '科技公司更新模型能力',
    summary: '一家科技公司发布新模型能力更新。',
    source_title: '科技日报',
    source_url: 'https://example.com/b',
    published_at: '2026-07-01T07:05:00.000Z',
    claim: '科技公司发布新模型能力。',
    confidence: 'medium',
  },
  {
    id: 'fact_003',
    title: '能源价格小幅波动',
    summary: '能源价格在亚洲早盘小幅波动。',
    source_title: '市场快讯',
    source_url: 'https://example.com/c',
    published_at: '2026-07-01T07:10:00.000Z',
    claim: '能源价格小幅波动。',
    confidence: 'high',
  },
]

describe('FactCard-first workflow surfaces', () => {
  it('renders CreationStudio facts and can trigger the facts node', async () => {
    const onRunNodes = vi.fn().mockResolvedValue(undefined)

    render(
      <CreationStudio
        visible
        onClose={vi.fn()}
        rawContents={[
          { title: '央行发布流动性操作', summary: '央行公告公开市场操作。', url: 'https://example.com/a', source: '财经日报' },
          { title: '科技公司更新模型能力', summary: '科技公司发布新模型能力。', url: 'https://example.com/b', source: '科技日报' },
        ]}
        initialFacts={facts}
        initialSelectedTopics={facts.map((fact, index) => ({ id: `topic_${index + 1}`, title: fact.title, fact_id: fact.id }))}
        onRunNodes={onRunNodes}
      />,
    )

    expect(screen.getByText('事实卡片与早报编排')).toBeTruthy()
    expect(screen.getByText('FactCard board')).toBeTruthy()
    expect(screen.getAllByText('央行发布流动性操作').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('新闻 1')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /生成事实卡片/ }))

    await waitFor(() => {
      expect(onRunNodes).toHaveBeenCalledWith(['facts'])
    })
  })

  it('saves WritingLayer edits into edited_script without overwriting generated script', async () => {
    const onSaveDraft = vi.fn().mockResolvedValue(undefined)
    const workflow = createWorkflow({
      script: {
        id: 'script_generated',
        title: '早报标题',
        description: '早报简介',
        segments: [
          {
            id: 'seg_opening',
            type: 'opening',
            title: '开场导语',
            text: '大家早上好，欢迎收听今天的通勤早咖啡。',
            source_fact_ids: [],
            estimated_seconds: 20,
          },
          {
            id: 'seg_news_1',
            type: 'news_item',
            title: '央行发布流动性操作',
            text: '第一条新闻，央行公告公开市场操作，维持市场流动性合理充裕。',
            source_fact_ids: ['fact_001'],
            estimated_seconds: 45,
          },
          {
            id: 'seg_closing',
            type: 'closing',
            title: '结尾总结',
            text: '以上就是今天的重点，祝你通勤顺利。',
            source_fact_ids: [],
            estimated_seconds: 20,
          },
        ],
      },
      facts,
    })

    render(
      <WritingLayer
        visible
        onClose={vi.fn()}
        workflow={workflow}
        onSaveDraft={onSaveDraft}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('fact_001')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '存' }))

    await waitFor(() => {
      expect(onSaveDraft).toHaveBeenCalled()
    })

    const patch = onSaveDraft.mock.calls[0][0]
    expect(patch.script).toBeUndefined()
    expect(patch.edited_script.edited_from).toBe('script_generated')
    expect(patch.edited_script.segments.find((segment: any) => segment.id === 'seg_news_1').source_fact_ids).toEqual(['fact_001'])
    expect(patch.stages.find((stage: any) => stage.id === 'seg_news_1').source_fact_ids).toEqual(['fact_001'])
  }, 15000)

  it('renders RSS validation and local-preview status in PublishLayer', async () => {
    const workflow = createWorkflow({
      script: { title: '早报标题', description: '早报简介' },
      stages: [{ id: 'seg_news_1', order: 1, speaker: 'Host A', text: '第一条新闻。' }],
      final_audio_path: 'out/episodes/episode_test/final.mp3',
      publish_outputs: {
        enclosure_url: 'dist/episodes/episode_test/final.mp3',
        rss_validation: {
          ok: true,
          errors: [],
          warnings: ['public_base_url is empty; RSS feed is local-preview only'],
          enclosure_url: 'dist/episodes/episode_test/final.mp3',
          local_preview_only: true,
        },
      },
    })

    render(
      <PublishLayer
        visible
        onClose={vi.fn()}
        workflow={workflow}
        onRunNodes={vi.fn().mockResolvedValue(undefined)}
      />,
    )

    fireEvent.click(screen.getByText('开始智能审查'))
    fireEvent.click(await screen.findByText('跳过这一步'))

    await waitFor(() => {
      expect(screen.getByText('RSS 校验状态')).toBeTruthy()
      expect(screen.getByText(/local-preview only/)).toBeTruthy()
      expect(screen.getByText(/dist\/episodes\/episode_test\/final\.mp3/)).toBeTruthy()
    })
  })
})
