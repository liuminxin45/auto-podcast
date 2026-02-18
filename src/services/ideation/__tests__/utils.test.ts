import { describe, it, expect } from 'vitest'
import { parseJSONFromLLM, validateIdeationResult, cleanLLMText } from '../utils'

describe('parseJSONFromLLM', () => {
  it('should parse clean JSON', () => {
    const json = '{"topic": {"title": "Test"}, "blocks": []}'
    const result = parseJSONFromLLM(json)
    expect(result).toEqual({ topic: { title: 'Test' }, blocks: [] })
  })

  it('should remove markdown code blocks', () => {
    const json = '```json\n{"topic": {"title": "Test"}, "blocks": []}\n```'
    const result = parseJSONFromLLM(json)
    expect(result).toEqual({ topic: { title: 'Test' }, blocks: [] })
  })

  it('should handle leading/trailing text', () => {
    const json = 'Here is the result:\n{"topic": {"title": "Test"}, "blocks": []}\nDone!'
    const result = parseJSONFromLLM(json)
    expect(result).toEqual({ topic: { title: 'Test' }, blocks: [] })
  })

  it('should throw on invalid JSON', () => {
    expect(() => parseJSONFromLLM('not json')).toThrow()
  })

  it('should normalize Chinese quotes to English quotes', () => {
    const json = '{"topic": {"title": "春晚机器人出圈：一场技术秀背后的产业博弈"}, "blocks": []}'
    const result = parseJSONFromLLM(json)
    expect(result.topic.title).toBe('春晚机器人出圈:一场技术秀背后的产业博弈')
  })

  it('should normalize Chinese punctuation (comma and colon)', () => {
    const json = '{"topic"：{"title"："测试"}，"blocks"：[]}'
    const result = parseJSONFromLLM(json)
    expect(result).toEqual({ topic: { title: '测试' }, blocks: [] })
  })

  it('should convert single quotes to double quotes in JSON keys', () => {
    const json = "{'topic': {'title': '测试'}, 'blocks': []}"
    const result = parseJSONFromLLM(json)
    expect(result).toEqual({ topic: { title: '测试' }, blocks: [] })
  })

  it('should handle array with single quotes', () => {
    const json = "{'key_points': ['对手的相对位置', '从追赶者到并行者']}"
    const result = parseJSONFromLLM(json)
    expect(result).toEqual({ key_points: ['对手的相对位置', '从追赶者到并行者'] })
  })

  it('should handle complex nested structure with single quotes', () => {
    const json = "{'topic': {'title': '春晚机器人出圈', 'description': '解析中国智造'}, 'blocks': [{'type': 'opening', 'title': '开场'}]}"
    const result = parseJSONFromLLM(json)
    expect(result).toEqual({
      topic: { title: '春晚机器人出圈', description: '解析中国智造' },
      blocks: [{ type: 'opening', title: '开场' }]
    })
  })
})

describe('validateIdeationResult', () => {
  it('should validate correct structure', () => {
    const valid = {
      topic: { title: 'Test', description: 'Desc' },
      blocks: [{ id: '1', type: 'opening', title: 'Block 1' }]
    }
    const result = validateIdeationResult(valid)
    expect(result.valid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('should detect missing topic', () => {
    const invalid = { blocks: [] }
    const result = validateIdeationResult(invalid)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('缺少 topic 字段')
  })

  it('should detect missing blocks', () => {
    const invalid = { topic: { title: 'Test', description: 'Desc' } }
    const result = validateIdeationResult(invalid)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('blocks 必须是数组')
  })

  it('should detect empty blocks', () => {
    const invalid = { topic: { title: 'Test', description: 'Desc' }, blocks: [] }
    const result = validateIdeationResult(invalid)
    expect(result.valid).toBe(false)
    expect(result.errors).toContain('blocks 不能为空')
  })
})

describe('cleanLLMText', () => {
  it('should trim whitespace', () => {
    expect(cleanLLMText('  test  ')).toBe('test')
  })

  it('should normalize line breaks', () => {
    expect(cleanLLMText('line1\r\nline2')).toBe('line1\nline2')
  })

  it('should collapse multiple newlines', () => {
    expect(cleanLLMText('line1\n\n\n\nline2')).toBe('line1\n\nline2')
  })

  it('should collapse multiple spaces', () => {
    expect(cleanLLMText('word1    word2')).toBe('word1 word2')
  })
})
