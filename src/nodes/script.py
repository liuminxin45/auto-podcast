"""
Script Node

生成播客脚本（对话形式）
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any
from .base import NodeConfig, BaseNode
from ..schemas.state import PodcastState


@dataclass
class ScriptConfig(NodeConfig):
    """Script 节点配置"""
    
    llm_model: str = "gpt-4o"
    target_duration_minutes: int = 15
    dialogue_style: str = "conversational"
    num_hosts: int = 2
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        return {
            "llm_model": "gpt-4o",
            "target_duration_minutes": 15,
            "dialogue_style": "conversational",
            "num_hosts": 2
        }


class ScriptNode(BaseNode):
    """脚本生成节点"""
    
    def __init__(self, config: ScriptConfig):
        super().__init__(config)
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
    
    def __call__(self, state: PodcastState) -> PodcastState:
        """生成脚本"""
        self.log(state, "开始生成脚本")
        
        try:
            topic = state.selected_topic
            materials = state.selected_materials
            
            if not topic or not materials:
                self.error(state, "缺少选题或素材")
                return state
            
            script = self._generate_script(topic, materials)
            
            state.script = script
            self.log(state, f"脚本生成完成: {script.get('title', '')}")
            
        except Exception as e:
            self.error(state, f"脚本生成失败: {str(e)}", detail=str(e))
        
        return state
    
    def _generate_script(self, topic: Dict[str, Any], materials: list) -> Dict[str, Any]:
        """生成脚本（使用 LLM）"""
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        
        llm = ChatOpenAI(
            model=self.config.llm_model,
            api_key=self._api_key,
            temperature=0.7
        )
        
        materials_text = "\n\n".join([
            f"- {m.get('title', '')}: {m.get('content', '')[:500]}"
            for m in materials[:5]
        ])
        
        prompt = f"""请基于以下素材生成一个{self.config.target_duration_minutes}分钟的播客对话脚本。

主题: {topic.get('title', '')}
描述: {topic.get('description', '')}

素材:
{materials_text}

要求:
1. {self.config.num_hosts}位主持人对话
2. 风格: {self.config.dialogue_style}
3. 包含开场、正文、结尾
4. 每段标注说话人

请以JSON格式返回:
{{
    "title": "节目标题",
    "description": "节目简介",
    "dialogue": [
        {{"speaker": "主持人A", "text": "对话内容"}},
        {{"speaker": "主持人B", "text": "对话内容"}}
    ]
}}
"""
        
        messages = [
            SystemMessage(content="你是一个专业的播客脚本编剧。"),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        
        import json
        import re
        
        content = response.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        
        if json_match:
            script_data = json.loads(json_match.group())
            return script_data
        
        return {
            "title": topic.get("title", "未命名节目"),
            "description": topic.get("description", ""),
            "dialogue": []
        }
