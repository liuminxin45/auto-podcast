"""
Fetch Step

数据获取步骤：从各个源拉取、标准化、去重、合规验证、日期过滤、汇总拆分
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.app.pipelines.base_step import BaseStep
from src.fetch.operations.normalize import prepare_items
from src.store.operations.dedup import dedup_items
from src.fetch.operations.compliance import filter_compliant_items, assess_compliance
from src.fetch.operations.source_guard import SourceGuard
from src.fetch.processors.digest_detector import detect_digest_items
from src.fetch.processors.digest_splitter import DigestSplitter, split_digest_items
from src.store.core.artifacts import write_jsonl

if TYPE_CHECKING:
    from src.app.core.context import EpisodeContext


class FetchStep(BaseStep):
    """数据获取步骤"""
    
    def execute(self, ctx: EpisodeContext) -> None:
        """执行 Fetch 步骤
        
        流程：
        1. 从各个源拉取数据
        2. Source guard & 标准化
        3. 去重
        4. 合规验证
        5. 日期过滤（只保留目标日期）
        6. 汇总型RSS检测与拆分
        7. 保存到 ctx.items_raw 和 ctx.items_dedup
        """
        from src.utils.logging_config import log_operation
        
        cfg = ctx.config
        
        # 1. 拉取数据（使用Fetcher Registry）
        from src.fetch import FetcherRegistry
        from src.fetch.core.base import FetchStatus
        import traceback
        
        log_operation(
            self.logger,
            step="Fetch",
            operation="start",
            result=f"已注册 {len(FetcherRegistry.list_all())} 个 fetcher"
        )
        fetched = []
        
        rss_sources = cfg.get("sources", {}).get("rss", [])
        timeout_s = cfg.get("fetch", {}).get("timeout_seconds", 30)
        
        if isinstance(rss_sources, list):
            for source_config in rss_sources:
                if not isinstance(source_config, dict) or not source_config.get("enabled", True):
                    continue
                
                # 获取fetcher类型（默认为standard_rss）
                fetcher_type = source_config.get("fetcher", "standard_rss")
                source_name = source_config.get("name", "unknown")
                
                # 创建fetcher实例
                fetcher = FetcherRegistry.create_instance(fetcher_type)
                if not fetcher:
                    self.logger.error(f"Unknown fetcher type: {fetcher_type}")
                    continue
                
                # 验证配置
                if not fetcher.validate_config(source_config):
                    self.logger.error(f"Invalid config for {source_name}")
                    continue
                
                # 拉取数据
                try:
                    self.logger.info(f"Fetching from {source_name} using {fetcher_type}")
                    # 转换episode_date为date对象
                    import datetime as dt
                    if isinstance(ctx.episode_date, str):
                        episode_date_obj = dt.datetime.strptime(ctx.episode_date, "%Y-%m-%d").date()
                    else:
                        episode_date_obj = ctx.episode_date
                    
                    result = fetcher.fetch_items(
                        config=source_config,
                        episode_date=episode_date_obj,
                        timeout_seconds=timeout_s
                    )
                    
                    if result.status == FetchStatus.SUCCESS:
                        fetched.extend(result.items)
                        self.logger.info(f"✓ {source_name}: {len(result.items)} items")
                    elif result.status == FetchStatus.PARTIAL:
                        fetched.extend(result.items)
                        self.logger.warning(f"⚠ {source_name}: {len(result.items)} items (partial)")
                    else:
                        self.logger.error(f"✗ {source_name}: {result.error_message}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to fetch {source_name}: {e}")
                    self.logger.error(traceback.format_exc())
        
        ctx.items_raw = list(fetched)
        self.logger.info(f"拉取完成: {len(ctx.items_raw)} items")
        
        # 保存 raw items
        artifacts_dir = ctx.run_dir / "1_fetch"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        if ctx.items_raw:
            write_jsonl(artifacts_dir / "01_raw_items.jsonl", ctx.items_raw)
        
        # 2. Source guard & 标准化
        source_guard_cfg = cfg.get("source_guard", {})
        source_guard_dir = source_guard_cfg.get("config_dir", "./config/sources")
        min_content_length = int(source_guard_cfg.get("min_content_length", 0))
        
        source_guard = SourceGuard(config_dir=source_guard_dir)
        self.logger.info(f"source guard loaded {len(source_guard._policies)} policies")
        
        normalized, blocked = prepare_items(
            ctx.items_raw,
            source_guard=source_guard,
            min_content_length=min_content_length,
        )
        self.logger.info(f"normalization: {len(normalized)} items, {len(blocked)} blocked")
        
        # 写入 artifacts
        artifacts_dir = ctx.run_dir / "1_fetch"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        filtered_dir = artifacts_dir / "filtered"
        filtered_dir.mkdir(parents=True, exist_ok=True)
        
        # Write normalized and simplified items (text selection already done in normalize_item)
        if normalized:
            write_jsonl(artifacts_dir / "02_simplified_items.jsonl", normalized)
        
        # Save blocked items to filtered directory
        if blocked:
            write_jsonl(filtered_dir / "02_source_guard_blocked.jsonl", blocked)
        
        # 3. 去重
        max_items = cfg.get("fetch", {}).get("max_items")
        deduped = dedup_items(normalized, max_items=max_items)
        self.logger.info(f"去重完成: {len(deduped)} items")
        
        if deduped:
            write_jsonl(artifacts_dir / "03_deduped_items.jsonl", deduped)
        
        fetched = deduped
        
        # 4. 合规验证
        compliance_cfg = cfg.get("compliance", {})
        self.logger.info("开始合规验证...")
        compliant_items, non_compliant_items = filter_compliant_items(
            fetched,
            rules=compliance_cfg.get("rules"),
            min_score=float(compliance_cfg.get("min_score", 0.6)),
            policy_level=compliance_cfg.get("policy_level", "standard"),
            rule_overrides=compliance_cfg.get("rule_overrides"),
        )
        self.logger.info(f"合规验证完成：合规{len(compliant_items)}条，不合规{len(non_compliant_items)}条")
        
        # Always write compliant items for consistency
        if compliant_items:
            write_jsonl(artifacts_dir / "04_compliant_items.jsonl", compliant_items)
        
        # Save non-compliant items to filtered directory
        if non_compliant_items:
            write_jsonl(filtered_dir / "04_non_compliant_items.jsonl", non_compliant_items)
        
        fetched = compliant_items
        
        # 5. 日期过滤（在拆分之前，避免浪费LLM调用）
        # 特殊处理：60s源始终只保留最新条目，免去日期过滤
        import datetime as dt
        date_str = ctx.episode_id.split(":")[-1] if ":" in ctx.episode_id else ctx.episode_id
        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as e:
            self.logger.error(f"日期解析失败: {date_str} - {e}")
            target_date = dt.date.today()
        
        # 分离60s源和其他源
        sixties_items = [item for item in fetched if "60s" in item.get("source_name", "").lower()]
        other_items = [item for item in fetched if "60s" not in item.get("source_name", "").lower()]
        
        self.logger.info(f"60s源: {len(sixties_items)} items, 其他源: {len(other_items)} items")
        
        # 60s源只保留最新的一条
        if sixties_items:
            # 按published_at排序，取最新的
            sixties_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
            sixties_latest = [sixties_items[0]]
            self.logger.info(f"60s源保留最新条目: {sixties_latest[0].get('title', '')[:50]}")
        else:
            sixties_latest = []
        
        date_filter_cfg = cfg.get("fetch", {}).get("date_filter", {})
        filter_enabled = date_filter_cfg.get("enabled", True)
        filter_mode = date_filter_cfg.get("mode", "exact")  # 默认精确模式，只保留当日
        days_before = int(date_filter_cfg.get("days_before", 0))  # 默认0天
        days_after = int(date_filter_cfg.get("days_after", 0))
        
        if not filter_enabled or filter_mode == "disabled":
            self.logger.info("日期过滤已禁用，保留所有items")
            date_filtered_items = other_items
            old_items = []
        else:
            if filter_mode == "exact":
                self.logger.info(f"开始日期过滤（精确模式）：只保留 {target_date} 的数据...")
                date_range_start = target_date
                date_range_end = target_date
            else:  # range mode
                date_range_start = target_date - dt.timedelta(days=days_before)
                date_range_end = target_date + dt.timedelta(days=days_after)
                self.logger.info(f"开始日期过滤（范围模式）：保留 {date_range_start} 至 {date_range_end} 的数据...")
            
            date_filtered_items = []
            old_items = []
            
            # 只对非60s源进行日期过滤
            for item in other_items:
                published_at = item.get("published_at")
                item_title = item.get('title', 'unknown')[:50]
                
                if not published_at:
                    self.logger.info(f"❌ 过滤无日期: {item_title}")
                    old_items.append(item)
                    continue
                
                try:
                    if isinstance(published_at, str):
                        item_date = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00")).date()
                    elif isinstance(published_at, dt.datetime):
                        item_date = published_at.date()
                    else:
                        item_date = None
                    
                    if item_date and date_range_start <= item_date <= date_range_end:
                        self.logger.info(f"✓ 保留: {item_title} (date={item_date})")
                        date_filtered_items.append(item)
                    else:
                        self.logger.info(f"❌ 过滤旧数据: {item_title} (date={item_date}, target={target_date})")
                        old_items.append(item)
                except Exception as e:
                    self.logger.warning(f"日期解析失败: {item_title} - {e}")
                    old_items.append(item)
            
            self.logger.info(f"日期过滤完成: 保留 {len(date_filtered_items)} 条, 过滤 {len(old_items)} 条")
            
            # 保存通过日期过滤的items（不包括60s）
            if date_filtered_items:
                write_jsonl(artifacts_dir / "05_date_filtered_kept_items.jsonl", date_filtered_items)
            
            # 保存被过滤掉的旧items到filtered目录
            if old_items:
                write_jsonl(filtered_dir / "05_date_filtered_old_items.jsonl", old_items)
        
        # 合并60s最新条目和其他源的日期过滤结果
        fetched = sixties_latest + date_filtered_items
        self.logger.info(f"日期过滤后总计: {len(fetched)} items (60s最新: {len(sixties_latest)}, 其他源: {len(date_filtered_items)})")
        
        # 记录进入digest检测阶段的items
        self.logger.info(f"进入汇总检测阶段: {len(fetched)} items")
        for idx, item in enumerate(fetched[:10], 1):  # 记录前10个
            text_src = item.get('text_source', 'unknown')
            self.logger.info(f"  {idx}. {item.get('source_name', 'unknown')} | text_source={text_src} | {item.get('title', '')[:50]}")
        
        # 6. 汇总型RSS拆分（在日期过滤之后，只对目标日期范围内的数据拆分）
        digest_split_cfg = cfg.get("digest_split", {})
        if digest_split_cfg.get("enabled", False):
            self.logger.info("开始汇总型RSS检测与拆分...")
            
            normal_items, digest_items = detect_digest_items(fetched)
            self.logger.info(f"检测完成: {len(normal_items)} 普通items, {len(digest_items)} 汇总items")
            
            # 保存普通items（未被识别为汇总的）
            if normal_items:
                write_jsonl(artifacts_dir / "06_normal_items.jsonl", normal_items)
            
            split_items = []
            if digest_items:
                splitter = DigestSplitter(
                    cache_ttl_seconds=int(digest_split_cfg.get("cache_ttl_seconds", 86400)),
                    enable_cache=digest_split_cfg.get("enable_cache", True)
                )
                
                split_items, split_stats = split_digest_items(digest_items, splitter)
                
                self.logger.info(f"拆分完成: 生成 {split_stats['total_sub_events']} 个子事件")
                
                # 保存原始汇总items到filtered目录（因为会被拆分替换）
                write_jsonl(filtered_dir / "06_digest_items_original.jsonl", digest_items)
                # 保存拆分结果
                if split_items:
                    write_jsonl(artifacts_dir / "07_split_items.jsonl", split_items)
            
            # 合并：普通items + 拆分后的子事件
            fetched = normal_items + split_items
            self.logger.info(f"合并后总计: {len(fetched)} items (普通{len(normal_items)} + 拆分{len(split_items)})")
        
        # 7. 确保 item_id 并保存到 ctx
        for item in fetched:
            if not item.get("id"):
                item["id"] = item.get("url", "")
        
        ctx.items_dedup = {item["id"]: item for item in fetched if item.get("id")}
        
        # 保存最终处理后的items（按source分组以便查看）
        if ctx.items_dedup:
            final_items = list(ctx.items_dedup.values())
            write_jsonl(artifacts_dir / "08_final_processed_items.jsonl", final_items)
            
            # 按source统计
            source_stats = {}
            for item in final_items:
                source = item.get("source_name") or item.get("source") or "unknown"
                source_stats[source] = source_stats.get(source, 0) + 1
            
            self.logger.info(f"Fetch 步骤完成: {len(ctx.items_dedup)} items from {len(source_stats)} sources")
            for source, count in sorted(source_stats.items(), key=lambda x: -x[1]):
                self.logger.info(f"  - {source}: {count} items")
        else:
            self.logger.info("Fetch 步骤完成: 0 items")
        
        ctx.add_event("fetch_completed", items_count=len(ctx.items_dedup))
