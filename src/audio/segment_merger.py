"""
Audio Segment Merger

音频段落合并器：将多个音频段落和BGM合并为完整播客
"""

from __future__ import annotations

import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
import tempfile


logger = logging.getLogger(__name__)


class AudioMerger:
    """音频合并器（使用ffmpeg）"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.AudioMerger")
        
        # 检查ffmpeg
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found. Please install ffmpeg first.")
    
    def merge_segments(
        self,
        segments: List[Path],
        output_path: Path,
        timeout_seconds: int = 300
    ) -> None:
        """
        合并多个音频段落
        
        Args:
            segments: 音频文件路径列表（按顺序）
            output_path: 输出文件路径
            timeout_seconds: 超时时间
        """
        if not segments:
            raise ValueError("No segments to merge")
        
        self.logger.info(f"合并 {len(segments)} 个音频段落...")
        
        # 创建临时文件列表
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for seg in segments:
                if not seg.exists():
                    raise FileNotFoundError(f"Segment not found: {seg}")
                # ffmpeg concat格式：file 'path'
                f.write(f"file '{seg.absolute()}'\n")
            list_file = Path(f.name)
        
        try:
            # 使用ffmpeg concat
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                "-y",  # 覆盖输出文件
                str(output_path)
            ]
            
            self.logger.debug(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=True
            )
            
            self.logger.info(f"✓ 合并完成: {output_path}")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Merge timeout after {timeout_seconds}s")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"ffmpeg error: {e.stderr}")
            raise RuntimeError(f"Merge failed: {e.stderr}")
        finally:
            # 清理临时文件
            if list_file.exists():
                list_file.unlink()
    
    def get_audio_duration(self, audio_path: Path) -> int:
        """
        获取音频时长（毫秒）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            int: 时长（毫秒）
        """
        if not audio_path.exists():
            return 0
        
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            
            duration_sec = float(result.stdout.strip())
            return int(duration_sec * 1000)
            
        except Exception as e:
            self.logger.warning(f"Failed to get duration for {audio_path}: {e}")
            return 0


def merge_episode_with_bgm(
    segments: List[Path],
    bgm_transitions: Optional[List[Path]],
    bgm_outro: Optional[Path],
    output_path: Path,
    timeout_seconds: int = 300
) -> int:
    """
    合并episode音频，插入BGM（BGM可选）
    
    Args:
        segments: 段落音频列表（S0-S5）
        bgm_transitions: 过渡BGM列表（在S1->S2, S2->S3, S3->S4, S4->S5之间插入）
        bgm_outro: 结尾BGM（在S5之后插入）
        output_path: 输出路径
        timeout_seconds: 超时时间
        
    Returns:
        int: 总时长（毫秒）
    """
    merger = AudioMerger()
    
    # 构建合并序列 - 如果没有BGM就只合并segments
    merge_sequence = []
    
    # 检查是否有任何BGM
    has_bgm = False
    if bgm_transitions:
        for bgm in bgm_transitions:
            if bgm and bgm.exists():
                has_bgm = True
                break
    if bgm_outro and bgm_outro.exists():
        has_bgm = True
    
    if not has_bgm:
        # 没有BGM，直接合并所有segments
        logger.info("未找到BGM文件，仅合并音频段落")
        merge_sequence = segments
    else:
        # 有BGM，按照原逻辑插入
        # S0
        if len(segments) > 0:
            merge_sequence.append(segments[0])
        
        # S1 + transition
        if len(segments) > 1:
            merge_sequence.append(segments[1])
            if bgm_transitions and len(bgm_transitions) > 0 and bgm_transitions[0].exists():
                merge_sequence.append(bgm_transitions[0])
        
        # S2 + transition
        if len(segments) > 2:
            merge_sequence.append(segments[2])
            if bgm_transitions and len(bgm_transitions) > 1 and bgm_transitions[1].exists():
                merge_sequence.append(bgm_transitions[1])
        
        # S3 + transition
        if len(segments) > 3:
            merge_sequence.append(segments[3])
            if bgm_transitions and len(bgm_transitions) > 2 and bgm_transitions[2].exists():
                merge_sequence.append(bgm_transitions[2])
        
        # S4 + transition
        if len(segments) > 4:
            merge_sequence.append(segments[4])
            if bgm_transitions and len(bgm_transitions) > 3 and bgm_transitions[3].exists():
                merge_sequence.append(bgm_transitions[3])
        
        # S5 + outro
        if len(segments) > 5:
            merge_sequence.append(segments[5])
            if bgm_outro and bgm_outro.exists():
                merge_sequence.append(bgm_outro)
    
    # 合并
    merger.merge_segments(merge_sequence, output_path, timeout_seconds)
    
    # 计算总时长
    total_duration = merger.get_audio_duration(output_path)
    
    return total_duration
