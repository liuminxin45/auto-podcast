// SoundStudio — Type Definitions
// Extracted from SoundStudio.tsx for maintainability.

export type StudioMode = 'ai' | 'recording'
export type VoiceProvider = 'edge_tts' | 'doubao_tts' | 'voice_clone'
export type VoiceStyle = 'natural' | 'steady' | 'deep' | 'relaxed' | 'warm' | 'energetic'
export type EmotionLevel = 'subtle' | 'moderate' | 'expressive'
export type SpeedLevel = 'slower' | 'normal' | 'faster'
export type PauseStyle = 'minimal' | 'natural' | 'dramatic'
export type BGMStyle = 'news' | 'interview' | 'latenight' | 'none'
export type BGMVolume = 'whisper' | 'background' | 'companion'
export type ExpressionTone = 'firm' | 'friendly' | 'calm'

export type SegmentRecordingStatus = 'empty' | 'recording' | 'recorded' | 'playing'
export type EditActionType = 'delete_selection' | 'trim_edges' | 'compress_pauses' | 'clean_silence' | 'remove_noise'
export type TransitionStyle = 'fade' | 'crossfade' | 'musical' | 'silence'
export type IntroOutroTemplate = 'professional' | 'casual' | 'minimal' | 'cinematic'
export type RightTab = 'voice' | 'atmosphere' | 'editing'

export interface TimelineSelection {
  startPos: number
  endPos: number
}

export interface EditHistoryEntry {
  id: string
  action: string
  timestamp: number
  description: string
}

export interface MusicInsertItem {
  id: string
  segmentId: string
  position: 'before' | 'after'
  style: TransitionStyle
}

export interface SegmentBGMOverride {
  segmentId: string
  style: string
  volume: BGMVolume
}

export interface ScriptSegment {
  id: string
  label: string
  icon: string
  color: string
  content: string
  estimatedSeconds: number
}

export interface RecordingSegment {
  segmentId: string
  status: SegmentRecordingStatus
  durationSeconds: number
  waveformData: number[]
  startedAtMs?: number
  audioUrl?: string
}

export interface ProduceProviderConfig {
  provider: VoiceProvider | 'openai_compatible'
  apiBase: string
  apiKey: string
  model: string
  requestTimeoutSec: number
  doubaoAppId: string
  doubaoAccessToken: string
  doubaoCluster: string
  doubaoVoiceType: string
  doubaoEndpoint: string
}

export type PersistedRecording = Omit<RecordingSegment, 'audioUrl' | 'startedAtMs'>

export type SoundStudioDraft = {
  mode: StudioMode
  voiceProvider: VoiceProvider
  voiceStyle: VoiceStyle
  emotionLevel: EmotionLevel
  speedLevel: SpeedLevel
  pauseStyle: PauseStyle
  expressionTone: ExpressionTone | null
  bgmStyle: BGMStyle
  bgmVolume: BGMVolume
  enableIntro: boolean
  enableOutro: boolean
  activeSegmentId: string
  recordings: Record<string, PersistedRecording>
  rightTab: RightTab
  timelineSelection: TimelineSelection | null
  editHistory: EditHistoryEntry[]
  editHistoryIndex: number
  musicInserts: MusicInsertItem[]
  segmentBGMOverrides: Record<string, SegmentBGMOverride>
  introTemplate: IntroOutroTemplate
  outroTemplate: IntroOutroTemplate
  transitionStyle: TransitionStyle
}
