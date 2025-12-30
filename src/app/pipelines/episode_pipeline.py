"""
Episode Pipeline

Episode 主流程编排：Fetch → Cluster → Selection → Research → Script → Audio → Publish
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.app.pipelines.steps import (
    FetchStep,
    ClusterStep,
    SelectionStep,
    ResearchStep,
    PublishStep,
)
from src.app.pipelines.steps.script_step_segmented import ScriptStepSegmented
from src.app.pipelines.steps.audio_step_segmented import AudioStepSegmented

if TYPE_CHECKING:
    from src.app.context import EpisodeContext


class EpisodePipeline:
    """Episode 主流程 Pipeline"""
    
    def __init__(self):
        self.logger = logging.getLogger("app.episode_pipeline")
        
        # 定义步骤顺序
        self.steps = [
            FetchStep(),
            ClusterStep(),
            SelectionStep(),
            ResearchStep(),
            ScriptStepSegmented(),  # 使用分段版本
            AudioStepSegmented(),   # 使用分段版本
            PublishStep(),
        ]
    
    def run(self, ctx: EpisodeContext) -> EpisodeContext:
        """运行完整的 Episode Pipeline
        
        Args:
            ctx: Episode 上下文
            
        Returns:
            更新后的 Episode 上下文
            
        Raises:
            Exception: 任何步骤执行失败
        """
        from src.utils.logging_config import log_operation
        from datetime import datetime
        
        start_time = datetime.now()
        
        log_operation(
            self.logger,
            step="Pipeline",
            operation="start",
            result=f"episode_id={ctx.episode_id}, {len(self.steps)} steps"
        )
        
        try:
            # 按顺序执行所有步骤
            for i, step in enumerate(self.steps, 1):
                step_name = step.__class__.__name__
                log_operation(
                    self.logger,
                    step="Pipeline",
                    operation="execute_step",
                    result=f"[{i}/{len(self.steps)}] {step_name}"
                )
                step.run(ctx)
            
            # 标记完成
            ctx.mark_completed()
            
            duration = (datetime.now() - start_time).total_seconds()
            log_operation(
                self.logger,
                step="Pipeline",
                operation="completed",
                result=f"episode_id={ctx.episode_id}, duration={duration:.1f}s"
            )
            
        except Exception as e:
            # 标记失败
            ctx.mark_failed(str(e))
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(
                f"Episode Pipeline 执行失败: {e}",
                extra={
                    'step': 'Pipeline',
                    'operation': 'failed',
                    'episode_id': ctx.episode_id,
                    'duration': duration,
                    'error': str(e)
                }
            )
            raise
        
        return ctx
