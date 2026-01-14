"""
n8n Bridge API - 将 auto-podcast 暴露为 n8n 可调用的 HTTP 接口

运行方式：
    uvicorn n8n_bridge.main:app --reload --port 8000

n8n 中配置 HTTP Request 节点：
    URL: http://localhost:8000/api/{endpoint}
    Method: POST
    Body: JSON
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
import json

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 延迟导入，避免启动时加载失败
def get_episode_context():
    from src.app.core.context import EpisodeContext
    return EpisodeContext

def get_episode_pipeline():
    from src.app.pipelines.episode_pipeline import EpisodePipeline
    return EpisodePipeline

def load_app_config():
    from src.config.loader import load_config
    return load_config()

def setup_app_logging():
    try:
        from src.utils.logging_config import setup_logging
        setup_logging()
    except ImportError:
        logging.basicConfig(level=logging.INFO)

# 初始化
app = FastAPI(
    title="auto-podcast n8n Bridge",
    description="将 auto-podcast 系统暴露为 n8n 可调用的 API",
    version="1.0.0"
)

# CORS 配置（允许 n8n 调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 日志配置
setup_app_logging()
logger = logging.getLogger("n8n_bridge")

# ============================================================
# 数据模型
# ============================================================

class ConfigGetRequest(BaseModel):
    """获取配置请求"""
    config_type: str = Field(..., description="配置类型: env | yaml")
    key: Optional[str] = Field(None, description="配置键（为空则返回全部）")

class ConfigSetRequest(BaseModel):
    """设置配置请求"""
    key: str = Field(..., description="配置键（如 DEEPSEEK_API_KEY）")
    value: str = Field(..., description="配置值")
    persist: bool = Field(True, description="是否持久化到 .env 文件")

class PipelineRunRequest(BaseModel):
    """运行 Pipeline 请求"""
    step: Optional[str] = Field(None, description="指定步骤（为空则运行完整流程）")
    config_override: Optional[Dict[str, Any]] = Field(None, description="配置覆盖")
    episode_id: Optional[str] = Field(None, description="Episode ID（为空则自动生成）")

class LLMCallRequest(BaseModel):
    """LLM 调用请求"""
    provider: str = Field("moonshot", description="LLM 提供商: moonshot | deepseek")
    prompt: str = Field(..., description="提示词")
    model: Optional[str] = Field(None, description="模型名称（为空则使用默认）")
    temperature: float = Field(0.7, description="温度参数")
    max_tokens: Optional[int] = Field(None, description="最大 token 数")

class TTSCallRequest(BaseModel):
    """TTS 调用请求"""
    text: str = Field(..., description="要转换的文本")
    voice: Optional[str] = Field(None, description="语音名称")
    mode: str = Field("tts", description="TTS 模式: tts | podcast | voiceclone_http")
    output_path: Optional[str] = Field(None, description="输出路径（为空则自动生成）")

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索查询")
    provider: str = Field("bocha", description="搜索提供商: bocha | metaso | anspire")
    count: int = Field(10, description="返回结果数量")
    api_type: Optional[str] = Field("ai-search", description="Bocha API 类型: ai-search | web-search")

# ============================================================
# 配置管理 API
# ============================================================

@app.post("/api/config/get")
async def get_config(request: ConfigGetRequest):
    """获取配置项"""
    try:
        if request.config_type == "env":
            # 读取 .env 文件
            env_path = project_root / ".env"
            if not env_path.exists():
                raise HTTPException(404, ".env 文件不存在")
            
            if request.key:
                # 返回单个配置
                value = os.getenv(request.key)
                return {"key": request.key, "value": value}
            else:
                # 返回所有配置
                env_vars = {}
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key.strip()] = value.strip()
                return {"config_type": "env", "data": env_vars}
        
        elif request.config_type == "yaml":
            # 读取 settings.yaml
            config = load_app_config()
            if request.key:
                # 支持嵌套键（如 "llm.provider"）
                keys = request.key.split(".")
                value = config
                for k in keys:
                    value = getattr(value, k, None)
                    if value is None:
                        raise HTTPException(404, f"配置键 {request.key} 不存在")
                return {"key": request.key, "value": value}
            else:
                # 返回整个配置（转为字典）
                return {"config_type": "yaml", "data": config.model_dump()}
        
        else:
            raise HTTPException(400, f"不支持的配置类型: {request.config_type}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(500, f"获取配置失败: {str(e)}")

@app.post("/api/config/set")
async def set_config(request: ConfigSetRequest):
    """设置配置项（修改 .env）"""
    try:
        if request.persist:
            env_path = project_root / ".env"
            
            # 读取现有内容
            lines = []
            key_found = False
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            
            # 更新或添加配置
            new_lines = []
            for line in lines:
                if line.strip().startswith(f"{request.key}="):
                    new_lines.append(f"{request.key}={request.value}\n")
                    key_found = True
                else:
                    new_lines.append(line)
            
            if not key_found:
                new_lines.append(f"{request.key}={request.value}\n")
            
            # 写回文件
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        
        # 同时更新当前进程环境变量
        os.environ[request.key] = request.value
        
        return {
            "success": True,
            "key": request.key,
            "value": request.value,
            "persisted": request.persist
        }
    
    except Exception as e:
        logger.error(f"设置配置失败: {e}")
        raise HTTPException(500, f"设置配置失败: {str(e)}")

@app.get("/api/config/list")
async def list_configs():
    """列出所有配置项"""
    try:
        env_path = project_root / ".env"
        env_vars = {}
        
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # 隐藏敏感信息
                        if any(x in key.upper() for x in ["KEY", "SECRET", "PASSWORD", "TOKEN"]):
                            value = "***HIDDEN***"
                        env_vars[key.strip()] = value.strip()
        
        return {
            "total": len(env_vars),
            "configs": env_vars
        }
    
    except Exception as e:
        logger.error(f"列出配置失败: {e}")
        raise HTTPException(500, f"列出配置失败: {str(e)}")

# ============================================================
# Pipeline 执行 API
# ============================================================

@app.post("/api/pipeline/run")
async def run_pipeline(request: PipelineRunRequest, background_tasks: BackgroundTasks):
    """运行 Pipeline（完整流程或单个步骤）"""
    try:
        # 生成 episode_id
        episode_id = request.episode_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 加载配置
        config = load_app_config()
        
        # 应用配置覆盖
        if request.config_override:
            for key, value in request.config_override.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # 创建上下文
        EpisodeContext = get_episode_context()
        ctx = EpisodeContext(episode_id=episode_id, config=config)
        
        # 运行 Pipeline
        if request.step:
            # 运行单个步骤
            step_map = {
                "fetch": "FetchStep",
                "cluster": "ClusterStep",
                "select": "SelectionStep",
                "research": "ResearchStep",
                "script": "ScriptStepSegmented",
                "audio": "AudioStepSegmented",
                "publish": "PublishStep"
            }
            
            if request.step not in step_map:
                raise HTTPException(400, f"未知步骤: {request.step}")
            
            # 动态导入步骤
            from src.app.pipelines import steps
            step_class = getattr(steps, step_map[request.step])
            step = step_class()
            
            logger.info(f"运行单步骤: {request.step} (episode_id={episode_id})")
            step.run(ctx)
            
            return {
                "success": True,
                "episode_id": episode_id,
                "step": request.step,
                "status": ctx.status,
                "output_dir": str(ctx.output_dir)
            }
        else:
            # 运行完整流程
            logger.info(f"运行完整 Pipeline (episode_id={episode_id})")
            EpisodePipeline = get_episode_pipeline()
            pipeline = EpisodePipeline()
            pipeline.run(ctx)
            
            return {
                "success": True,
                "episode_id": episode_id,
                "status": ctx.status,
                "output_dir": str(ctx.output_dir),
                "script_segments": len(ctx.script_segments) if ctx.script_segments else 0,
                "audio_files": len(ctx.audio_files) if ctx.audio_files else 0
            }
    
    except Exception as e:
        logger.error(f"Pipeline 运行失败: {e}", exc_info=True)
        raise HTTPException(500, f"Pipeline 运行失败: {str(e)}")

# ============================================================
# 工具/Provider API
# ============================================================

@app.post("/api/llm/call")
async def call_llm(request: LLMCallRequest):
    """调用 LLM"""
    try:
        from src.llm.client.api_client import DeepSeekClient, MoonshotClient
        
        # 选择 LLM 客户端
        if request.provider == "deepseek":
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            model = request.model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            timeout = int(os.getenv("HTTP_TIMEOUT_SECONDS", "180"))
            
            if not api_key:
                raise HTTPException(400, "DEEPSEEK_API_KEY 未配置")
            
            client = DeepSeekClient(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout
            )
        elif request.provider == "moonshot":
            base_url = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
            api_key = os.getenv("MOONSHOT_API_KEY", "")
            model = request.model or os.getenv("MOONSHOT_MODEL", "kimi-k2-0905-preview")
            timeout = int(os.getenv("HTTP_TIMEOUT_SECONDS", "180"))
            
            if not api_key:
                raise HTTPException(400, "MOONSHOT_API_KEY 未配置")
            
            client = MoonshotClient(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout
            )
        else:
            raise HTTPException(400, f"不支持的 LLM 提供商: {request.provider}")
        
        # 调用 LLM
        response = client.generate(
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return {
            "success": True,
            "provider": request.provider,
            "response": response,
            "model": client.model
        }
    
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        raise HTTPException(500, f"LLM 调用失败: {str(e)}")

@app.post("/api/tts/call")
async def call_tts(request: TTSCallRequest):
    """调用 TTS"""
    try:
        from src.audio.tts.doubao_tts import DoubaoTTSClient
        
        # 创建 TTS 客户端
        client = DoubaoTTSClient()
        
        # 生成输出路径
        if not request.output_path:
            output_dir = project_root / "out" / "tts_test"
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            request.output_path = str(output_dir / f"tts_{timestamp}.mp3")
        
        # 调用 TTS
        audio_path = client.synthesize(
            text=request.text,
            output_path=request.output_path,
            voice=request.voice
        )
        
        return {
            "success": True,
            "mode": request.mode,
            "audio_path": str(audio_path),
            "text_length": len(request.text)
        }
    
    except Exception as e:
        logger.error(f"TTS 调用失败: {e}")
        raise HTTPException(500, f"TTS 调用失败: {str(e)}")

@app.post("/api/search/call")
async def call_search(request: SearchRequest):
    """调用搜索 API"""
    try:
        if request.provider == "bocha":
            from src.research.sources.research_client import bocha_web_search_items
            
            # 构造搜索项
            items = [{"title": request.query, "text": ""}]
            
            # 调用博查搜索
            result = bocha_web_search_items(
                items=items,
                api_key=os.getenv("BOCHA_API_KEY", ""),
                count=request.count,
                api_type=request.api_type or "ai-search"
            )
            
            return {
                "success": result.get("ok", False),
                "provider": "bocha",
                "api_type": request.api_type,
                "results": result.get("response_text", ""),
                "metadata": result.get("metadata", {})
            }
        
        elif request.provider == "metaso":
            # TODO: 实现 MetaSo 搜索
            raise HTTPException(501, "MetaSo 搜索暂未实现")
        
        elif request.provider == "anspire":
            # TODO: 实现 Anspire 搜索
            raise HTTPException(501, "Anspire 搜索暂未实现")
        
        else:
            raise HTTPException(400, f"不支持的搜索提供商: {request.provider}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索调用失败: {e}")
        raise HTTPException(500, f"搜索调用失败: {str(e)}")

# ============================================================
# 健康检查
# ============================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "auto-podcast n8n Bridge",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "auto-podcast n8n Bridge API",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
