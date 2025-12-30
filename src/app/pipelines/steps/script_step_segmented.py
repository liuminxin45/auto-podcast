"""
Script Step (Segmented Version)

脚本生成步骤 - 分段版本
按段落生成脚本：S0-S5
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, List
from datetime import datetime

from src.app.pipelines.base_step import BaseStep
from src.models.segment import SegmentScript, SEGMENT_ORDER
from src.llm.segment_generator import SegmentGenerator

if TYPE_CHECKING:
    from src.app.core.context import EpisodeContext


class ScriptStepSegmented(BaseStep):
    """脚本生成步骤（分段版本）"""
    
    def execute(self, ctx: EpisodeContext) -> None:
        """执行 Script 步骤"""
        cfg = ctx.config
        
        # 检查是否有选中的 items
        if not ctx.items_selected:
            self.logger.warning("没有选中的 items，跳过脚本生成")
            ctx.script_segments = []
            return
        
        from src.utils.logging_config import log_operation
        
        log_operation(
            self.logger,
            step="Script",
            operation="start",
            result=f"{len(ctx.items_selected)} items, {len(SEGMENT_ORDER)} segments to generate"
        )
        
        # 准备上下文
        context = self._prepare_context(ctx)
        
        # 获取 LLM 客户端
        llm_client = self._get_llm_client(cfg)
        
        # 生成所有段落
        timeout_s = int(cfg.get("llm", {}).get("timeout_seconds", 120))
        generator = SegmentGenerator(llm_client, timeout_seconds=timeout_s)
        
        segments = []
        for segment_id in SEGMENT_ORDER:
            try:
                log_operation(
                    self.logger,
                    step="Script",
                    operation=f"generate_{segment_id}",
                    result="starting"
                )
                segment = generator.generate_segment(segment_id, context, retry=True)
                segments.append(segment)
                
                log_operation(
                    self.logger,
                    step="Script",
                    operation=f"generate_{segment_id}",
                    result=f"completed, {segment.duration_sec}s, {len(segment.text)} chars"
                )
                
                # 保存单个段落
                self._save_segment(ctx, segment)
                
            except Exception as e:
                self.logger.error(f"段落 {segment_id} 生成失败: {e}")
                # 关键段落失败则停止
                if segment_id in ["S0", "S1"]:
                    raise RuntimeError(f"关键段落 {segment_id} 生成失败: {e}")
        
        # 保存到 context
        ctx.script_segments = segments
        
        # 保存汇总
        self._save_summary(ctx, segments)
        
        self.logger.info(f"脚本生成完成: {len(segments)} 个段落")
        ctx.add_event("script_segments_generated", segments_count=len(segments))
    
    def _prepare_context(self, ctx: EpisodeContext) -> dict:
        """准备生成上下文"""
        cfg = ctx.config
        
        # 获取日期信息
        date_str = str(ctx.episode_date)
        weekday_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
        
        try:
            from datetime import datetime
            dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = weekday_map.get(dt_obj.weekday(), "")
        except:
            weekday = ""
        
        # 准备新闻列表
        news_items = []
        for item in ctx.items_selected:
            news_items.append({
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "source_name": item.get("source_name", ""),
                "text": item.get("text", ""),  # 使用简化后的text字段
            })
        
        # 选择deep dive主题（第一条新闻）
        deep_dive_topic = news_items[0]["title"] if news_items else "今日热点"
        
        return {
            "show_name": cfg.get("channel", {}).get("name", "生活与消费资讯"),
            "date": date_str,
            "weekday": weekday,
            "news_items": news_items,
            "deep_dive_topic": deep_dive_topic,
            "related_news": news_items[:2] if len(news_items) >= 2 else news_items,
        }
    
    def _get_llm_client(self, cfg: dict):
        """获取 LLM 客户端"""
        provider = (os.environ.get("LLM_PROVIDER") or "moonshot").strip().lower()
        if provider not in {"moonshot", "deepseek"}:
            self.logger.warning(f"未知的 LLM_PROVIDER={provider}，回退到 moonshot")
            provider = "moonshot"
        
        timeout_s = int(cfg.get("llm", {}).get("timeout_seconds", 120))
        
        if provider == "deepseek":
            return self._create_deepseek_client(timeout_s)
        else:
            return self._create_moonshot_client(timeout_s)
    
    def _create_deepseek_client(self, timeout_s: int):
        """创建 DeepSeek 客户端"""
        from src.llm.client.api_client import DeepSeekClient
        
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "").strip()
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
        
        if not base_url or not api_key:
            raise RuntimeError("DeepSeek 未配置: 需要设置 DEEPSEEK_BASE_URL 和 DEEPSEEK_API_KEY")
        
        return DeepSeekClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_s
        )
    
    def _create_moonshot_client(self, timeout_s: int):
        """创建 Moonshot 客户端"""
        from src.llm.client.api_client import MoonshotClient
        
        base_url = os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1").strip()
        api_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
        model = os.environ.get("MOONSHOT_MODEL", "moonshot-v1-8k").strip()
        
        if not api_key:
            raise RuntimeError("Moonshot 未配置: 需要设置 MOONSHOT_API_KEY")
        
        return MoonshotClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_s
        )
    
    def _save_segment(self, ctx: EpisodeContext, segment: SegmentScript) -> None:
        """保存单个段落"""
        script_dir = ctx.run_dir / "3_script" / "segments"
        script_dir.mkdir(parents=True, exist_ok=True)
        
        segment_path = script_dir / f"{segment.id}.json"
        segment_path.write_text(
            json.dumps(segment.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def _save_summary(self, ctx: EpisodeContext, segments: List[SegmentScript]) -> None:
        """保存汇总"""
        script_dir = ctx.run_dir / "3_script"
        script_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存所有段落的汇总
        summary = {
            "episode_id": ctx.episode_id,
            "date": str(ctx.episode_date),
            "segments": [s.to_dict() for s in segments],
            "total_duration_sec": sum(s.duration_sec for s in segments),
            "generated_at": datetime.now().isoformat(),
        }
        
        summary_path = script_dir / f"{ctx.episode_date}.segments.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        # 保存合并的文本（用于查看）
        full_text = "\n\n".join([
            f"=== {s.id}: {s.title} ({s.duration_sec}秒) ===\n{s.text}"
            for s in segments
        ])
        
        text_path = script_dir / f"{ctx.episode_date}.full_script.txt"
        text_path.write_text(full_text, encoding="utf-8")
