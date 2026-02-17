/**
 * Quick Integration Verification Script
 * Verifies LLM service integration without full test framework
 */

const fs = require('fs')
const path = require('path')

console.log('🔍 LLM Service Integration Verification\n')

// Check 1: Verify llmService imports
console.log('✓ Check 1: Verifying llmService imports...')
const filesToCheck = [
  'src/utils/llmClassifier.ts',
  'src/components/LLMConfigFields.tsx',
  'src/services/organizeAI.ts',
]

let importCount = 0
for (const file of filesToCheck) {
  const filePath = path.join(__dirname, '..', file)
  if (!fs.existsSync(filePath)) {
    console.log(`  ⚠️  ${file} not found`)
    continue
  }
  
  const content = fs.readFileSync(filePath, 'utf-8')
  if (content.includes('llmService')) {
    console.log(`  ✅ ${file}`)
    importCount++
  } else {
    console.log(`  ❌ ${file} - NOT using llmService`)
  }
}
console.log(`  → ${importCount}/${filesToCheck.length} files using llmService\n`)

// Check 2: Verify no direct fetch to /chat/completions (except in llmService itself)
console.log('✓ Check 2: Verifying no direct LLM API calls...')
const srcPath = path.join(__dirname, '..', 'src')
let directCallsFound = []

function scanDirectory(dir) {
  const files = fs.readdirSync(dir)
  
  for (const file of files) {
    const filePath = path.join(dir, file)
    const stat = fs.statSync(filePath)
    
    if (stat.isDirectory()) {
      if (!file.startsWith('.') && file !== 'node_modules' && file !== '__tests__') {
        scanDirectory(filePath)
      }
    } else if (file.endsWith('.ts') || file.endsWith('.tsx')) {
      // Skip llmService.ts itself and test files
      if (file === 'llmService.ts' || file.includes('.test.')) {
        continue
      }
      
      const content = fs.readFileSync(filePath, 'utf-8')
      
      // Check for direct fetch to chat/completions
      if (content.includes('chat/completions') && content.includes('fetch(')) {
        const relativePath = path.relative(path.join(__dirname, '..'), filePath)
        directCallsFound.push(relativePath)
      }
    }
  }
}

scanDirectory(srcPath)

if (directCallsFound.length === 0) {
  console.log('  ✅ No direct API calls found outside llmService\n')
} else {
  console.log('  ❌ Direct API calls found in:')
  directCallsFound.forEach(file => console.log(`     - ${file}`))
  console.log()
}

// Check 3: Verify service layer features exist
console.log('✓ Check 3: Verifying service layer features...')
const llmServicePath = path.join(__dirname, '..', 'src', 'services', 'llmService.ts')
const llmServiceContent = fs.readFileSync(llmServicePath, 'utf-8')

const features = [
  { name: 'Cache', check: 'getFromCache' },
  { name: 'Rate Limiting', check: 'checkRateLimit' },
  { name: 'Metrics', check: 'getMetrics' },
  { name: 'Streaming', check: 'callStreaming' },
  { name: 'Error Handling', check: 'LLMError' },
]

features.forEach(feature => {
  if (llmServiceContent.includes(feature.check)) {
    console.log(`  ✅ ${feature.name}`)
  } else {
    console.log(`  ❌ ${feature.name} - NOT found`)
  }
})
console.log()

// Check 4: Verify constants are centralized
console.log('✓ Check 4: Verifying centralized constants...')
const constantsPath = path.join(__dirname, '..', 'src', 'constants', 'llm.ts')
if (fs.existsSync(constantsPath)) {
  const constantsContent = fs.readFileSync(constantsPath, 'utf-8')
  const hasDefaults = constantsContent.includes('LLM_DEFAULTS')
  const hasModels = constantsContent.includes('LLM_MODELS')
  
  if (hasDefaults && hasModels) {
    console.log('  ✅ Constants centralized in src/constants/llm.ts\n')
  } else {
    console.log('  ⚠️  Constants file exists but incomplete\n')
  }
} else {
  console.log('  ❌ Constants file not found\n')
}

// Check 5: Verify Python LLM client exists
console.log('✓ Check 5: Verifying Python LLM client...')
const pythonClientPath = path.join(__dirname, '..', 'protocol', 'llm_client.py')
if (fs.existsSync(pythonClientPath)) {
  const pythonContent = fs.readFileSync(pythonClientPath, 'utf-8')
  if (pythonContent.includes('class LLMClient')) {
    console.log('  ✅ Python LLMClient exists\n')
  } else {
    console.log('  ⚠️  llm_client.py exists but LLMClient class not found\n')
  }
} else {
  console.log('  ❌ Python LLMClient not found\n')
}

// Summary
console.log('═══════════════════════════════════════')
console.log('Summary:')
console.log(`  Service Layer Integration: ${importCount}/${filesToCheck.length} files`)
console.log(`  Direct API Calls: ${directCallsFound.length === 0 ? '✅ None' : '❌ ' + directCallsFound.length}`)
console.log(`  Features: ${features.filter(f => llmServiceContent.includes(f.check)).length}/${features.length}`)
console.log('═══════════════════════════════════════\n')

// Exit code
const allPassed = importCount === filesToCheck.length && directCallsFound.length === 0
process.exit(allPassed ? 0 : 1)
