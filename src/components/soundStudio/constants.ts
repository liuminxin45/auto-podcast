// SoundStudio — Constants
// Extracted from SoundStudio.tsx for maintainability.

import type {
  VoiceStyle, VoiceProvider, EmotionLevel, SpeedLevel, PauseStyle,
  BGMStyle, BGMVolume, ExpressionTone, EditActionType, TransitionStyle,
  IntroOutroTemplate, ScriptSegment,
} from './types'

export const VOICE_STYLES: Array<{ key: VoiceStyle; label: string; desc: string; icon: string }> = [
  { key: 'natural', label: '自然', desc: '日常对话感，真实亲切', icon: '🗣️' },
  { key: 'steady', label: '稳重', desc: '沉稳有力，像资深主播', icon: '🎙️' },
  { key: 'deep', label: '深度', desc: '低沉磁性，引人深思', icon: '🌊' },
  { key: 'relaxed', label: '轻松', desc: '慵懒随意，像深夜电台', icon: '☕' },
  { key: 'warm', label: '温暖', desc: '柔和关怀，让人安心', icon: '🌅' },
  { key: 'energetic', label: '活力', desc: '充满激情，富有感染力', icon: '⚡' },
]

export const VOICE_PROVIDERS: Array<{ key: VoiceProvider; label: string; desc: string; badge?: string }> = [
  { key: 'edge_tts', label: '标准 TTS', desc: '稳定快速，适合日常批量生成', badge: '稳' },
  { key: 'doubao_tts', label: '豆包音色', desc: '更自然细腻，适合叙事与评论', badge: '质' },
  { key: 'voice_clone', label: '克隆声音', desc: '人格化表达，打造专属主播感', badge: 'IP' },
]

export const VOICE_PROVIDER_LABELS: Record<VoiceProvider, string> = {
  edge_tts: '标准 TTS',
  doubao_tts: '豆包音色',
  voice_clone: '克隆声音',
}

export const EMOTION_LEVELS: Array<{ key: EmotionLevel; label: string; desc: string }> = [
  { key: 'subtle', label: '克制', desc: '平稳内敛' },
  { key: 'moderate', label: '适中', desc: '自然流露' },
  { key: 'expressive', label: '丰富', desc: '情感饱满' },
]

export const SPEED_LEVELS: Array<{ key: SpeedLevel; label: string }> = [
  { key: 'slower', label: '稍慢' },
  { key: 'normal', label: '正常' },
  { key: 'faster', label: '稍快' },
]

export const PAUSE_STYLES: Array<{ key: PauseStyle; label: string; desc: string }> = [
  { key: 'minimal', label: '紧凑', desc: '段落间几乎不停顿' },
  { key: 'natural', label: '自然', desc: '像正常说话一样' },
  { key: 'dramatic', label: '留白', desc: '适当留出思考空间' },
]

export const BGM_STYLES: Array<{ key: BGMStyle; label: string; icon: string; desc: string }> = [
  { key: 'news', label: '新闻风', icon: '📰', desc: '节奏明快，信息感强' },
  { key: 'interview', label: '访谈风', icon: '🎤', desc: '轻柔铺底，不抢注意力' },
  { key: 'latenight', label: '深夜电台', icon: '🌙', desc: '舒缓悠远，氛围感十足' },
  { key: 'none', label: '无音乐', icon: '🔇', desc: '纯人声，干净直接' },
]

export const BGM_VOLUMES: Array<{ key: BGMVolume; label: string }> = [
  { key: 'whisper', label: '极轻' },
  { key: 'background', label: '铺底' },
  { key: 'companion', label: '陪伴' },
]

export const EXPRESSION_TONES: Array<{ key: ExpressionTone; label: string; icon: string }> = [
  { key: 'firm', label: '更坚定', icon: '💪' },
  { key: 'friendly', label: '更亲切', icon: '🤗' },
  { key: 'calm', label: '更冷静', icon: '🧊' },
]

export const QUICK_EDIT_ACTIONS: Array<{ key: EditActionType; label: string; icon: string; desc: string; color: string }> = [
  { key: 'trim_edges', label: '裁掉多余', icon: '✂️', desc: '去除开头结尾的空白', color: '#8b5cf6' },
  { key: 'compress_pauses', label: '缩短停顿', icon: '⏩', desc: '把过长的沉默变紧凑', color: '#f59e0b' },
  { key: 'clean_silence', label: '清理空白', icon: '🧹', desc: '自动去除无声片段', color: '#10b981' },
  { key: 'remove_noise', label: '去除杂音', icon: '✨', desc: '让声音更干净清晰', color: '#2563eb' },
]

export const TRANSITION_STYLES: Array<{ key: TransitionStyle; label: string; icon: string; desc: string }> = [
  { key: 'fade', label: '淡入淡出', icon: '🌅', desc: '柔和过渡' },
  { key: 'crossfade', label: '交叉融合', icon: '🔀', desc: '前后声音融合' },
  { key: 'musical', label: '音乐过渡', icon: '🎵', desc: '用一小段旋律衔接' },
  { key: 'silence', label: '自然留白', icon: '💭', desc: '短暂的安静' },
]

export const INTRO_TEMPLATES: Array<{ key: IntroOutroTemplate; label: string; icon: string; desc: string; duration: string }> = [
  { key: 'professional', label: '专业范', icon: '🏢', desc: '新闻播报感开场', duration: '5秒' },
  { key: 'casual', label: '轻松聊', icon: '☕', desc: '朋友闲聊的氛围', duration: '4秒' },
  { key: 'minimal', label: '极简风', icon: '🎯', desc: '干净利落，直入主题', duration: '3秒' },
  { key: 'cinematic', label: '电影感', icon: '🎬', desc: '有故事氛围的开场', duration: '6秒' },
]

export const SEGMENT_BGM_OPTIONS: Array<{ key: string; label: string; icon: string }> = [
  { key: 'same', label: '跟随全局', icon: '🔗' },
  { key: 'tension', label: '紧张感', icon: '⚡' },
  { key: 'warm', label: '温暖', icon: '🌅' },
  { key: 'reflective', label: '沉思', icon: '💭' },
  { key: 'none', label: '纯人声', icon: '🔇' },
]

export const DEMO_SEGMENTS: ScriptSegment[] = [
  { id: 'seg_opening', label: '开场', icon: '🎬', color: '#f59e0b', content: '欢迎来到本期节目，今天我们来聊一个很多人都在关注的话题…', estimatedSeconds: 90 },
  { id: 'seg_main1', label: '主线一', icon: '📌', color: '#2563eb', content: '首先，让我们从最核心的问题说起…', estimatedSeconds: 180 },
  { id: 'seg_main2', label: '主线二', icon: '📌', color: '#8b5cf6', content: '接下来，我想从另一个角度来看这件事…', estimatedSeconds: 180 },
  { id: 'seg_discuss', label: '延伸讨论', icon: '💬', color: '#06b6d4', content: '说到这里，其实还有一个很值得思考的点…', estimatedSeconds: 150 },
  { id: 'seg_closing', label: '结尾', icon: '🎤', color: '#10b981', content: '好了，今天就聊到这里。希望这期节目能给你一些新的思考…', estimatedSeconds: 60 },
]

export const SEGMENT_VISUAL_MAP: Record<string, { icon: string; color: string }> = {
  opening: { icon: '🎬', color: '#f59e0b' },
  mainline: { icon: '📌', color: '#2563eb' },
  main_1: { icon: '📌', color: '#2563eb' },
  main_2: { icon: '📌', color: '#8b5cf6' },
  discussion: { icon: '💬', color: '#06b6d4' },
  news_item: { icon: '🗞️', color: '#0ea5e9' },
  closing: { icon: '🎤', color: '#10b981' },
  custom: { icon: '📝', color: '#64748b' },
}
