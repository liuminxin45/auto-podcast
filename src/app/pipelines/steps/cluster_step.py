"""
Cluster Step

聚类步骤：将相似的新闻聚合成 StoryCluster
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.app.pipelines.base_step import BaseStep
from src.store.operations.clusters import cluster_items, ClusterConfig

if TYPE_CHECKING:
    from src.app.core.context import EpisodeContext


class ClusterStep(BaseStep):
    """聚类步骤"""
    
    def execute(self, ctx: EpisodeContext) -> None:
        """执行 Cluster 步骤"""
        from src.utils.logging_config import log_operation
        
        cfg = ctx.config
        
        # 获取聚类配置 - 支持多个可能的配置路径
        cluster_cfg_dict = (
            cfg.get("clustering") or 
            cfg.get("store", {}).get("clustering") or
            cfg.get("selection", {}).get("clustering") or 
            {}
        )
        
        # 创建 ClusterConfig 对象
        cluster_cfg = ClusterConfig(
            simhash_max_distance=int(cluster_cfg_dict.get("simhash_max_distance", 4)),
            title_min_jaccard=float(cluster_cfg_dict.get("title_min_jaccard", 0.4)),
            time_window_days=int(cluster_cfg_dict.get("time_window_days", 3)),
            cooldown_days=int(cluster_cfg_dict.get("cooldown_days", 2)),
        )
        
        log_operation(
            self.logger,
            step="Cluster",
            operation="config",
            result=f"simhash_dist={cluster_cfg.simhash_max_distance}, jaccard={cluster_cfg.title_min_jaccard}"
        )
        
        # 转换为 items 列表
        items_list = list(ctx.items_dedup.values())
        
        if not items_list:
            self.logger.warning("没有 items 可聚类")
            ctx.clusters = []
            return
        
        log_operation(
            self.logger,
            step="Cluster",
            operation="start_clustering",
            result=f"{len(items_list)} items"
        )
        
        # 执行聚类
        ctx.clusters = cluster_items(items_list, config=cluster_cfg)
        
        log_operation(
            self.logger,
            step="Cluster",
            operation="clustering_completed",
            result=f"{len(ctx.clusters)} clusters from {len(items_list)} items"
        )
        
        ctx.add_event("clustering_completed",
                     items_count=len(items_list),
                     clusters_count=len(ctx.clusters))
