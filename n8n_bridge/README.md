# n8n Bridge for auto-podcast

将 auto-podcast 系统接入 n8n，实现可视化工作流编排和调试。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        n8n Workflows                         │
│  - 完整 Pipeline 流程                                        │
│  - 分步执行流程                                              │
│  - 配置管理                                                  │
│  - 工具调用（LLM/TTS/Search）                                │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Bridge (localhost:8000)                 │
│  - /api/config/*    配置管理 API                             │
│  - /api/pipeline/*  Pipeline 执行 API                        │
│  - /api/llm/*       LLM 调用 API                             │
│  - /api/tts/*       TTS 调用 API                             │
│  - /api/search/*    搜索 API                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              auto-podcast 核心代码                           │
│  EpisodePipeline / Steps / Providers / Agents               │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
# 安装 FastAPI 和 uvicorn
pip install fastapi uvicorn[standard]

# 或添加到 requirements.txt
echo "fastapi>=0.104.0" >> requirements.txt
echo "uvicorn[standard]>=0.24.0" >> requirements.txt
pip install -r requirements.txt
```

### 2. 启动 Bridge API

```bash
# 方式 1：直接运行
python -m uvicorn n8n_bridge.main:app --reload --port 8000

# 方式 2：使用脚本
python n8n_bridge/main.py
```

访问 http://localhost:8000/docs 查看 API 文档。

### 3. 安装 n8n

```bash
# 使用 npm（推荐）
npm install -g n8n

# 或使用 Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### 4. 启动 n8n

```bash
n8n start
```

访问 http://localhost:5678

### 5. 导入工作流

在 n8n 界面中：
1. 点击右上角 "+" → "Import from File"
2. 选择 `n8n_bridge/workflows/` 下的 JSON 文件
3. 激活工作流

## API 端点说明

### 配置管理 API

#### 获取配置
```bash
POST http://localhost:8000/api/config/get
Content-Type: application/json

{
  "config_type": "env",  # env | yaml
  "key": "DEEPSEEK_API_KEY"  # 可选，为空则返回全部
}
```

#### 设置配置
```bash
POST http://localhost:8000/api/config/set
Content-Type: application/json

{
  "key": "DEEPSEEK_API_KEY",
  "value": "sk-xxxxx",
  "persist": true  # 是否写入 .env 文件
}
```

#### 列出所有配置
```bash
GET http://localhost:8000/api/config/list
```

### Pipeline 执行 API

#### 运行完整 Pipeline
```bash
POST http://localhost:8000/api/pipeline/run
Content-Type: application/json

{
  "step": null,  # null = 完整流程
  "config_override": {
    "llm.provider": "deepseek"
  },
  "episode_id": "20260113_test"  # 可选
}
```

#### 运行单个步骤
```bash
POST http://localhost:8000/api/pipeline/run
Content-Type: application/json

{
  "step": "fetch",  # fetch | cluster | select | research | script | audio | publish
  "episode_id": "20260113_test"
}
```

### 工具调用 API

#### LLM 调用
```bash
POST http://localhost:8000/api/llm/call
Content-Type: application/json

{
  "provider": "moonshot",  # moonshot | deepseek
  "prompt": "你好，请介绍一下自己",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

#### TTS 调用
```bash
POST http://localhost:8000/api/tts/call
Content-Type: application/json

{
  "text": "这是一段测试文本",
  "voice": null,  # 使用默认语音
  "mode": "tts",  # tts | podcast | voiceclone_http
  "output_path": null  # 自动生成
}
```

#### 搜索调用
```bash
POST http://localhost:8000/api/search/call
Content-Type: application/json

{
  "query": "阿里巴巴 2024 ESG 报告",
  "provider": "bocha",  # bocha | metaso | anspire
  "count": 10,
  "api_type": "ai-search"  # ai-search | web-search (仅 bocha)
}
```

## n8n 工作流说明

### 1. 完整 Pipeline 流程 (`auto_podcast_full_pipeline.json`)

**用途**：一键运行完整的播客生成流程

**触发方式**：
```bash
curl -X POST http://localhost:5678/webhook/webhook-podcast \
  -H "Content-Type: application/json" \
  -d '{
    "config_override": {"llm.provider": "deepseek"},
    "episode_id": "20260113_test"
  }'
```

**节点流程**：
1. Webhook 触发器
2. 调用 Bridge API 运行完整 Pipeline
3. 返回执行结果（episode_id, status, output_dir）

### 2. 配置管理流程 (`config_management.json`)

**用途**：读取/修改配置项

**触发方式**：
```bash
# 获取配置
curl -X POST http://localhost:5678/webhook/config-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "action": "get",
    "config_type": "env",
    "key": "DEEPSEEK_API_KEY"
  }'

# 设置配置
curl -X POST http://localhost:5678/webhook/config-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "action": "set",
    "key": "DEEPSEEK_API_KEY",
    "value": "sk-xxxxx",
    "persist": true
  }'
```

**节点流程**：
1. Webhook 触发器
2. 判断操作类型（get/set）
3. 调用对应 API
4. 返回结果

### 3. 分步执行流程 (`step_by_step.json`)

**用途**：逐步执行 Pipeline，便于调试

**触发方式**：
```bash
curl -X POST http://localhost:5678/webhook/step-webhook \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20260113_debug"}'
```

**节点流程**：
1. Webhook 触发器
2. 依次执行 7 个步骤：
   - 抓取新闻 (fetch)
   - 聚类去重 (cluster)
   - 选题 (select)
   - 深度研究 (research)
   - 生成脚本 (script)
   - 生成音频 (audio)
   - 发布 (publish)
3. 返回最终结果

## 自定义工作流示例

### 示例 1：定时抓取新闻

在 n8n 中创建新工作流：
1. **Cron 节点**：设置定时触发（如每天早上 8 点）
2. **HTTP Request 节点**：调用 `/api/pipeline/run` 运行 fetch 步骤
3. **Slack/Email 节点**：发送通知

### 示例 2：LLM 对比测试

1. **Manual Trigger**：手动触发
2. **Set 节点**：设置测试 prompt
3. **HTTP Request (Moonshot)**：调用 Moonshot LLM
4. **HTTP Request (DeepSeek)**：调用 DeepSeek LLM
5. **Compare 节点**：对比两个结果
6. **Save to File**：保存对比结果

### 示例 3：配置批量更新

1. **Manual Trigger**：手动触发
2. **Code 节点**：准备配置列表
3. **Loop 节点**：遍历配置项
4. **HTTP Request**：调用 `/api/config/set` 更新配置

## 调试技巧

### 1. 查看 Bridge API 日志

```bash
# 启动时查看详细日志
uvicorn n8n_bridge.main:app --reload --port 8000 --log-level debug
```

### 2. 在 n8n 中查看执行历史

- 点击工作流右上角的"Executions"
- 查看每个节点的输入/输出数据
- 查看错误信息

### 3. 使用 n8n 的 Debug 模式

- 在节点上右键 → "Execute Node"
- 查看单个节点的执行结果

### 4. 测试 API 端点

使用 FastAPI 自动生成的文档：
- 访问 http://localhost:8000/docs
- 直接在浏览器中测试 API

## 扩展开发

### 添加新的 API 端点

在 `n8n_bridge/main.py` 中添加：

```python
@app.post("/api/custom/my-endpoint")
async def my_custom_endpoint(request: MyRequest):
    """自定义端点"""
    try:
        # 你的逻辑
        result = do_something(request)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(500, str(e))
```

### 创建自定义 n8n 节点

如果需要更复杂的节点（如带 UI 的配置面板），可以开发自定义 n8n 节点：
- 参考：https://docs.n8n.io/integrations/creating-nodes/

## 常见问题

### Q: Bridge API 启动失败？
A: 检查端口 8000 是否被占用，或修改端口：
```bash
uvicorn n8n_bridge.main:app --port 8001
```

### Q: n8n 无法连接到 Bridge API？
A: 
1. 确认 Bridge API 正在运行（访问 http://localhost:8000/health）
2. 检查防火墙设置
3. 如果 n8n 在 Docker 中，使用 `host.docker.internal:8000` 而非 `localhost:8000`

### Q: 配置修改后不生效？
A: 
1. 检查 `.env` 文件是否正确更新
2. 重启 Bridge API 以重新加载环境变量
3. 某些配置需要重启整个系统

### Q: Pipeline 执行失败？
A: 
1. 查看 Bridge API 日志
2. 检查 `out/runs/{episode_id}/` 下的日志文件
3. 确认所有必需的配置项（API Key 等）已设置

## 生产部署建议

### 1. 使用进程管理器

```bash
# 使用 systemd
sudo nano /etc/systemd/system/n8n-bridge.service

[Unit]
Description=n8n Bridge API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/auto-podcast
ExecStart=/path/to/venv/bin/uvicorn n8n_bridge.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target

# 启动服务
sudo systemctl enable n8n-bridge
sudo systemctl start n8n-bridge
```

### 2. 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 添加认证

在 `n8n_bridge/main.py` 中添加 API Key 验证：

```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("N8N_BRIDGE_API_KEY"):
        raise HTTPException(401, "Invalid API Key")

@app.post("/api/pipeline/run", dependencies=[Depends(verify_api_key)])
async def run_pipeline(request: PipelineRunRequest):
    # ...
```

## 许可证

与 auto-podcast 主项目保持一致。
