@echo off
echo ========================================
echo 启动 n8n (Docker 方式)
echo ========================================
echo.

REM 检查 Docker 是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

echo [1/3] 停止旧容器（如果存在）...
docker stop n8n-auto-podcast >nul 2>&1
docker rm n8n-auto-podcast >nul 2>&1

echo [2/3] 启动 n8n 容器...
cd /d "%~dp0"
docker-compose up -d

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ n8n 启动成功！
    echo ========================================
    echo.
    echo 访问地址: http://localhost:5678
    echo.
    echo [3/3] 等待 n8n 初始化（约 10 秒）...
    timeout /t 10 /nobreak >nul
    echo.
    echo 现在可以在浏览器中打开 n8n 了
    echo.
    echo 提示：
    echo - 首次访问需要创建管理员账号
    echo - 导入工作流：点击右上角 "+" -> "Import from File"
    echo - 工作流文件位置：n8n_bridge\workflows\
    echo.
    pause
) else (
    echo.
    echo [错误] n8n 启动失败
    echo 请检查 Docker 是否正常运行
    pause
    exit /b 1
)
