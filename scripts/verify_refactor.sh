#!/bin/bash
# Verification script for refactored code

echo "=== Verifying Auto-Podcast Studio Refactor ==="

# 1. Check Python dependencies
echo -e "\n1. Checking Python dependencies..."
python -c "import feedparser, requests, trafilatura, pydantic" && echo "✓ Python deps OK" || echo "✗ Missing Python deps"

# 2. Check Node modules
echo -e "\n2. Checking Node modules..."
[ -d "node_modules" ] && echo "✓ Node modules installed" || echo "✗ Run npm install"

# 3. Verify node structure
echo -e "\n3. Verifying node structure..."
for node in source_selector fetch manual preprocess research topic_selection script stages tts audio_postprocess assets store publish; do
  if [ -f "nodes/$node/__main__.py" ]; then
    echo "✓ $node node OK"
  else
    echo "✗ $node node missing"
  fi
done

# 4. Check fetch sources
echo -e "\n4. Checking fetch sources..."
python scripts/get_fetch_sources.py > /dev/null 2>&1 && echo "✓ Fetch sources OK" || echo "✗ Fetch sources error"

# 5. Build frontend
echo -e "\n5. Building frontend..."
npm run build > /dev/null 2>&1 && echo "✓ Frontend build OK" || echo "✗ Frontend build failed"

echo -e "\n=== Verification Complete ==="
