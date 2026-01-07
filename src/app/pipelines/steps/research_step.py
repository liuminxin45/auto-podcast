"""
Research Step

研究步骤：对选中的内容进行深度研究
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.app.pipelines.base_step import BaseStep
from src.research.core.pipeline import ResearchPipeline
from src.research.sources.research_client import create_client_from_env
from src.research.utils.budget import BudgetConfig
from src.utils.validation import (
    validate_evidence_pack,
    validate_enhanced_item,
    validate_batch,
    ValidationError,
    StrictModeError
)

if TYPE_CHECKING:
    from src.app.core.context import EpisodeContext


class ResearchStep(BaseStep):
    """研究步骤"""
    
    def execute(self, ctx: EpisodeContext) -> None:
        """执行 Research 步骤"""
        cfg = ctx.config
        research_cfg = cfg.get("research", {})
        
        # 检查是否启用
        if not research_cfg.get("enabled", False):
            self.logger.info("Research 功能未启用，跳过")
            ctx.research_results = []
            ctx.add_event("research_disabled")
            return
        
        # 检查是否有选中的 items
        if not ctx.items_selected:
            self.logger.warning("没有选中的 items，跳过 research")
            ctx.research_results = []
            ctx.add_event("research_skipped_no_items")
            return
        
        from src.utils.logging_config import log_operation, log_api_call
        
        self.logger.info(f"开始 Research：{len(ctx.items_selected)} items")
        
        try:
            # 1. 提取 title 和 summary 字段用于 research
            research_items = []
            total_chars = 0
            for item in ctx.items_selected:
                title = item.get("title", "")
                summary = item.get("summary", "") or item.get("content", "")
                # 限制 summary 长度（前 500 字符）
                if summary and len(summary) > 500:
                    summary = summary[:500]
                
                research_items.append({
                    "id": item.get("id"),
                    "title": title,
                    "summary": summary,
                    "source_name": item.get("source_name", ""),
                })
                total_chars += len(title) + len(summary)
            
            log_operation(
                self.logger,
                step="Research",
                operation="prepare_items",
                result=f"{len(research_items)} items, {total_chars} chars total"
            )
            
            # 2. 创建 research 客户端
            provider = research_cfg.get("provider", "anspire")
            research_client = create_client_from_env(provider=provider)
            
            # 设置保存目录（用于保存博查 API 请求/响应）
            research_dir = ctx.run_dir / "2_research"
            research_client.config.save_dir = str(research_dir)
            
            # 配置预算
            budget_cfg = BudgetConfig(
                max_total_claims=research_cfg.get("max_total_claims", 20),
                max_claims_per_item=research_cfg.get("max_claims_per_item", 5),
            )
            
            # 创建 pipeline
            pipeline = ResearchPipeline(
                research_client=research_client,
                budget_config=budget_cfg,
                scenario="realtime",
            )
            
            # 3. 运行 research（只用 title）
            result = pipeline.run(
                research_items,
                max_claims_per_item=research_cfg.get("max_claims_per_item", 10),
                min_claim_confidence=research_cfg.get("min_claim_confidence", 0.6),
                include_opinions=research_cfg.get("include_opinions", False),
                include_contrast_queries=research_cfg.get("include_contrast_queries", True),
            )
            
            # 检查 research 结果是否为空
            stats = result.get("stats", {})
            total_claims = stats.get("total_claims", 0)
            total_evidence_packs = stats.get("total_evidence_packs", 0)
            
            if total_claims == 0 and total_evidence_packs == 0:
                error_msg = (
                    "Research 失败: 没有生成任何 claims 或 evidence packs。"
                    "可能原因：API 调用失败、解析错误或配置问题。"
                    f"\n结果详情: {result}"
                )
                self.logger.error(error_msg)
                ctx.add_event("research_empty_result", error=error_msg)
                raise RuntimeError(error_msg)
            
            # 4. 将 research 结果组装回原始 items
            evidence_packs = result.get("evidence_packs", [])
            self._merge_research_results(ctx, evidence_packs)
            
            # 保存原始结果
            ctx.research_results = evidence_packs
            
            # 保存到文件
            self._save_research_results(ctx, result)
            
            # 统计
            stats = result.get("stats", {})
            self.logger.info(
                f"Research 完成: {stats.get('total_claims', 0)} claims, "
                f"{stats.get('total_queries', 0)} queries, "
                f"{stats.get('total_evidence_packs', 0)} evidence packs"
            )
            
            ctx.add_event(
                "research_completed",
                claims_count=stats.get("total_claims", 0),
                evidence_packs_count=stats.get("total_evidence_packs", 0),
            )
            
        except Exception as e:
            self.logger.error(f"Research 失败: {e}", exc_info=True)
            ctx.research_results = []
            ctx.add_event("research_failed", error=str(e))
    
    def _merge_research_results(self, ctx: "EpisodeContext", evidence_packs: list) -> None:
        """将 research 结果合并回原始 items"""
        if not evidence_packs:
            self.logger.info("没有 evidence packs，跳过合并")
            return
        
        # ========== 数据验证：验证 evidence_packs 结构 ==========
        research_cfg = ctx.config.get("research", {})
        strict_mode = research_cfg.get("strict_validation", True)  # 默认启用严格模式
        
        self.logger.info(f"开始验证 {len(evidence_packs)} 个 evidence packs (strict={strict_mode})")
        
        validation_result = validate_batch(
            evidence_packs,
            validate_evidence_pack,
            context="Evidence Packs",
            fail_fast=False,
            strict=strict_mode
        )
        
        # 如果验证失败，根据严格模式决定是否抛异常
        if not validation_result.passed:
            if strict_mode:
                validation_result.raise_if_failed(strict=True)
            else:
                self.logger.warning(f"Evidence packs 验证失败，但非严格模式，继续执行")
        
        # 构建 item_id -> evidence_pack 的映射
        evidence_by_item = {}
        for pack in evidence_packs:
            # evidence_pack 可能是 EvidencePack 对象或字典
            if hasattr(pack, "item_id"):
                item_id = pack.item_id
                evidence_by_item[item_id] = pack
            elif isinstance(pack, dict):
                item_id = pack.get("item_id")
                if item_id:
                    evidence_by_item[item_id] = pack
        
        # 调试日志：显示 evidence_by_item 的键
        self.logger.info(f"Evidence packs 的 item_id: {list(evidence_by_item.keys())}")
        
        # 调试日志：显示 items_selected 的 ID
        item_ids = [item.get("id") for item in ctx.items_selected]
        self.logger.info(f"Items selected 的 ID: {item_ids}")
        
        # 将 evidence 合并到 items_selected
        merged_count = 0
        for item in ctx.items_selected:
            item_id = item.get("id")
            if item_id in evidence_by_item:
                evidence = evidence_by_item[item_id]
                
                # 提取 evidence 内容
                if hasattr(evidence, "summary"):
                    item["research_evidence"] = evidence.summary
                elif isinstance(evidence, dict):
                    item["research_evidence"] = evidence.get("summary", "")
                
                # 提取 claim 信息
                if hasattr(evidence, "claim"):
                    # EvidencePack 对象，claim 是一个 Claim 对象
                    item["research_claims"] = [evidence.claim.text]
                elif isinstance(evidence, dict) and "claim" in evidence:
                    # 字典格式，claim 是一个字典
                    claim_dict = evidence.get("claim", {})
                    if isinstance(claim_dict, dict):
                        item["research_claims"] = [claim_dict.get("text", "")]
                    else:
                        item["research_claims"] = [str(claim_dict)]
                
                # 提取主要证据和对照证据
                if isinstance(evidence, dict):
                    item["research_main_evidence"] = evidence.get("main_evidence", [])
                    item["research_contrast_evidence"] = evidence.get("contrast_evidence", [])
                    item["research_verdict"] = evidence.get("verdict", "uncertain")
                    item["research_confidence"] = evidence.get("confidence", 0.0)
                
                merged_count += 1
        
        self.logger.info(f"已将 {merged_count}/{len(ctx.items_selected)} 个 items 的 research 结果合并")
        
        # ========== 数据验证：验证合并后的 items ==========
        if merged_count < len(ctx.items_selected):
            missing_count = len(ctx.items_selected) - merged_count
            self.logger.warning(
                f"警告: {missing_count} 个 items 没有匹配到 research 结果。"
                f"这可能导致部分 items 缺少 research 数据。"
            )
            
            if strict_mode:
                raise ValidationError(
                    f"严格模式: {missing_count} 个 items 缺少 research 结果，中止流程"
                )
        
        # 保存增强后的 items
        self._save_enhanced_items(ctx, strict_mode=strict_mode)
    
    def _save_enhanced_items(self, ctx: "EpisodeContext", strict_mode: bool = True) -> None:
        """保存增强后的 items（包含 research 结果）"""
        import json
        
        # ========== 数据验证：验证 enhanced_items 结构 ==========
        self.logger.info(f"开始验证 {len(ctx.items_selected)} 个 enhanced items (strict={strict_mode})")
        
        validation_result = validate_batch(
            ctx.items_selected,
            lambda item, strict: validate_enhanced_item(item, require_research=True, strict=strict),
            context="Enhanced Items",
            fail_fast=False,
            strict=strict_mode
        )
        
        # 如果验证失败，根据严格模式决定是否抛异常
        if not validation_result.passed:
            if strict_mode:
                validation_result.raise_if_failed(strict=True)
            else:
                self.logger.warning(f"Enhanced items 验证失败，但非严格模式，继续保存")
        
        research_dir = ctx.run_dir / "2_research"
        research_dir.mkdir(parents=True, exist_ok=True)
        
        enhanced_items_path = research_dir / "enhanced_items.json"
        with open(enhanced_items_path, "w", encoding="utf-8") as f:
            json.dump(ctx.items_selected, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"增强后的 items 已保存: {enhanced_items_path}")
    
    def _save_research_results(self, ctx: "EpisodeContext", result: dict) -> None:
        """保存 research 结果到文件"""
        import json
        
        research_dir = ctx.run_dir / "2_research"
        research_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存完整结果
        result_path = research_dir / "research_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "claims": [c.__dict__ if hasattr(c, "__dict__") else c for c in result.get("claims", [])],
                    "clusters": result.get("clusters", []),
                    "queries": [q.__dict__ if hasattr(q, "__dict__") else q for q in result.get("queries", [])],
                    "evidence_packs": [
                        ep.model_dump() if hasattr(ep, "model_dump") else ep
                        for ep in result.get("evidence_packs", [])
                    ],
                    "stats": result.get("stats", {}),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        
        self.logger.info(f"Research 结果已保存: {result_path}")
