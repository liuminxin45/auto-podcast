"""
Adapters Layer - Bocha AI Search Provider

使用博查 AI Search API 作为搜索提供商。
支持网页搜索、图片、模态卡等多种结果类型。
"""

from __future__ import annotations

import json
import os
from typing import List, Dict, Any

import httpx

from src.adapters.search.base import BaseSearchProvider
from src.domain.models import SearchError


class BochaAISearchProvider(BaseSearchProvider):
    """博查 AI Search 搜索提供商"""
    
    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = "https://api.bocha.cn/v1/ai-search",
        timeout: int = 30
    ):
        """
        Args:
            api_key: 博查 API Key（如果为 None，从环境变量 BOCHA_API_KEY 读取）
            api_url: API 端点
            timeout: 请求超时时间（秒）
        """
        super().__init__()
        
        self.api_key = api_key or os.environ.get("BOCHA_API_KEY", "")
        if not self.api_key:
            raise SearchError(
                "MISSING_API_KEY",
                "博查 API Key 未配置，请设置 BOCHA_API_KEY 环境变量或传入 api_key 参数"
            )
        
        self.api_url = api_url
        self.timeout = timeout
        
        self.logger.info(f"初始化博查 AI Search 提供商: api_url={api_url}")
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        freshness: str = "noLimit",
        include_answer: bool = False,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大返回结果数（最多 50）
            freshness: 时间范围（oneDay, oneWeek, oneMonth, oneYear, noLimit）
            include_answer: 是否包含 AI 生成的答案
            **kwargs: 其他参数
            
        Returns:
            搜索结果列表
        """
        self._validate_query(query)
        
        # 限制 max_results 在 1-50 之间
        count = min(max(1, max_results), 50)
        
        self.logger.info(
            f"[BochaAI] 开始搜索: query='{query[:50]}...', count={count}, "
            f"freshness={freshness}, include_answer={include_answer}"
        )
        
        # 构建请求
        payload = {
            "query": query,
            "count": count,
            "freshness": freshness,
            "answer": include_answer,
            "stream": False  # 使用非流式返回
        }
        
        self.logger.debug(f"[BochaAI] 请求参数: {json.dumps(payload, ensure_ascii=False)}")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                self.logger.debug(f"[BochaAI] 发送请求到: {self.api_url}")
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )
                
                self.logger.info(f"[BochaAI] API 响应状态: {response.status_code}")
                
                if response.status_code != 200:
                    self.logger.error(f"[BochaAI] API 错误: status={response.status_code}, body={response.text[:200]}")
                    raise SearchError(
                        "API_ERROR",
                        f"博查 API 返回错误: {response.status_code}",
                        detail=response.text
                    )
                
                data = response.json()
                self.logger.debug(f"[BochaAI] 响应数据: code={data.get('code')}, messages_count={len(data.get('messages', []))}")
                
                # 检查返回状态
                if data.get("code") != 200:
                    error_msg = data.get('msg', 'Unknown error')
                    self.logger.error(f"[BochaAI] API 业务错误: {error_msg}")
                    raise SearchError(
                        "API_ERROR",
                        f"博查 API 返回错误: {error_msg}",
                        detail=data
                    )
                
                # 解析结果
                self.logger.info(f"[BochaAI] 开始解析响应数据...")
                results = self._parse_response(data, max_results)
                
                self.logger.info(f"[BochaAI] ✓ 搜索完成: 返回 {len(results)} 条结果")
                if results:
                    self.logger.debug(f"[BochaAI] 首条结果: title='{results[0].get('title', '')[:50]}', url={results[0].get('url', '')}")
                return results
        
        except httpx.TimeoutException:
            self.logger.error(f"[BochaAI] ✗ 请求超时: {self.timeout}秒")
            raise SearchError(
                "TIMEOUT",
                f"博查 API 请求超时（{self.timeout}秒）"
            )
        except httpx.RequestError as e:
            self.logger.error(f"[BochaAI] ✗ 网络错误: {str(e)}")
            raise SearchError(
                "NETWORK_ERROR",
                f"网络请求失败: {str(e)}",
                detail=str(e)
            )
        except SearchError:
            raise
        except Exception as e:
            self.logger.error(f"[BochaAI] ✗ 未知异常: {e}", exc_info=True)
            raise SearchError(
                "SEARCH_ERROR",
                f"搜索过程中发生错误: {str(e)}",
                detail=str(e)
            )
    
    def _parse_response(
        self,
        data: Dict[str, Any],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        解析博查 AI Search 响应
        
        Args:
            data: API 响应数据
            max_results: 最大结果数
            
        Returns:
            标准化的搜索结果列表
        """
        results = []
        messages = data.get("messages", [])
        
        self.logger.debug(f"[BochaAI] 解析响应: 共 {len(messages)} 条消息")
        
        for idx, message in enumerate(messages):
            role = message.get("role")
            msg_type = message.get("type")
            content_type = message.get("content_type")
            content = message.get("content", "")
            
            self.logger.debug(f"[BochaAI] 消息[{idx}]: role={role}, type={msg_type}, content_type={content_type}")
            
            # 只处理 assistant 返回的 source 类型消息
            if role != "assistant" or msg_type != "source":
                self.logger.debug(f"[BochaAI] 跳过消息[{idx}]: 非 assistant/source 类型")
                continue
            
            # 处理网页结果
            if content_type == "webpage":
                self.logger.debug(f"[BochaAI] 解析网页结果...")
                webpage_results = self._parse_webpage(content, max_results - len(results))
                self.logger.info(f"[BochaAI] 解析到 {len(webpage_results)} 条网页结果")
                results.extend(webpage_results)
            
            # 处理模态卡（百科、医疗等）
            elif content_type in [
                "baike_pro", "medical_common", "medical_pro",
                "weather_china", "weather_international",
                "calendar", "train_line", "train_station_common", "train_station_pro",
                "star_chinese_zodiac_animal", "star_chinese_zodiac",
                "star_western_zodiac_sign", "star_western_zodiac",
                "gold_price", "gold_price_trend", "gold_price_futures_trend",
                "exchangerate", "oil_price", "phone", "stock",
                "car_common", "car_pro"
            ]:
                self.logger.debug(f"[BochaAI] 解析模态卡: {content_type}")
                modal_result = self._parse_modal_card(content, content_type)
                if modal_result:
                    self.logger.info(f"[BochaAI] 解析到模态卡: {content_type}")
                    results.append(modal_result)
                else:
                    self.logger.warning(f"[BochaAI] 模态卡解析失败: {content_type}")
            
            # 如果已经达到最大结果数，停止处理
            if len(results) >= max_results:
                self.logger.debug(f"[BochaAI] 已达到最大结果数 {max_results}，停止解析")
                break
        
        self.logger.info(f"[BochaAI] 解析完成: 总共 {len(results)} 条结果")
        return results[:max_results]
    
    def _parse_webpage(
        self,
        content: str,
        max_count: int
    ) -> List[Dict[str, Any]]:
        """解析网页搜索结果"""
        results = []
        
        try:
            # content 是 JSON 字符串
            webpage_data = json.loads(content)
            value_list = webpage_data.get("value", [])
            
            self.logger.debug(f"[BochaAI] 网页数据: 共 {len(value_list)} 条")
            
            for item in value_list[:max_count]:
                result = self._normalize_result({
                    "title": item.get("name", ""),
                    "snippet": item.get("snippet") or item.get("summary", ""),
                    "url": item.get("url", ""),
                    "source": item.get("siteName"),
                    "published_date": item.get("dateLastCrawled"),
                    "score": None,  # 博查不提供评分
                    "metadata": {
                        "display_url": item.get("displayUrl"),
                        "site_icon": item.get("siteIcon"),
                        "language": item.get("language"),
                    }
                })
                results.append(result)
            
            self.logger.debug(f"[BochaAI] 网页解析: 成功解析 {len(results)}/{len(value_list)} 条")
        
        except json.JSONDecodeError as e:
            self.logger.warning(f"[BochaAI] ✗ 解析网页结果失败: {e}")
        except Exception as e:
            self.logger.warning(f"[BochaAI] ✗ 处理网页结果异常: {e}")
        
        return results
    
    def _parse_modal_card(
        self,
        content: str,
        content_type: str
    ) -> Dict[str, Any] | None:
        """
        解析模态卡结果（百科、医疗、天气等）
        
        将模态卡转换为一条特殊的搜索结果
        """
        try:
            # content 是 JSON 字符串（数组格式）
            modal_data = json.loads(content)
            
            if not modal_data or not isinstance(modal_data, list):
                return None
            
            # 取第一个模态卡
            card = modal_data[0]
            
            # 提取基本信息
            title = card.get("name", f"{content_type} 结果")
            url = card.get("url", "")
            snippet = card.get("snippet", "")
            
            # 尝试从 modelCard 中提取更多信息
            model_card = card.get("modelCard", {})
            
            # 构建摘要
            if not snippet and model_card:
                # 尝试从模态卡中提取摘要
                snippet = self._extract_modal_summary(model_card, content_type)
            
            result = self._normalize_result({
                "title": title,
                "snippet": snippet[:500] if snippet else f"[{content_type}] 结构化信息",
                "url": url or f"https://modal-card/{content_type}",
                "source": "博查模态卡",
                "published_date": card.get("datePublished"),
                "score": 0.95,  # 模态卡通常是高质量结果
                "metadata": {
                    "modal_type": content_type,
                    "modal_card": model_card,
                }
            })
            
            return result
        
        except json.JSONDecodeError as e:
            self.logger.warning(f"[BochaAI] ✗ 解析模态卡失败: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"[BochaAI] ✗ 处理模态卡异常: {e}")
            return None
    
    def _extract_modal_summary(
        self,
        model_card: Dict[str, Any],
        content_type: str
    ) -> str:
        """从模态卡中提取摘要信息"""
        # 不同类型的模态卡结构不同，尝试提取关键信息
        
        # 百科卡
        if content_type == "baike_pro":
            card_data = model_card.get("module_list", [{}])[0].get("item_list", [{}])[0].get("data", {}).get("card", {})
            return card_data.get("dynAbstract") or card_data.get("abstract_info", "")[:300]
        
        # 医疗卡
        elif content_type in ["medical_common", "medical_pro"]:
            subitem = model_card.get("subitem", [])
            if subitem:
                return subitem[0].get("content", "")[:300]
        
        # 天气卡
        elif content_type in ["weather_china", "weather_international"]:
            return "天气信息"
        
        # 其他类型，返回 JSON 字符串的前 200 字符
        return json.dumps(model_card, ensure_ascii=False)[:200]
    
    def get_provider_name(self) -> str:
        """返回提供商名称"""
        return "bocha-ai-search"
