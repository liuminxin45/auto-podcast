"""
Audio Step (Segmented Version)

音频生成步骤 - 分段版本
为每个段落生成TTS，然后合并为完整播客
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from src.app.pipelines.base_step import BaseStep
from src.models.segment import SegmentAudio, BGMInsert, EpisodeManifest, SEGMENT_ORDER
from src.audio.segment_merger import merge_episode_with_bgm, AudioMerger

if TYPE_CHECKING:
    from src.app.core.context import EpisodeContext


class AudioStepSegmented(BaseStep):
    """音频生成步骤（分段版本）"""
    
    def execute(self, ctx: EpisodeContext) -> None:
        """执行 Audio 步骤"""
        if not hasattr(ctx, 'script_segments') or not ctx.script_segments:
            self.logger.warning("没有脚本段落，跳过音频生成")
            ctx.audio_manifest = None
            return
        
        self.logger.info(f"开始分段音频生成：{len(ctx.script_segments)} 个段落")
        
        # 创建输出目录
        tts_dir = ctx.run_dir / "4_tts" / "segments"
        tts_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成每个段落的TTS
        segment_audios = []
        for segment_script in ctx.script_segments:
            try:
                audio = self._generate_segment_tts(ctx, segment_script, tts_dir)
                segment_audios.append(audio)
            except Exception as e:
                self.logger.error(f"段落 {segment_script.id} TTS失败: {e}")
                # 关键段落失败则停止
                if segment_script.id in ["S0", "S1"]:
                    raise RuntimeError(f"关键段落 {segment_script.id} TTS失败: {e}")
        
        # 准备BGM
        bgm_inserts = self._prepare_bgm(ctx)
        
        # 合并音频
        final_path = self._merge_segments(ctx, segment_audios, bgm_inserts)
        
        # 创建manifest
        manifest = EpisodeManifest(
            episode_id=ctx.episode_id,
            segments=segment_audios,
            bgm=bgm_inserts,
            final_path=str(final_path),
            created_at=datetime.now().isoformat(),
        )
        
        # 计算总时长
        merger = AudioMerger()
        manifest.total_duration_ms = merger.get_audio_duration(final_path)
        
        # 保存manifest
        manifest_path = ctx.run_dir / "4_tts" / "manifest.json"
        manifest.save(str(manifest_path))
        
        # 保存到context
        ctx.audio_manifest = manifest
        ctx.audio_paths = {
            "final": str(final_path),
            "manifest": str(manifest_path),
        }
        
        self.logger.info(f"音频生成完成: {len(segment_audios)} 个段落, 总时长 {manifest.total_duration_ms/1000:.1f}秒")
        ctx.add_event("audio_segments_generated",
                     segments_count=len(segment_audios),
                     total_duration_ms=manifest.total_duration_ms)
    
    def _generate_segment_tts(
        self,
        ctx: EpisodeContext,
        segment_script,
        segments_dir: Path
    ) -> SegmentAudio:
        """生成单个段落的TTS"""
        from src.utils.logging_config import log_api_call, log_operation
        
        segment_id = segment_script.id
        output_path = segments_dir / f"{segment_id}.mp3"
        
        # 检查缓存
        if output_path.exists():
            log_operation(
                self.logger,
                step="Audio",
                operation=f"tts_{segment_id}",
                result="使用缓存"
            )
            merger = AudioMerger()
            duration_ms = merger.get_audio_duration(output_path)
            return SegmentAudio(
                segment_id=segment_id,
                mp3_path=str(output_path),
                duration_ms=duration_ms,
                gen_ms=0,
                tts_ms=0,
                cached=True
            )
        
        # 生成TTS
        text = segment_script.text
        char_count = len(text)
        
        log_api_call(
            self.logger,
            api_type="TTS",
            operation=f"synthesize_{segment_id}",
            char_count=char_count
        )
        
        start_time = time.time()
        
        try:
            audio_bytes = self._call_tts(ctx, text)
            output_path.write_bytes(audio_bytes)
            
            gen_ms = int((time.time() - start_time) * 1000)
            
            # 获取音频时长
            merger = AudioMerger()
            duration_ms = merger.get_audio_duration(output_path)
            
            self.logger.info(f"✓ {segment_id} TTS完成: {duration_ms/1000:.1f}秒, 耗时 {gen_ms}ms")
            
            return SegmentAudio(
                segment_id=segment_id,
                mp3_path=str(output_path),
                duration_ms=duration_ms,
                gen_ms=gen_ms,
                tts_ms=gen_ms,  # 简化：gen_ms = tts_ms
                cached=False
            )
            
        except Exception as e:
            self.logger.error(f"✗ {segment_id} TTS失败: {e}")
            raise
    
    def _call_tts(self, ctx: EpisodeContext, text: str) -> bytes:
        """调用TTS服务"""
        cfg = ctx.config
        timeout_s = int(cfg.get("llm", {}).get("timeout_seconds", 120))
        
        # 获取 Doubao 模式
        doubao_mode_env = os.environ.get("DOUBAO_MODE")
        if doubao_mode_env is not None and doubao_mode_env.strip():
            doubao_mode = doubao_mode_env.strip().lower()
        else:
            rid = (os.environ.get("DOUBAO_RESOURCE_ID") or "").strip()
            ws_url = (os.environ.get("DOUBAO_WS_URL") or "").strip()
            if rid == "volc.service_type.10050" or ("podcasttts" in ws_url):
                doubao_mode = "podcast"
            else:
                doubao_mode = "tts"
        
        # 根据模式调用TTS
        if doubao_mode == "podcast":
            return self._tts_podcast(text, timeout_s)
        elif doubao_mode == "voiceclone_http":
            return self._tts_voiceclone(text, timeout_s)
        elif doubao_mode in {"tts", "tts_v3_http"}:
            return self._tts_v3_http(ctx, text, timeout_s)
        elif doubao_mode == "tts_v3_ws":
            return self._tts_v3_ws(ctx, text, timeout_s)
        else:
            raise RuntimeError(f"未知的 DOUBAO_MODE={doubao_mode}")
    
    def _tts_podcast(self, text: str, timeout_s: int) -> bytes:
        """Podcast 模式 TTS"""
        from src.tts.tts_client import TTSClientFactory
        
        client = TTSClientFactory.create_doubao_podcast_client(timeout_seconds=timeout_s)
        text = self._strip_angle_tags(text)
        result = client.synthesize(text, mode="podcast")
        return result.audio_data
    
    def _tts_voiceclone(self, text: str, timeout_s: int) -> bytes:
        """VoiceClone 模式 TTS"""
        from src.tts.tts_client import TTSClientFactory
        
        client = TTSClientFactory.create_doubao_podcast_client(timeout_seconds=timeout_s)
        speaker_id = (os.environ.get("DOUBAO_VOICECLONE_SPEAKER_ID") or "").strip()
        result = client.synthesize(text, mode="voiceclone_http", speaker_id=speaker_id)
        return result.audio_data
    
    def _tts_v3_http(self, ctx: EpisodeContext, text: str, timeout_s: int) -> bytes:
        """TTS V3 HTTP 模式"""
        from src.tts.tts_client import TTSClientFactory
        
        client = TTSClientFactory.create_doubao_podcast_client(timeout_seconds=timeout_s)
        voice_cfg = (ctx.config.get("tts") or {}).get("voice") or ""
        voice = voice_cfg.get("default", "") if isinstance(voice_cfg, dict) else str(voice_cfg).strip()
        result = client.synthesize(text, mode="tts_v3_http", speaker=voice)
        return result.audio_data
    
    def _tts_v3_ws(self, ctx: EpisodeContext, text: str, timeout_s: int) -> bytes:
        """TTS V3 WebSocket 模式"""
        from src.tts.tts_client import TTSClientFactory
        
        voice_cfg = (ctx.config.get("tts") or {}).get("voice") or ""
        voice = voice_cfg.get("default", "") if isinstance(voice_cfg, dict) else str(voice_cfg).strip()
        client = TTSClientFactory.create_doubao_client(voice_type=voice, timeout_seconds=timeout_s)
        
        try:
            result = client.synthesize(text, mode="tts_v3_ws")
            return result.audio_data
        except Exception as e:
            if "text too long" in str(e):
                self.logger.warning("文本过长，使用分块模式")
                result = client.synthesize(text, mode="default")
                return result.audio_data
            raise
    
    def _prepare_bgm(self, ctx: EpisodeContext) -> List[BGMInsert]:
        """准备BGM"""
        cfg = ctx.config
        audio_cfg = cfg.get("audio", {})
        assets_dir = Path(audio_cfg.get("assets_dir", "./assets"))
        
        bgm_inserts = []
        
        # Transition BGM (在S1->S2, S2->S3, S3->S4, S4->S5之间)
        transition_path = assets_dir / "bgm" / "transition.mp3"
        if transition_path.exists():
            for insert_after in ["S1", "S2", "S3", "S4"]:
                bgm_inserts.append(BGMInsert(
                    name="transition",
                    path=str(transition_path),
                    insert_after=insert_after
                ))
        else:
            self.logger.warning(f"Transition BGM not found: {transition_path}")
        
        # Outro BGM (在S5之后)
        outro_path = assets_dir / "bgm" / "outro.mp3"
        if outro_path.exists():
            bgm_inserts.append(BGMInsert(
                name="outro",
                path=str(outro_path),
                insert_after="S5"
            ))
        else:
            self.logger.warning(f"Outro BGM not found: {outro_path}")
        
        return bgm_inserts
    
    def _merge_segments(
        self,
        ctx: EpisodeContext,
        segment_audios: List[SegmentAudio],
        bgm_inserts: List[BGMInsert]
    ) -> Path:
        """合并所有段落"""
        self.logger.info("开始合并音频段落...")
        
        # 准备段落路径
        segment_paths = [Path(audio.mp3_path) for audio in segment_audios]
        
        # 准备BGM路径
        transition_bgms = []
        outro_bgm = None
        
        for bgm in bgm_inserts:
            if bgm.name == "transition":
                transition_bgms.append(Path(bgm.path))
            elif bgm.name == "outro":
                outro_bgm = Path(bgm.path)
        
        # 输出路径
        final_dir = ctx.run_dir / "5_render"
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / f"{ctx.episode_date}.final.mp3"
        
        # 合并
        cfg = ctx.config
        timeout_s = int(cfg.get("llm", {}).get("timeout_seconds", 120))
        
        total_duration_ms = merge_episode_with_bgm(
            segments=segment_paths,
            bgm_transitions=transition_bgms if transition_bgms else None,
            bgm_outro=outro_bgm,
            output_path=final_path,
            timeout_seconds=timeout_s
        )
        
        self.logger.info(f"✓ 合并完成: {final_path}, 总时长 {total_duration_ms/1000:.1f}秒")
        
        return final_path
    
    @staticmethod
    def _strip_angle_tags(text: str) -> str:
        """移除 SSML 标签"""
        return re.sub(r"<[^>]+>", "", text)
