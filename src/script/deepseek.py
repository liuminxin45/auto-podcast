from __future__ import annotations

import json
import logging
from typing import Any

import requests
from pydantic import BaseModel, Field


class ScriptInputItem(BaseModel):
    id: str
    title: str
    summary: str = ""
    content: str = ""
    url: str
    published_at: str | None = None


class ScriptOutput(BaseModel):
    title: str
    ssml: str
    shownotes: str
    tags: list[str] = Field(default_factory=list)


class DeepSeekClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.log = logging.getLogger("script.deepseek")

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def generate(self, channel: dict, items: list[ScriptInputItem], temperature: float) -> ScriptOutput:
        style = (channel.get("style") or {}) if isinstance(channel, dict) else {}
        tone = style.get("tone") or "口语化、生动、像朋友聊天"
        audience = style.get("audience") or "普通听众"

        item_lines = []
        for i, it in enumerate(items, start=1):
            item_lines.append(
                f"{i}. 标题: {it.title}\n摘要: {it.summary}\n链接: {it.url}\n发布时间: {it.published_at or ''}"  # noqa: E501
            )

        system = (
            "你是一名中文播客脚本作者。"
            "你要把新闻内容改写成口语化、节奏明快、像真人聊天的播客。"
            "不要写成新闻稿，不要像公文。"
            "输出必须是严格 JSON，不能输出多余文字。"
        )

        user = f"""
栏目: {channel.get('name') if isinstance(channel, dict) else ''}
受众: {audience}
风格: {tone}

请根据以下新闻素材，生成一期播客脚本。结构固定：
- 10 秒开场（欢迎 + 今日主题）
- 3~5 条内容（每条都要包含：发生了什么 / 对普通人影响 / 建议）
- 结尾总结（复盘 + 行动建议 + 下期预告一句）

强约束：
- 输出 JSON，字段为：title, ssml, shownotes, tags
- ssml 必须是可用于 TTS 的 SSML，包含 <break time=\"500ms\"/> 等停顿
- shownotes 用 Markdown，列出每条新闻的要点与链接
- tags 3~8 个中文标签

新闻素材：
{chr(10).join(item_lines)}

现在输出 JSON：
""".strip()

        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }

        resp = requests.post(
            self._endpoint(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        content = (
            (((data.get("choices") or [])[0] or {}).get("message") or {}).get("content")
            or ""
        )

        try:
            obj = json.loads(content)
        except json.JSONDecodeError as e:
            self.log.error("LLM returned non-JSON: %s", content)
            raise RuntimeError("DeepSeek output is not valid JSON") from e

        try:
            return ScriptOutput.model_validate(obj)
        except Exception as e:  # noqa: BLE001
            self.log.error("LLM JSON schema invalid: %s", content)
            raise RuntimeError("DeepSeek output JSON schema invalid") from e
