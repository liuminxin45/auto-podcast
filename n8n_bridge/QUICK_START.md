# n8n Bridge 快速启动指南

## 当前状态

✅ **FastAPI Bridge 已启动并测试通过**
- 运行在：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs
- 核心功能测试：4/6 通过

⏳ **n8n 安装中**
- 使用淘宝镜像加速
- 预计还需要一些时间

---

## 方案选择

### 🎯 方案 1：等待 npm 安装完成（当前进行中）

**优点**：
- 全局安装，可以直接使用 `n8n` 命令
- 适合长期使用

**缺点**：
- 首次安装时间较长（10-30 分钟）
- 依赖包较多

**使用方法**（安装完成后）：
```bash
# 启动 n8n
n8n start

# 访问
http://localhost:5678
```

---

### 🚀 方案 2：使用 npx 临时运行（推荐，无需等待）

**优点**：
- 无需等待全局安装
- 首次运行会自动下载
- 不污染全局环境

**使用方法**：
```bash
# 直接运行（首次会自动下载）
npx n8n

# 访问
http://localhost:5678
```

---

### 🐳 方案 3：使用 Docker（最简单，但需要安装 Docker）

**优点**：
- 环境隔离
- 一键启动/停止
- 包含数据持久化

**前提**：需要先安装 Docker Desktop
- 下载地址：https://www.docker.com/products/docker-desktop/

**使用方法**：
```bash
# 方式 1：使用 docker-compose
cd e:\neo\auto-podcast\n8n_bridge
docker-compose up -d

# 方式 2：使用启动脚本
start_n8n_docker.bat

# 访问
http://localhost:5678
```

---

## 不使用 n8n 的替代方案

如果你只是想测试 Bridge API 功能，可以**不安装 n8n**，直接使用以下工具：

### 方式 1：使用 Python 测试脚本（已提供）

```bash
# 运行完整测试
python n8n_bridge/test_api.py

# 测试单个功能
python -c "
import requests
response = requests.get('http://127.0.0.1:8000/api/config/list')
print(response.json())
"
```

### 方式 2：使用 Postman 或 Insomnia

1. 下载 Postman：https://www.postman.com/downloads/
2. 导入 API 端点：
   - GET http://127.0.0.1:8000/health
   - GET http://127.0.0.1:8000/api/config/list
   - POST http://127.0.0.1:8000/api/config/get
   - POST http://127.0.0.1:8000/api/pipeline/run

### 方式 3：使用 FastAPI 自带的 Swagger UI

直接在浏览器中打开：
```
http://127.0.0.1:8000/docs
```

可以直接在网页中测试所有 API 端点！

---

## 推荐的工作流程

### 阶段 1：测试 Bridge API（当前可用）

1. **确认 Bridge API 运行正常**：
   ```bash
   curl http://127.0.0.1:8000/health
   ```

2. **在浏览器中打开 API 文档**：
   ```
   http://127.0.0.1:8000/docs
   ```

3. **测试配置管理**：
   - 点击 `/api/config/list` → "Try it out" → "Execute"
   - 查看返回的 47 个配置项

4. **测试搜索功能**（需要配置 BOCHA_API_KEY）：
   - 点击 `/api/search/call` → "Try it out"
   - 输入测试数据并执行

### 阶段 2：集成 n8n（可选）

等 npm 安装完成后，或者使用 `npx n8n` 直接运行：

1. **启动 n8n**
2. **导入工作流**：
   - 打开 http://localhost:5678
   - 点击右上角 "+" → "Import from File"
   - 选择 `n8n_bridge/workflows/` 下的 JSON 文件
3. **配置节点**：
   - HTTP Request 节点的 URL 设置为 `http://127.0.0.1:8000/api/*`
4. **测试工作流**

---

## 常见问题

### Q1: npm 安装一直卡住怎么办？

**解决方案**：
1. 已切换到淘宝镜像（当前状态）
2. 或者使用 `npx n8n` 直接运行
3. 或者安装 Docker 使用容器方式

### Q2: Bridge API 启动失败？

**检查清单**：
- [ ] 端口 8000 是否被占用？
- [ ] Python 依赖是否安装完整？
- [ ] .env 文件是否存在？

**解决方法**：
```bash
# 检查端口占用
netstat -ano | findstr :8000

# 重新安装依赖
pip install fastapi uvicorn[standard]

# 重启 Bridge API
python -m uvicorn n8n_bridge.main:app --host 127.0.0.1 --port 8000
```

### Q3: API 调用返回错误？

**常见原因**：
1. **API Key 未配置**：编辑 `.env` 文件，替换 `replace_me` 为真实的 API Key
2. **配置文件缺失**：确保 `config/base/settings.yaml` 存在
3. **模块导入失败**：运行 `pip install -r requirements.txt` 安装所有依赖

### Q4: 不想用 n8n，有其他可视化工具吗？

**替代方案**：
1. **FastAPI Swagger UI**（已内置）：http://127.0.0.1:8000/docs
2. **Postman**：专业的 API 测试工具
3. **Insomnia**：轻量级 API 客户端
4. **VS Code REST Client**：在编辑器中直接测试 API

---

## 下一步建议

### 立即可做（无需等待 n8n）：

1. ✅ **在浏览器中打开 Swagger UI**：
   ```
   http://127.0.0.1:8000/docs
   ```

2. ✅ **测试配置管理功能**：
   - 列出所有配置
   - 读取单个配置
   - 修改配置（谨慎操作）

3. ✅ **配置有效的 API Key**：
   - 编辑 `.env` 文件
   - 替换占位符为真实的 Key
   - 重启 Bridge API

4. ✅ **测试工具调用**：
   - LLM 调用（需要 DEEPSEEK_API_KEY）
   - 搜索调用（需要 BOCHA_API_KEY）

### 等 n8n 安装完成后：

1. 🔄 **启动 n8n**
2. 🔄 **导入预置工作流**
3. 🔄 **测试工作流执行**
4. 🔄 **创建自定义工作流**

---

## 联系与支持

如果遇到问题：
1. 查看 Bridge API 日志
2. 查看 `out/runs/{episode_id}/` 下的日志文件
3. 检查 API 文档：http://127.0.0.1:8000/docs

---

**最后更新**：2026-01-13 23:48
**Bridge API 状态**：✅ 运行中
**n8n 状态**：⏳ 安装中
