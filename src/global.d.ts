import type { Workflow, WorkflowCreateResult, ContentItem } from './types/workflow'

declare global {
  interface LLMCallParams {
    apiBase: string
    apiKey: string
    model: string
    messages: Array<{ role: string; content: string }>
    temperature?: number
    maxTokens?: number
    timeout?: number
  }

  interface LLMResponse {
    choices: Array<{
      message: {
        content: string
      }
    }>
  }

  interface ProduceGeneratePayload {
    episodeId?: string
    voiceProvider?: 'edge_tts' | 'doubao_tts' | 'voice_clone'
    voiceStyle?: string
    emotionLevel?: string
    speedLevel?: 'slower' | 'normal' | 'faster'
    pauseStyle?: string
    expressionTone?: string | null
    segments: Array<{
      id: string
      type: string
      label: string
      content: string
      estimatedSeconds: number
    }>
    providerConfig?: {
      provider?: string
      apiBase?: string
      apiKey?: string
      model?: string
      requestTimeoutSec?: number
      doubaoAppId?: string
      doubaoAccessToken?: string
      doubaoCluster?: string
      doubaoVoiceType?: string
      doubaoEndpoint?: string
    }
  }

  interface ProduceGenerateResult {
    episodeId: string
    providerRequested: string
    providerApplied: string
    warnings: string[]
    audioSegments: string[]
    finalAudioPath: string
    audioMetadata: Record<string, unknown>
    logs: Array<{ level?: string; message: string }>
    errors: Array<{ node?: string; message: string }>
  }

  interface ProduceProgressData {
    episodeId: string
    stage: string
    status: 'running' | 'completed' | 'failed'
    progress: number
    detail: string
  }

  interface RadarState {
    enabled: boolean
    intervalMin: number
    keepLast: number
    lastRunAt: string | null
    lastError: string | null
    running: boolean
    contents: ContentItem[]
  }

  interface FetchSource {
    id: string
    name: string
    description: string
  }

  interface ElectronAPI {
    createWorkflow: (config: Record<string, any>) => Promise<WorkflowCreateResult>
    getWorkflow: (id: string) => Promise<Workflow | null>
    approveNode: (workflowId: string, nodeName: string, approved: boolean, modifiedOutput?: any) => Promise<{ status: string }>
    onWorkflowUpdate: (callback: (data: Workflow) => void) => void
    onNeedApproval: (callback: (data: any) => void) => void
    onRadarUpdate: (callback: (data: RadarState) => void) => void
    saveNodeConfig: (nodeName: string, config: Record<string, any>) => Promise<{ success: boolean; error?: string }>
    loadNodeConfig: (nodeName: string) => Promise<Record<string, any> | null>
    loadAllConfigs: () => Promise<Record<string, Record<string, any>>>
    deleteNodeConfig: (nodeName: string) => Promise<{ success: boolean; error?: string }>
    resetAllConfigs: () => Promise<{ success: boolean; error?: string }>
    getFetchSources: () => Promise<FetchSource[]>
    radarGetState: () => Promise<RadarState>
    radarStart: (config?: Record<string, any>) => Promise<any>
    radarStop: () => Promise<any>
    radarRunOnce: (config?: Record<string, any>) => Promise<any>
    radarClearContents: () => Promise<any>
    radarUpdateContents: (contents: ContentItem[]) => Promise<any>
    produceGenerate: (payload: ProduceGeneratePayload) => Promise<ProduceGenerateResult>
    onProduceProgress: (callback: (data: ProduceProgressData) => void) => void
    removeProduceProgressListeners: () => void
    llmCall: (params: LLMCallParams) => Promise<LLMResponse>
    llmFetchModels: (params: { apiBase: string; apiKey: string }) => Promise<any>
  }

  interface Window {
    electronAPI: ElectronAPI
    __DEBUG_MODE__?: boolean
  }
}

export {}
