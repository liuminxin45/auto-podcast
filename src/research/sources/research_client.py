"""
Unified Research Client

这个文件提供了统一的研究客户端接口，支持多种研究服务提供商。

功能概述：
- 统一MetaSo和其他研究API调用接口
- 提供向后兼容的客户端类
- 支持深度研究、背景分析等多种应用场景
- 完整的错误处理和重试机制

主要类：
- UnifiedResearchClient: 统一研究客户端
- MetaSoClient: MetaSo API客户端（向后兼容）
- ResearchConfig: 研究配置模型
- ResearchOutput: 研究输出模型

工厂方法：
- create_client(): 根据配置创建对应客户端
- 支持环境变量和配置文件

使用示例：
    client = create_client("metaso", api_key, base_url, model, timeout)
    result = client.research_items(items, max_items=10)

作者：Auto-Podcast Team
版本：1.0.0
更新：2025-12-25
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import requests
from pydantic import BaseModel, Field

from src.research.sources.anspire import anspire_research_items
from src.research.core.config import ResearchSettings, load_research_config
from src.research.sources.metaso import metaso_research_items


def bocha_web_search_items(
    items: List[Dict[str, Any]],
    api_key: str,
    timeout_seconds: int = 60,
    count: int = 10,
    summary: bool = True,
    freshness: str = "noLimit",
    max_items: Optional[int] = None,
    save_dir: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    使用博查 Web Search API 搜索新闻条目
    
    Args:
        items: 要搜索的新闻条目列表
        api_key: 博查 API Key
        timeout_seconds: 请求超时时间
        count: 返回结果数量 (1-50)
        summary: 是否显示文本摘要
        freshness: 搜索时间范围
        max_items: 最大处理条目数
        
    Returns:
        搜索结果字典，包含 ok, response_json, response_text 等字段
    """
    logger = logging.getLogger("research.sources.bocha")
    
    if not api_key:
        logger.error("博查 API Key 未配置")
        return {"ok": False, "error": "API Key 未配置"}
    
    # 限制处理的条目数
    if max_items and len(items) > max_items:
        items = items[:max_items]
        logger.info(f"限制处理条目数为 {max_items}")
    
    # 构建搜索查询（从新闻标题和文本中提取关键词）
    queries = []
    for item in items:
        title = item.get("title", "")
        text = item.get("text", "")
        # 优先使用标题，如果标题为空则使用文本的前50个字符
        query = title if title else (text[:50] if text else "")
        if query:
            queries.append(query)
    
    if not queries:
        logger.warning("没有有效的搜索查询")
        return {"ok": False, "error": "没有有效的搜索查询"}
    
    # 合并查询（博查支持复杂查询）
    combined_query = " ".join(queries[:3])  # 只取前3个查询避免过长
    
    url = "https://api.bocha.cn/v1/web-search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": combined_query,
        "freshness": freshness,
        "summary": summary,
        "count": min(count, 50)  # 最大50
    }
    
    try:
        logger.info(f"开始博查搜索，查询: {combined_query[:100]}...")
        
        # 准备保存目录
        save_path = None
        if save_dir:
            import os
            from pathlib import Path
            import hashlib
            save_path = Path(save_dir)
            save_path.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名（使用查询的哈希值）
            query_hash = hashlib.md5(combined_query.encode()).hexdigest()[:8]
            
            # 保存请求报文
            request_data = {
                "url": url,
                "headers": {k: v for k, v in headers.items() if k != "Authorization"},  # 不保存API Key
                "payload": payload,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            request_file = save_path / f"bocha_request_{query_hash}.json"
            with open(request_file, "w", encoding="utf-8") as f:
                json.dump(request_data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存请求报文: {request_file}")
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout_seconds
        )
        
        # 保存响应报文
        if save_path and response:
            import hashlib
            query_hash = hashlib.md5(combined_query.encode()).hexdigest()[:8]
            
            response_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.status_code == 200 else response.text,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            response_file = save_path / f"bocha_response_{query_hash}.json"
            with open(response_file, "w", encoding="utf-8") as f:
                json.dump(response_data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存响应报文: {response_file}")
        
        if response.status_code == 200:
            result = response.json()
            
            # 检查响应格式
            if result.get("code") == 200 and result.get("data"):
                data = result["data"]
                web_pages = data.get("webPages", {})
                pages = web_pages.get("value", [])
                
                # 构建返回格式（兼容现有 research 流程）
                content_parts = []
                for i, page in enumerate(pages[:count], 1):
                    name = page.get("name", "")
                    snippet = page.get("snippet", "")
                    summary_text = page.get("summary", "")
                    url_link = page.get("url", "")
                    site_name = page.get("siteName", "")
                    date_published = page.get("datePublished", "")
                    
                    part = f"[{i}] {name}\n"
                    if site_name:
                        part += f"来源: {site_name}\n"
                    if date_published:
                        part += f"发布时间: {date_published}\n"
                    if summary_text:
                        part += f"摘要: {summary_text}\n"
                    elif snippet:
                        part += f"简介: {snippet}\n"
                    if url_link:
                        part += f"链接: {url_link}\n"
                    content_parts.append(part)
                
                content = "\n".join(content_parts)
                
                logger.info(f"博查搜索成功，返回 {len(pages)} 条结果")
                return {
                    "ok": True,
                    "response_json": {
                        "choices": [{
                            "message": {
                                "content": content
                            }
                        }]
                    },
                    "response_text": content,
                    "model": "bocha-web-search",
                    "metadata": {
                        "total_results": web_pages.get("totalEstimatedMatches", 0),
                        "query": combined_query,
                        "pages_count": len(pages)
                    }
                }
            else:
                error_msg = result.get("message", "未知错误")
                logger.error(f"博查 API 返回错误: {error_msg}")
                return {"ok": False, "error": error_msg}
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"博查 API 请求失败: {error_msg}")
            return {"ok": False, "error": error_msg}
            
    except requests.exceptions.Timeout:
        logger.error(f"博查 API 请求超时 ({timeout_seconds}秒)")
        return {"ok": False, "error": "请求超时"}
    except Exception as e:
        logger.error(f"博查搜索异常: {e}")
        return {"ok": False, "error": str(e)}


class ResearchConfig(BaseModel):
    """研究配置模型"""
    provider: str = Field(default="metaso", description="研究服务提供商 (metaso, anspire, bocha)")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    base_url: Optional[str] = Field(default=None, description="API基础URL")
    model: Optional[str] = Field(default=None, description="模型名称")
    timeout_seconds: int = Field(default=60, description="请求超时时间（秒）")
    max_items: Optional[int] = Field(default=None, description="最大研究条目数")
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="重试延迟时间（秒）")
    top_k: Optional[int] = Field(default=None, description="Anspire: 搜索返回的最大结果数")
    is_stream: bool = Field(default=False, description="Anspire: 是否使用流式输出")
    # Bocha Web Search 配置
    bocha_count: int = Field(default=10, description="Bocha: 返回结果数量 (1-50)")
    bocha_summary: bool = Field(default=True, description="Bocha: 是否显示文本摘要")
    bocha_freshness: str = Field(default="noLimit", description="Bocha: 搜索时间范围 (noLimit, oneDay, oneWeek, oneMonth, oneYear)")
    # 保存目录
    save_dir: Optional[str] = Field(default=None, description="保存请求/响应报文的目录")


class ResearchOutput(BaseModel):
    """研究输出模型"""
    success: bool = Field(description="研究是否成功")
    content: Optional[str] = Field(default=None, description="研究内容")
    model: Optional[str] = Field(default=None, description="使用的模型")
    provider: str = Field(description="服务提供商")
    input_items_count: int = Field(description="输入条目数量")
    processing_time_ms: int = Field(description="处理时间（毫秒）")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class UnifiedResearchClient:
    """统一研究客户端"""
    
    def __init__(self, config: ResearchConfig):
        self.config = config
        self.logger = logging.getLogger(f"research.sources.{config.provider}")
        
    def research_items(self, items: List[Dict[str, Any]], **kwargs) -> ResearchOutput:
        """
        研究给定的条目列表
        
        Args:
            items: 要研究的条目列表
            **kwargs: 额外参数（如max_items等）
            
        Returns:
            ResearchOutput: 研究结果
        """
        start_time = time.perf_counter()
        
        try:
            # 合并配置和参数
            max_items = kwargs.get('max_items') or self.config.max_items
            model = kwargs.get('model') or self.config.model
            
            self.logger.info(f"开始研究 {len(items)} 个条目，提供商: {self.config.provider}")
            
            # 根据提供商调用对应的研究方法
            if self.config.provider == "metaso":
                result = self._research_with_metaso(items, max_items, model)
            elif self.config.provider == "anspire":
                result = self._research_with_anspire(items, max_items)
            elif self.config.provider == "bocha":
                result = self._research_with_bocha(items, max_items)
            else:
                raise ValueError(f"不支持的研究提供商: {self.config.provider}")
            
            # 计算处理时间
            processing_time_ms = int((time.perf_counter() - start_time) * 1000)
            
            # 构建输出
            output = ResearchOutput(
                success=result is not None and result.get("ok", False),
                content=result.get("response_json", {}).get("choices", [{}])[0].get("message", {}).get("content") if result and result.get("response_json") else result.get("response_text") if result else None,
                model=result.get("model") if result else model,
                provider=self.config.provider,
                input_items_count=len(items),
                processing_time_ms=processing_time_ms,
                metadata=result or {}
            )
            
            if output.success:
                self.logger.info(f"研究完成，耗时 {processing_time_ms}ms")
            else:
                self.logger.warning("研究失败")
                
            return output
            
        except Exception as e:
            processing_time_ms = int((time.perf_counter() - start_time) * 1000)
            error_msg = str(e)
            self.logger.error(f"研究过程中发生错误: {error_msg}")
            
            return ResearchOutput(
                success=False,
                provider=self.config.provider,
                input_items_count=len(items),
                processing_time_ms=processing_time_ms,
                error=error_msg
            )
    
    def _research_with_metaso(self, items: List[Dict[str, Any]], max_items: Optional[int], model: Optional[str]) -> Optional[Dict[str, Any]]:
        """使用MetaSo进行研究"""
        try:
            result = metaso_research_items(
                items=items,
                timeout_seconds=self.config.timeout_seconds,
                model=model,
                max_items=max_items
            )
            return result
        except Exception as e:
            self.logger.error(f"MetaSo研究失败: {e}")
            raise
    
    def _research_with_anspire(self, items: List[Dict[str, Any]], max_items: Optional[int]) -> Optional[Dict[str, Any]]:
        """使用Anspire进行研究"""
        try:
            result = anspire_research_items(
                items=items,
                timeout_seconds=self.config.timeout_seconds,
                top_k=self.config.top_k,
                is_stream=self.config.is_stream,
                max_items=max_items
            )
            return result
        except Exception as e:
            self.logger.error(f"Anspire研究失败: {e}")
            raise
    
    def _research_with_bocha(self, items: List[Dict[str, Any]], max_items: Optional[int]) -> Optional[Dict[str, Any]]:
        """使用博查 Web Search 进行研究"""
        try:
            result = bocha_web_search_items(
                items=items,
                api_key=self.config.api_key or "",
                timeout_seconds=self.config.timeout_seconds,
                count=self.config.bocha_count,
                summary=self.config.bocha_summary,
                freshness=self.config.bocha_freshness,
                max_items=max_items,
                save_dir=self.config.save_dir
            )
            return result
        except Exception as e:
            self.logger.error(f"博查搜索失败: {e}")
            raise
    
    def research_with_retry(self, items: List[Dict[str, Any]], **kwargs) -> ResearchOutput:
        """
        带重试机制的研究方法
        
        Args:
            items: 要研究的条目列表
            **kwargs: 额外参数
            
        Returns:
            ResearchOutput: 研究结果
        """
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = self.research_items(items, **kwargs)
                if result.success:
                    return result
                    
                # 如果是客户端错误（4xx），不重试
                if hasattr(result, 'error') and result.error and '400' in result.error:
                    self.logger.warning(f"客户端错误，不重试: {result.error}")
                    return result
                    
                last_error = result.error
                
                if attempt < self.config.max_retries:
                    self.logger.warning(f"研究失败，{self.config.retry_delay}秒后重试 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {last_error}")
                    time.sleep(self.config.retry_delay)
                    
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.max_retries:
                    self.logger.warning(f"研究异常，{self.config.retry_delay}秒后重试 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {last_error}")
                    time.sleep(self.config.retry_delay)
        
        # 所有重试都失败了
        self.logger.error(f"研究失败，已达到最大重试次数: {last_error}")
        return ResearchOutput(
            success=False,
            provider=self.config.provider,
            input_items_count=len(items),
            processing_time_ms=0,
            error=last_error or "重试次数已用尽"
        )


class MetaSoClient(UnifiedResearchClient):
    """MetaSo研究客户端（向后兼容）"""
    
    def __init__(self, api_key: str, model: Optional[str] = None, timeout_seconds: int = 60):
        config = ResearchConfig(
            provider="metaso",
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds
        )
        super().__init__(config)


def create_client(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: int = 60,
    max_items: Optional[int] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **kwargs
) -> UnifiedResearchClient:
    """
    创建研究客户端的工厂方法
    
    Args:
        provider: 研究服务提供商 ("metaso", "anspire")
        api_key: API密钥
        base_url: API基础URL
        model: 模型名称 (仅MetaSo)
        timeout_seconds: 超时时间
        max_items: 最大条目数
        max_retries: 最大重试次数
        retry_delay: 重试延迟
        **kwargs: 其他配置参数 (如top_k, is_stream for Anspire)
        
    Returns:
        UnifiedResearchClient: 配置好的研究客户端
    """
    config = ResearchConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        max_items=max_items,
        max_retries=max_retries,
        retry_delay=retry_delay,
        **kwargs
    )
    
    if provider in ["metaso", "anspire", "bocha"]:
        return UnifiedResearchClient(config)
    else:
        raise ValueError(f"不支持的研究提供商: {provider}")


def create_client_from_env(provider: Optional[str] = None) -> UnifiedResearchClient:
    """
    从环境变量和配置文件创建研究客户端
    
    Args:
        provider: 研究服务提供商 ("metaso", "anspire", "bocha")，如果为None则从RESEARCH_PROVIDER读取
        
    Returns:
        UnifiedResearchClient: 配置好的研究客户端
    """
    import os
    
    # 加载配置文件
    try:
        research_config = load_research_config()
    except Exception as e:
        logging.getLogger("research.sources.config").warning(f"加载配置文件失败: {e}，使用默认配置")
        research_config = ResearchSettings()  # 使用默认配置
    
    # 确定提供商
    if provider is None:
        provider = os.environ.get("RESEARCH_PROVIDER")
        if provider is None and research_config:
            provider = research_config.provider
        if provider is None:
            provider = "metaso"  # 默认值
    
    # 从环境变量获取基础配置，优先使用环境变量
    if provider == "metaso":
        api_key = os.environ.get("METASO_API_KEY")
        base_url = os.environ.get("METASO_BASE_URL")
        model = os.environ.get("METASO_MODEL", research_config.metaso.get("model") if research_config else "fast")
        timeout_seconds = int(os.environ.get("METASO_TIMEOUT_SECONDS", str(research_config.timeout_seconds if research_config else 60)))
        max_items = int(os.environ.get("METASO_MAX_ITEMS", "0")) or None
        max_retries = int(os.environ.get("METASO_MAX_RETRIES", str(research_config.max_retries if research_config else 3)))
        retry_delay = float(os.environ.get("METASO_RETRY_DELAY", str(research_config.retry_delay if research_config else 1.0)))
        
        return create_client(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_items=max_items,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
    elif provider == "anspire":
        api_key = os.environ.get("ANSPIRE_API_KEY")
        base_url = os.environ.get("ANSPIRE_BASE_URL")
        timeout_seconds = int(os.environ.get("ANSPIRE_TIMEOUT_SECONDS", str(research_config.timeout_seconds if research_config else 60)))
        max_items = int(os.environ.get("ANSPIRE_MAX_ITEMS", "0")) or None
        max_retries = int(os.environ.get("ANSPIRE_MAX_RETRIES", str(research_config.max_retries if research_config else 3)))
        retry_delay = float(os.environ.get("ANSPIRE_RETRY_DELAY", str(research_config.retry_delay if research_config else 1.0)))
        top_k = int(os.environ.get("ANSPIRE_TOP_K", str(research_config.anspire.get("top_k") if research_config else 5)))
        is_stream = os.environ.get("ANSPIRE_IS_STREAM", str(research_config.anspire.get("is_stream", False) if research_config else "false")).lower() == "true"
        
        return create_client(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_items=max_items,
            max_retries=max_retries,
            retry_delay=retry_delay,
            top_k=top_k,
            is_stream=is_stream
        )
    elif provider == "bocha":
        api_key = os.environ.get("BOCHA_API_KEY") or (research_config.bocha.get("api_key") if research_config and hasattr(research_config, 'bocha') else None)
        timeout_seconds = int(os.environ.get("BOCHA_TIMEOUT_SECONDS", str(research_config.bocha.get("timeout_seconds", research_config.timeout_seconds) if research_config and hasattr(research_config, 'bocha') else 60)))
        max_items = int(os.environ.get("BOCHA_MAX_ITEMS", str(research_config.bocha.get("max_items", 0) if research_config and hasattr(research_config, 'bocha') else 0))) or None
        max_retries = int(os.environ.get("BOCHA_MAX_RETRIES", str(research_config.bocha.get("max_retries", research_config.max_retries) if research_config and hasattr(research_config, 'bocha') else 3)))
        retry_delay = float(os.environ.get("BOCHA_RETRY_DELAY", str(research_config.bocha.get("retry_delay", research_config.retry_delay) if research_config and hasattr(research_config, 'bocha') else 1.0)))
        bocha_count = int(os.environ.get("BOCHA_COUNT", str(research_config.bocha.get("count", 10) if research_config and hasattr(research_config, 'bocha') else 10)))
        bocha_summary = os.environ.get("BOCHA_SUMMARY", str(research_config.bocha.get("summary", True) if research_config and hasattr(research_config, 'bocha') else "true")).lower() == "true"
        bocha_freshness = os.environ.get("BOCHA_FRESHNESS", str(research_config.bocha.get("freshness", "noLimit") if research_config and hasattr(research_config, 'bocha') else "noLimit"))
        
        return create_client(
            provider=provider,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            max_items=max_items,
            max_retries=max_retries,
            retry_delay=retry_delay,
            bocha_count=bocha_count,
            bocha_summary=bocha_summary,
            bocha_freshness=bocha_freshness
        )
    else:
        raise ValueError(f"不支持的研究提供商: {provider}")


# 向后兼容的函数
def research_items_with_client(
    client: UnifiedResearchClient,
    items: List[Dict[str, Any]],
    max_items: Optional[int] = None,
    use_retry: bool = True,
    **kwargs
) -> ResearchOutput:
    """
    使用客户端研究条目
    
    Args:
        client: 研究客户端
        items: 要研究的条目列表
        max_items: 最大条目数
        use_retry: 是否使用重试机制
        **kwargs: 其他参数
        
    Returns:
        ResearchOutput: 研究结果
    """
    if max_items is not None:
        kwargs['max_items'] = max_items
    
    if use_retry:
        return client.research_with_retry(items, **kwargs)
    else:
        return client.research_items(items, **kwargs)
