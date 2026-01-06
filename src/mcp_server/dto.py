"""
MCP Server Layer - Data Transfer Objects

定义 MCP 工具的输入输出结构。
使用 Pydantic 进行参数校验。
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ExecRequest(BaseModel):
    """exec 工具的请求参数"""
    op: str = Field(..., description="操作类型，如 'web.search' 或 'web.fetch'")
    payload: Dict[str, Any] = Field(default_factory=dict, description="操作参数")


class HealthResponse(BaseModel):
    """health 工具的响应"""
    version: str
    uptime_seconds: float
    available_ops: list[str]
    environment: Dict[str, Any]


class SchemaResponse(BaseModel):
    """schema 工具的响应"""
    ops: Dict[str, Dict[str, Any]]
