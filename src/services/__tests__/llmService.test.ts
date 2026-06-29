import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { llmService } from '../llmService'
import { LLMError } from '../../types/llm'
import { LLM_DEFAULTS } from '../../constants/llm'

describe('LLMService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    llmService.clearCache()
    global.fetch = vi.fn()
    ;(global.window as any) = { electronAPI: null }
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('call', () => {
    it('should throw LLMError when API credentials are missing', async () => {
      await expect(
        llmService.call({
          apiBase: '',
          apiKey: '',
          model: 'gpt-4',
          messages: [{ role: 'user', content: 'test' }],
        })
      ).rejects.toThrow(LLMError)
    })

    it('should call Electron IPC when available', async () => {
      const mockElectronAPI = {
        llmCall: vi.fn().mockResolvedValue({
          id: 'test-id',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [
            {
              index: 0,
              message: { role: 'assistant', content: 'Hello' },
              finish_reason: 'stop',
            },
          ],
        }),
      }
      ;(global.window as any).electronAPI = mockElectronAPI

      const result = await llmService.call({
        apiBase: 'https://api.openai.com/v1',
        apiKey: 'test-key',
        model: 'gpt-4',
        messages: [{ role: 'user', content: 'Hi' }],
      })

      expect(mockElectronAPI.llmCall).toHaveBeenCalledWith(
        expect.objectContaining({
          apiBase: 'https://api.openai.com/v1',
          apiKey: 'test-key',
          model: 'gpt-4',
          messages: [{ role: 'user', content: 'Hi' }],
          temperature: LLM_DEFAULTS.TEMPERATURE,
          timeout: LLM_DEFAULTS.TIMEOUT,
        })
      )
      expect(result.choices[0].message.content).toBe('Hello')
    })

    it('should require Electron IPC when gateway is unavailable', async () => {
      ;(global.window as any).electronAPI = null

      await expect(
        llmService.call({
          apiBase: 'https://api.openai.com/v1',
          apiKey: 'test-key',
          model: 'gpt-4',
          messages: [{ role: 'user', content: 'Hi' }],
        })
      ).rejects.toThrow('LLM Gateway requires Electron IPC')
      expect(global.fetch).not.toHaveBeenCalled()
    })

    it('should handle network errors gracefully', async () => {
      ;(global.window as any).electronAPI = {
        llmCall: vi.fn().mockRejectedValue(new Error('NETWORK: Network error')),
      }

      await expect(
        llmService.call({
          apiBase: 'https://api.openai.com/v1',
          apiKey: 'test-key',
          model: 'gpt-4',
          messages: [{ role: 'user', content: 'Hi' }],
        })
      ).rejects.toThrow(LLMError)
    })

    it('should handle timeout errors', async () => {
      vi.useFakeTimers()
      ;(global.window as any).electronAPI = {
        llmCall: vi.fn(() => new Promise(() => {})),
      }

      const assertion = expect(
        llmService.call({
          apiBase: 'https://api.openai.com/v1',
          apiKey: 'test-key',
          model: 'gpt-4',
          messages: [{ role: 'user', content: 'Hi' }],
          timeout: 50,
        })
      ).rejects.toThrow('Electron IPC timeout')
      await vi.advanceTimersByTimeAsync(10000)
      await assertion
      vi.useRealTimers()
    })

    it('should forward Azure configs through Electron IPC', async () => {
      const mockElectronAPI = {
        llmCall: vi.fn().mockResolvedValue({
          id: 'test-id',
          object: 'chat.completion',
          created: Date.now(),
          model: 'gpt-4',
          choices: [
            {
              index: 0,
              message: { role: 'assistant', content: 'test' },
              finish_reason: 'stop',
            },
          ],
        }),
      }
      ;(global.window as any).electronAPI = mockElectronAPI

      await llmService.call({
        apiBase: 'https://test.openai.azure.com/v1',
        apiKey: 'azure-key',
        model: 'gpt-4',
        messages: [{ role: 'user', content: 'Hi' }],
      })

      expect(mockElectronAPI.llmCall).toHaveBeenCalledWith(
        expect.objectContaining({
          apiBase: 'https://test.openai.azure.com/v1',
          apiKey: 'azure-key',
        })
      )
      expect(global.fetch).not.toHaveBeenCalled()
    })
  })

  describe('fetchModels', () => {
    it('should fetch models via Electron IPC', async () => {
      const mockElectronAPI = {
        llmFetchModels: vi.fn().mockResolvedValue({
          object: 'list',
          data: [
            { id: 'gpt-4', object: 'model' },
            { id: 'gpt-3.5-turbo', object: 'model' },
          ],
        }),
      }
      ;(global.window as any).electronAPI = mockElectronAPI

      const models = await llmService.fetchModels('https://api.openai.com/v1', 'test-key')

      expect(models).toEqual(['gpt-3.5-turbo', 'gpt-4'])
      expect(mockElectronAPI.llmFetchModels).toHaveBeenCalled()
    })

    it('should throw LLMError for invalid response format', async () => {
      const mockElectronAPI = {
        llmFetchModels: vi.fn().mockResolvedValue({ invalid: 'response' }),
      }
      ;(global.window as any).electronAPI = mockElectronAPI

      await expect(llmService.fetchModels('https://api.openai.com/v1', 'test-key')).rejects.toThrow(
        'Invalid models response'
      )
    })
  })

  describe('batchAnalyze', () => {
    it('should process items in batches', async () => {
      const items = Array.from({ length: 25 }, (_, i) => ({ id: i }))
      const batchFn = vi.fn().mockImplementation((batch: any) => Promise.resolve(batch))
      const onProgress = vi.fn()

      const result = await llmService.batchAnalyze(items, batchFn, onProgress)

      expect(result).toHaveLength(25)
      expect(batchFn).toHaveBeenCalledTimes(3)
      expect(onProgress).toHaveBeenCalled()
      expect(onProgress).toHaveBeenLastCalledWith(1)
    })

    it('should handle batch errors gracefully', async () => {
      const items = Array.from({ length: 15 }, (_, i) => ({ id: i }))
      const batchFn = vi.fn().mockImplementation((batch: any) => {
        if (batch[0].id === 10) {
          throw new Error('Batch error')
        }
        return Promise.resolve(batch)
      })

      const result = await llmService.batchAnalyze(items, batchFn)

      expect(result).toHaveLength(15)
      expect(batchFn).toHaveBeenCalledTimes(2)
    })

    it('should call onProgress with correct values', async () => {
      const items = Array.from({ length: 20 }, (_, i) => ({ id: i }))
      const batchFn = vi.fn().mockResolvedValue([])
      const progressValues: number[] = []
      const onProgress = vi.fn((p: number) => progressValues.push(p))

      await llmService.batchAnalyze(items, batchFn, onProgress)

      expect(progressValues.length).toBeGreaterThan(0)
      expect(progressValues[progressValues.length - 1]).toBe(1)
    })
  })
})
