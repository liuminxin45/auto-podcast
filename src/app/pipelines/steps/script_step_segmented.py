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
from src.llm.segment_generator import SegmentScriptGenerator
from src.llm.templates.prompts import NewsItem, ShowConfig

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
        from src.utils.validation import validate_enhanced_item, ValidationError
        
        # ========== 数据验证：检查 items_selected 是否包含 research 数据 ==========
        research_cfg = cfg.get("research", {})
        strict_mode = research_cfg.get("strict_validation", True)
        
        self.logger.info(f"开始验证 {len(ctx.items_selected)} 个 items 的 research 数据")
        
        items_with_research = 0
        items_without_research = []
        
        for item in ctx.items_selected:
            item_id = item.get("id", "unknown")
            has_research = (
                item.get("research_evidence") or 
                item.get("research_claims") or 
                item.get("research_main_evidence")
            )
            
            if has_research:
                items_with_research += 1
                # 记录详细信息
                evidence_count = len(item.get("research_main_evidence", []))
                claims_count = len(item.get("research_claims", []))
                self.logger.debug(
                    f"Item {item_id}: {evidence_count} 条证据, {claims_count} 个论点"
                )
            else:
                items_without_research.append(item_id)
        
        self.logger.info(
            f"Research 数据检查: {items_with_research}/{len(ctx.items_selected)} 个 items 包含 research 数据"
        )
        
        if items_without_research:
            warning_msg = f"警告: {len(items_without_research)} 个 items 缺少 research 数据: {items_without_research}"
            self.logger.warning(warning_msg)
            
            if strict_mode and items_with_research == 0:
                raise ValidationError(
                    f"严格模式: 所有 items 都缺少 research 数据，无法生成高质量脚本"
                )
        
        log_operation(
            self.logger,
            step="Script",
            operation="start",
            result=f"{len(ctx.items_selected)} items, {len(SEGMENT_ORDER)} segments to generate"
        )
        
        # 准备上下文
        render_params = self._prepare_render_params(ctx)
        
        # 获取 LLM 客户端适配器
        llm_adapter = self._get_llm_adapter(cfg)

        # ========== 可选：使用 LangGraph Agent 生成脚本（最小侵入）==========
        agent_cfg = (cfg.get("script", {}) or {}).get("agent", {}) or {}
        use_agent = bool(agent_cfg.get("enabled", False))
        if use_agent:
            from src.llm.podcast_script_agent import generate_segmented_script

            news_bundle = self._build_news_bundle_for_agent(ctx)
            style_profile = self._build_style_profile(cfg)

            temperature = float(agent_cfg.get("temperature", cfg.get("llm", {}).get("temperature", 0.7)))
            threshold = int(agent_cfg.get("threshold", 78))
            max_revisions = int(agent_cfg.get("max_revisions", 2))

            try:
                result = generate_segmented_script(
                    llm=llm_adapter,
                    news=news_bundle,
                    style_profile=style_profile,
                    temperature=temperature,
                    threshold=threshold,
                    max_revisions=max_revisions,
                )

                outputs = dict(result.outputs)
                self._save_agent_debug(ctx, result)

                # 走后续统一流程：outputs -> segments
                segments = self._convert_outputs_to_segments(outputs)

                for segment in segments:
                    self._save_segment(ctx, segment)

                ctx.script_segments = segments
                self._save_summary(ctx, segments)

                self.logger.info(
                    f"脚本生成完成(Agent): {len(segments)} 个段落, score={result.score}, revisions={result.revisions}"
                )
                ctx.add_event(
                    "script_segments_generated",
                    segments_count=len(segments),
                    agent=True,
                    score=result.score,
                    revisions=result.revisions,
                    issues=result.issues,
                )
                return
            except Exception as e:
                self.logger.exception(f"Agent 脚本生成失败，回退到原有生成器: {e}")

        # 创建配置
        show_config = ShowConfig(
            show_name=cfg.get("channel", {}).get("name", "民心A I切片电台"),
            host_name="民心",
            humor_level=1,
            brief_density="short",
        )
        
        # 生成所有段落
        log_operation(
            self.logger,
            step="Script",
            operation="generate_all",
            result="starting"
        )
        
        generator = SegmentScriptGenerator(llm=llm_adapter, config=show_config)
        
        try:
            outputs = generator.render(**render_params)
        except Exception as e:
            self.logger.error(f"脚本生成失败: {e}")
            raise RuntimeError(f"脚本生成失败: {e}") from e
        
        # 将输出转换为 SegmentScript 对象
        segments = self._convert_outputs_to_segments(outputs)
        
        # 保存每个段落
        for segment in segments:
            self._save_segment(ctx, segment)
        
        # 保存到 context
        ctx.script_segments = segments
        
        # 保存汇总
        self._save_summary(ctx, segments)
        
        self.logger.info(f"脚本生成完成: {len(segments)} 个段落")
        ctx.add_event("script_segments_generated", segments_count=len(segments))

    def _build_style_profile(self, cfg: dict) -> str:
        """将现有频道风格配置拼成 agent 的 style_profile 文本"""
        channel = cfg.get("channel", {}) or {}
        style = channel.get("style", {}) or {}
        tone = (style.get("tone") or "").strip()
        audience = (style.get("audience") or "").strip()
        name = (channel.get("name") or "").strip()
        length = style.get("length_minutes")
        length_s = f"{length}分钟" if length is not None else ""

        parts = []
        if name:
            parts.append(f"频道：{name}")
        if tone:
            parts.append(f"语气：{tone}")
        if audience:
            parts.append(f"受众：{audience}")
        if length_s:
            parts.append(f"时长：{length_s}")
        return "；".join(parts) if parts else "口语化、生动、像朋友聊天"

    def _build_news_bundle_for_agent(self, ctx: EpisodeContext) -> str:
        """把 items_selected + research 打包成 agent 输入"""
        lines = []
        lines.append("【今日新闻素材】")
        for idx, item in enumerate(ctx.items_selected or [], 1):
            title = (item.get("title") or "").strip()
            text = (item.get("text") or item.get("content") or "").strip()
            source = (item.get("source_name") or item.get("source") or "").strip()

            lines.append(f"\n========== 新闻 {idx} ==========")
            if title:
                lines.append(f"标题：{title}")
            if source:
                lines.append(f"来源：{source}")
            if text:
                if len(text) > 800:
                    text = text[:800].rstrip() + "…"
                lines.append(f"内容：{text}")

            claims = item.get("research_claims") or []
            if claims:
                lines.append("\n【关键论点】")
                for c in claims[:8]:
                    lines.append(f"- {c}")

            evidences = item.get("research_main_evidence") or []
            if evidences:
                lines.append(f"\n【主要证据】（{len(evidences)}条，节选）")
                for ev in evidences[:3]:
                    st = (ev.get("source_title") or "").strip()
                    ct = (ev.get("content") or "").strip()
                    if ct and len(ct) > 240:
                        ct = ct[:240].rstrip() + "…"
                    if st:
                        lines.append(f"- {st}：{ct}")
                    elif ct:
                        lines.append(f"- {ct}")

        return "\n".join(lines).strip() + "\n"

    def _save_agent_debug(self, ctx: EpisodeContext, result) -> None:
        """保存 agent 产物，便于回归"""
        agent_dir = ctx.run_dir / "3_script" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)

        (agent_dir / "outline.txt").write_text(result.outline or "", encoding="utf-8")
        (agent_dir / "critique.json").write_text(
            json.dumps(result.critique or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (agent_dir / "final_outputs.json").write_text(
            json.dumps(result.outputs or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    
    def _build_deep_facts_bundle(self, items: list) -> str:
        """
        构建深度段落的素材库，包含所有快讯及其 research 数据
        
        让 LLM 自由选择深度话题，可以是：
        - 某一条完整的快讯
        - 某条快讯中的某个角度或细节
        - 多条快讯背后的共同现象或趋势
        - 某个引发思考的点
        
        Returns:
            str: 格式化的素材库文本
        """
        if not items:
            return "今日暂无深度素材"
        
        bundle_parts = []
        bundle_parts.append("【今日快讯素材库】")
        bundle_parts.append("以下是今天的所有快讯及其深度调研数据，供你围绕既定深度主题取用与分析。")
        bundle_parts.append("")
        
        for idx, item in enumerate(items, 1):
            bundle_parts.append(f"\n========== 快讯 {idx} ==========")
            
            # 基本信息
            title = item.get("title", "")
            text = item.get("text", "")
            source = item.get("source_name", "")
            
            bundle_parts.append(f"标题：{title}")
            bundle_parts.append(f"内容：{text}")
            if source:
                bundle_parts.append(f"来源：{source}")
            
            # Research 数据
            research_claims = item.get("research_claims", [])
            if research_claims:
                bundle_parts.append("\n【关键论点】")
                for claim in research_claims:
                    bundle_parts.append(f"  - {claim}")
            
            main_evidence = item.get("research_main_evidence", [])
            if main_evidence:
                bundle_parts.append(f"\n【深度调研证据】（共 {len(main_evidence)} 条）")
                for i, evidence in enumerate(main_evidence[:5], 1):  # 最多5条
                    source_title = evidence.get("source_title", "未知来源")
                    content = evidence.get("content", "")
                    published_at = evidence.get("published_at", "")
                    relevance_score = evidence.get("relevance_score", 0)
                    
                    content_preview = content[:200] if content else ""
                    
                    bundle_parts.append(f"\n  证据 {i}：{source_title}")
                    if published_at:
                        bundle_parts.append(f"  发布时间：{published_at}")
                    bundle_parts.append(f"  相关度：{relevance_score:.2f}")
                    if content_preview:
                        bundle_parts.append(f"  内容摘要：{content_preview}...")
            
            verdict = item.get("research_verdict", "")
            confidence = item.get("research_confidence", 0)
            if verdict:
                verdict_map = {
                    "supported": "已验证支持",
                    "refuted": "已验证反驳",
                    "uncertain": "证据不足"
                }
                verdict_text = verdict_map.get(verdict, verdict)
                bundle_parts.append(f"\n【验证结论】{verdict_text}（置信度：{confidence:.2f}）")
        
        bundle_parts.append("\n\n========== 使用说明 ==========")
        bundle_parts.append("深度主题已在前序确定。请只从上述素材中挑选与该主题最相关的事实、证据与细节来支持你的分析。")
        
        return "\n".join(bundle_parts)
    
    def _prepare_render_params(self, ctx: EpisodeContext) -> dict:
        """准备 render 方法的参数"""
        cfg = ctx.config
        # 获取日期信息
        date_str = str(ctx.episode_date)
        weekday_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
        
        try:
            dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = f"星期{weekday_map.get(dt_obj.weekday(), '')}"
        except:
            weekday = None
        
        # 准备新闻列表，转换为 NewsItem 对象
        news_items = []
        for item in ctx.items_selected:
            title = item.get("title", "")
            text = item.get("text", "")
            
            # 如果是合并新闻，使用叙述提示
            if item.get("is_merged"):
                narrative_hint = item.get("narrative_hint", "")
                facts = narrative_hint if narrative_hint else text
            else:
                facts = text
            
            # 获取research结果
            research_evidence = item.get("research_evidence", None)
            research_claims = item.get("research_claims", None)
            
            news_item = NewsItem(
                title=title,
                facts=facts,
                context=item.get("source_name", ""),
                research_evidence=research_evidence,
                research_claims=research_claims
            )
            news_items.append(news_item)
        
        # ========== 构建深度段落的素材库（所有快讯 + research 数据）==========
        deep_facts_bundle = self._build_deep_facts_bundle(ctx.items_selected)
        
        self.logger.info(
            f"Deep dive 素材库构建完成: {len(deep_facts_bundle)} 字符"
        )
        
        # 历史事件：优先从 today_in_history 数据源拉取；失败则回退占位符
        history_event = "历史上的今天发生了一些重要事件"
        try:
            from src.fetch import FetcherRegistry
            from src.fetch.core.base import FetchStatus

            # 转换episode_date为date对象
            import datetime as dt
            if isinstance(ctx.episode_date, str):
                episode_date_obj = dt.datetime.strptime(ctx.episode_date, "%Y-%m-%d").date()
            else:
                episode_date_obj = ctx.episode_date

            history_source = None
            for source_config in (cfg.get("sources", {}) or {}).get("rss", []) or []:
                if not isinstance(source_config, dict):
                    continue
                if (source_config.get("fetcher") or "").strip() == "today_in_history":
                    history_source = source_config
                    break

            if history_source:
                fetcher = FetcherRegistry.create_instance("today_in_history")
                if fetcher and fetcher.validate_config(history_source):
                    timeout_s = int((cfg.get("fetch", {}) or {}).get("timeout_seconds", 30))
                    result = fetcher.fetch_items(
                        config=history_source,
                        episode_date=episode_date_obj,
                        timeout_seconds=timeout_s,
                    )
                    if result.status in (FetchStatus.SUCCESS, FetchStatus.PARTIAL) and result.items:
                        lines = []
                        for idx, it in enumerate(result.items, 1):
                            title = (it.get("title") or "").strip()
                            content = (it.get("content") or it.get("summary") or "").strip()
                            meta = it.get("_metadata") or {}
                            event_type = (meta.get("event_type") or "").strip()
                            link = (it.get("url") or "").strip()
                            if not title or not content:
                                continue

                            # 控制长度，避免把 history 段 prompt 撑爆
                            content = content.replace("\n", " ").strip()
                            if len(content) > 240:
                                content = content[:240].rstrip() + "…"

                            suffix = []
                            if event_type:
                                suffix.append(f"类型:{event_type}")
                            if link:
                                suffix.append(f"链接:{link}")
                            suffix_text = f"（{'；'.join(suffix)}）" if suffix else ""
                            lines.append(f"{idx}. {title}：{content}{suffix_text}")

                        if lines:
                            history_event = "\n".join(lines)
        except Exception as e:
            self.logger.warning(f"历史事件拉取失败，使用占位符: {e}")
        
        render_params = {
            "date_line": date_str,
            "weekday_line": weekday,
            "lunar_line": None,
            "tease_points": [item.title for item in news_items[:4]],
            "history_event": history_event,
            "news_items": news_items,
            "deep_topic": "今日话题",  # 不再预设话题，让 LLM 自由选择
            "deep_facts": deep_facts_bundle,
            "outro_hint": "明天我们再展开",
            "cta_hint": "喜欢这种A I切片的话，点个关注，就当给我充电。",
        }
        
        # ========== 记录传递给 LLM 的数据摘要 ==========
        self.logger.info("=" * 60)
        self.logger.info("传递给 LLM 的数据摘要:")
        self.logger.info(f"  - 新闻条数: {len(news_items)}")
        self.logger.info(f"  - Deep facts 素材库长度: {len(deep_facts_bundle)} 字符")
        
        # 记录 deep_facts 的前500字符（用于调试）
        deep_facts_preview = deep_facts_bundle[:500] if len(deep_facts_bundle) > 500 else deep_facts_bundle
        self.logger.info(f"  - Deep facts 预览:\n{deep_facts_preview}...")
        
        # 统计 research 数据
        total_evidence = sum(
            len(item.get("research_main_evidence", [])) 
            for item in ctx.items_selected
        )
        total_claims = sum(
            len(item.get("research_claims", [])) 
            for item in ctx.items_selected
        )
        self.logger.info(f"  - 总证据数: {total_evidence}")
        self.logger.info(f"  - 总论点数: {total_claims}")
        self.logger.info("=" * 60)
        
        return render_params
    
    def _get_llm_adapter(self, cfg: dict):
        """获取 LLM 客户端适配器"""
        provider = (
            os.environ.get("LLM_PROVIDER")
            or cfg.get("llm", {}).get("provider")
            or "moonshot"
        ).strip().lower()
        if provider not in {"moonshot", "deepseek"}:
            self.logger.warning(f"未知的 LLM_PROVIDER={provider}，回退到 moonshot")
            provider = "moonshot"
        
        timeout_s = int(cfg.get("llm", {}).get("timeout_seconds", 120))
        
        if provider == "deepseek":
            client = self._create_deepseek_client(timeout_s, cfg)
        else:
            client = self._create_moonshot_client(timeout_s, cfg)
        
        # 包装为适配器
        from src.llm.client.segment_adapter import LLMClientAdapter
        return LLMClientAdapter(client)
    
    def _create_deepseek_client(self, timeout_s: int, cfg: dict):
        """创建 DeepSeek 客户端"""
        from src.llm.client.api_client import DeepSeekClient

        deepseek_cfg = (cfg.get("llm", {}) or {}).get("deepseek", {}) or {}
        base_url = (os.environ.get("DEEPSEEK_BASE_URL") or deepseek_cfg.get("base_url") or "").strip()
        api_key = (os.environ.get("DEEPSEEK_API_KEY") or deepseek_cfg.get("api_key") or "").strip()
        model = (os.environ.get("DEEPSEEK_MODEL") or deepseek_cfg.get("model") or "deepseek-chat").strip()

        if not base_url or not api_key:
            raise RuntimeError("DeepSeek 未配置: 需要在 settings.yaml 的 llm.deepseek 里配置，或设置 DEEPSEEK_BASE_URL / DEEPSEEK_API_KEY")
        
        return DeepSeekClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_s
        )
    
    def _create_moonshot_client(self, timeout_s: int, cfg: dict):
        """创建 Moonshot 客户端"""
        from src.llm.client.api_client import MoonshotClient

        moonshot_cfg = (cfg.get("llm", {}) or {}).get("moonshot", {}) or {}
        base_url = (os.environ.get("MOONSHOT_BASE_URL") or moonshot_cfg.get("base_url") or "https://api.moonshot.cn/v1").strip()
        api_key = (os.environ.get("MOONSHOT_API_KEY") or moonshot_cfg.get("api_key") or "").strip()
        model = (os.environ.get("MOONSHOT_MODEL") or moonshot_cfg.get("model") or "moonshot-v1-8k").strip()

        if not api_key:
            raise RuntimeError("Moonshot 未配置: 需要在 settings.yaml 的 llm.moonshot 里配置，或设置 MOONSHOT_API_KEY")
        
        return MoonshotClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_s
        )
    
    def _convert_outputs_to_segments(self, outputs: dict) -> List[SegmentScript]:
        """将 render() 的输出转换为 SegmentScript 对象列表"""
        # 段落映射：新版本的 segment_id -> 旧版本的 id 和 type
        segment_mapping = {
            "opening": ("S0", "OPENING", "开场", 30),
            "history": ("S1", "HISTORY", "历史上的今天", 20),
            "briefs": ("S2", "DETAIL_NEWS", "快讯", 120),
            "deep_dive": ("S3", "DEEP_DIVE", "深度", 180),
            "outro": ("S4", "CLOSING", "结尾", 20),
        }
        
        segments = []
        for new_id, (old_id, seg_type, title, default_duration) in segment_mapping.items():
            text = outputs.get(new_id, "")
            if not text:
                self.logger.warning(f"段落 {new_id} 没有生成内容")
                continue
            
            # 估算时长（按每秒3个字计算）
            duration_sec = max(default_duration, len(text) // 3)
            
            segment = SegmentScript(
                id=old_id,
                type=seg_type,
                title=title,
                text=text,
                duration_sec=duration_sec,
                facts_used=[],
            )
            segments.append(segment)
        
        return segments
    
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
