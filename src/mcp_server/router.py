"""
MCP Server Layer - Router

op 到 service 的路由映射和参数校验。
不包含业务逻辑，只负责分发和校验。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.domain.services.web_service import WebService
from src.domain.models import OperationResult, ValidationError


class Router:
    """操作路由器"""
    
    # 支持的操作列表
    SUPPORTED_OPS = [
        "web.search",
        "web.fetch",
    ]
    
    def __init__(self, web_service: WebService, logger: logging.Logger | None = None):
        """
        Args:
            web_service: Web 服务实例
            logger: 日志记录器
        """
        self.web_service = web_service
        self.logger = logger or logging.getLogger(self.__class__.__name__)
    
    async def route(self, op: str, payload: Dict[str, Any]) -> OperationResult:
        """
        路由操作到对应的处理函数
        
        Args:
            op: 操作类型
            payload: 操作参数
            
        Returns:
            操作结果
        """
        self.logger.info(f"[Router] 接收路由请求: op={op}, payload_keys={list(payload.keys())}")
        self.logger.debug(f"[Router] 请求详情: payload={payload}")
        
        # 校验 op
        if not op:
            self.logger.error(f"[Router] ✗ op 为空")
            return OperationResult.failure(
                "INVALID_OP",
                "op 不能为空"
            )
        
        if op not in self.SUPPORTED_OPS:
            self.logger.error(f"[Router] ✗ 不支持的操作: {op}")
            return OperationResult.failure(
                "UNSUPPORTED_OP",
                f"不支持的操作: {op}",
                detail={"supported_ops": self.SUPPORTED_OPS}
            )
        
        # 路由到对应的处理函数
        try:
            self.logger.debug(f"[Router] 路由到处理函数: {op}")
            
            if op == "web.search":
                result = await self._handle_web_search(payload)
            elif op == "web.fetch":
                result = await self._handle_web_fetch(payload)
            else:
                self.logger.error(f"[Router] ✗ 操作未实现: {op}")
                return OperationResult.failure(
                    "NOT_IMPLEMENTED",
                    f"操作 {op} 尚未实现"
                )
            
            self.logger.info(f"[Router] ✓ 路由完成: op={op}, success={result.success}")
            return result
        
        except ValidationError as e:
            self.logger.warning(f"[Router] ✗ 参数校验失败: {e.message}")
            return OperationResult.failure(e.code, e.message, detail=e.detail)
        
        except Exception as e:
            self.logger.error(f"[Router] ✗ 操作执行失败: {e}", exc_info=True)
            return OperationResult.failure(
                "INTERNAL_ERROR",
                f"内部错误: {str(e)}",
                detail=str(e)
            )
    
    async def _handle_web_search(self, payload: Dict[str, Any]) -> OperationResult:
        """处理 web.search 操作"""
        self.logger.debug(f"[Router] 处理 web.search...")
        
        # 提取参数
        query = payload.get("query")
        max_results = payload.get("max_results", 10)
        
        self.logger.debug(f"[Router] 提取参数: query='{query}', max_results={max_results}")
        
        # 校验必填参数
        if not query:
            self.logger.error(f"[Router] ✗ 缺少 query 参数")
            raise ValidationError("MISSING_QUERY", "缺少必填参数: query")
        
        # 校验参数类型
        if not isinstance(query, str):
            self.logger.error(f"[Router] ✗ query 类型错误: {type(query)}")
            raise ValidationError("INVALID_QUERY_TYPE", "query 必须是字符串")
        
        if not isinstance(max_results, int):
            self.logger.error(f"[Router] ✗ max_results 类型错误: {type(max_results)}")
            raise ValidationError("INVALID_MAX_RESULTS_TYPE", "max_results 必须是整数")
        
        self.logger.info(f"[Router] 参数校验通过")
        
        # 调用服务
        self.logger.debug(f"[Router] 调用 WebService.search...")
        results = await self.web_service.search(
            query=query,
            max_results=max_results,
            **{k: v for k, v in payload.items() if k not in ["query", "max_results"]}
        )
        
        self.logger.info(f"[Router] WebService 返回 {len(results)} 条结果")
        
        # 转换为字典
        self.logger.debug(f"[Router] 转换结果为字典...")
        data = [r.to_dict() for r in results]
        
        self.logger.info(f"[Router] ✓ web.search 完成: {len(data)} 条结果")
        
        return OperationResult.success(
            data=data,
            meta={
                "count": len(results),
                "provider": self.web_service.search_provider.get_provider_name(),
            }
        )
    
    async def _handle_web_fetch(self, payload: Dict[str, Any]) -> OperationResult:
        """处理 web.fetch 操作"""
        self.logger.debug(f"[Router] 处理 web.fetch...")
        
        # 提取参数
        url = payload.get("url")
        extract_content = payload.get("extract_content", True)
        timeout = payload.get("timeout")
        
        self.logger.debug(f"[Router] 提取参数: url={url}, extract={extract_content}, timeout={timeout}")
        
        # 校验必填参数
        if not url:
            self.logger.error(f"[Router] ✗ 缺少 url 参数")
            raise ValidationError("MISSING_URL", "缺少必填参数: url")
        
        # 校验参数类型
        if not isinstance(url, str):
            self.logger.error(f"[Router] ✗ url 类型错误: {type(url)}")
            raise ValidationError("INVALID_URL_TYPE", "url 必须是字符串")
        
        if not isinstance(extract_content, bool):
            self.logger.error(f"[Router] ✗ extract_content 类型错误: {type(extract_content)}")
            raise ValidationError("INVALID_EXTRACT_CONTENT_TYPE", "extract_content 必须是布尔值")
        
        if timeout is not None and not isinstance(timeout, int):
            self.logger.error(f"[Router] ✗ timeout 类型错误: {type(timeout)}")
            raise ValidationError("INVALID_TIMEOUT_TYPE", "timeout 必须是整数")
        
        self.logger.info(f"[Router] 参数校验通过")
        
        # 调用服务
        self.logger.debug(f"[Router] 调用 WebService.fetch...")
        result = await self.web_service.fetch(
            url=url,
            extract_content=extract_content,
            timeout=timeout
        )
        
        self.logger.info(f"[Router] WebService 返回结果: title='{result.title}', length={result.content_length}")
        
        # 转换为字典
        self.logger.debug(f"[Router] 转换结果为字典...")
        data = result.to_dict()
        
        self.logger.info(f"[Router] ✓ web.fetch 完成: url={result.url}")
        
        return OperationResult.success(
            data=data,
            meta={
                "url": result.url,
                "content_length": result.content_length,
                "is_truncated": result.is_truncated,
            }
        )
    
    def get_supported_ops(self) -> list[str]:
        """获取支持的操作列表"""
        return self.SUPPORTED_OPS.copy()
    
    def get_op_schema(self) -> Dict[str, Dict[str, Any]]:
        """获取操作的 schema"""
        return {
            "web.search": {
                "description": "执行网络搜索",
                "parameters": {
                    "query": {
                        "type": "string",
                        "required": True,
                        "description": "搜索查询"
                    },
                    "max_results": {
                        "type": "integer",
                        "required": False,
                        "default": 10,
                        "description": "最大返回结果数（1-50）"
                    }
                },
                "returns": {
                    "type": "array",
                    "items": {
                        "title": "string",
                        "snippet": "string",
                        "url": "string",
                        "source": "string?",
                        "published_date": "string?",
                        "score": "float?"
                    }
                }
            },
            "web.fetch": {
                "description": "抓取网页内容",
                "parameters": {
                    "url": {
                        "type": "string",
                        "required": True,
                        "description": "目标 URL"
                    },
                    "extract_content": {
                        "type": "boolean",
                        "required": False,
                        "default": True,
                        "description": "是否提取正文内容"
                    },
                    "timeout": {
                        "type": "integer",
                        "required": False,
                        "default": 30,
                        "description": "超时时间（秒）"
                    }
                },
                "returns": {
                    "url": "string",
                    "title": "string?",
                    "content": "string",
                    "author": "string?",
                    "publish_date": "string?",
                    "status_code": "integer",
                    "content_length": "integer",
                    "is_truncated": "boolean"
                }
            }
        }
