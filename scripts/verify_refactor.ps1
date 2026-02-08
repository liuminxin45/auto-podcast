# Verification script for refactored code (PowerShell)

Write-Host "=== Verifying Auto-Podcast Studio Refactor ===" -ForegroundColor Cyan

# 1. Check Python dependencies
Write-Host "`n1. Checking Python dependencies..." -ForegroundColor Yellow
try {
    python -c "import feedparser, requests, trafilatura, pydantic" 2>$null
    Write-Host "✓ Python deps OK" -ForegroundColor Green
} catch {
    Write-Host "✗ Missing Python deps" -ForegroundColor Red
}

# 2. Check Node modules
Write-Host "`n2. Checking Node modules..." -ForegroundColor Yellow
if (Test-Path "node_modules") {
    Write-Host "✓ Node modules installed" -ForegroundColor Green
} else {
    Write-Host "✗ Run npm install" -ForegroundColor Red
}

# 3. Verify node structure
Write-Host "`n3. Verifying node structure..." -ForegroundColor Yellow
$nodes = @('source_selector', 'fetch', 'manual', 'preprocess', 'research', 'topic_selection', 'script', 'stages', 'tts', 'audio_postprocess', 'assets', 'store', 'publish')
foreach ($node in $nodes) {
    if (Test-Path "nodes\$node\__main__.py") {
        Write-Host "✓ $node node OK" -ForegroundColor Green
    } else {
        Write-Host "✗ $node node missing" -ForegroundColor Red
    }
}

# 4. Check fetch sources
Write-Host "`n4. Checking fetch sources..." -ForegroundColor Yellow
try {
    python scripts\get_fetch_sources.py | Out-Null
    Write-Host "✓ Fetch sources OK" -ForegroundColor Green
} catch {
    Write-Host "✗ Fetch sources error" -ForegroundColor Red
}

# 5. Build frontend
Write-Host "`n5. Building frontend..." -ForegroundColor Yellow
try {
    npm run build 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Frontend build OK" -ForegroundColor Green
    } else {
        Write-Host "✗ Frontend build failed" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ Frontend build failed" -ForegroundColor Red
}

Write-Host "`n=== Verification Complete ===" -ForegroundColor Cyan
