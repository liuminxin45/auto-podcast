const { makeRequest, makeStreamingRequest } = require('./httpClient')
const { ensureLLMGateway, stopLLMGateway } = require('./llmGatewayProcess')

const DEFAULT_TIMEOUT = 30000
const STREAMING_TIMEOUT = 180000

async function fetchModels({ apiBase, apiKey }) {
  const gateway = await ensureLLMGateway()
  const url = `${gateway.baseUrl}/models`

  try {
    const response = await makeRequest({
      url,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: {
        api_base: apiBase,
        api_key: apiKey,
        timeout: Math.ceil(DEFAULT_TIMEOUT / 1000)
      },
      timeout: DEFAULT_TIMEOUT
    })
    return response.body
  } catch (error) {
    throw new Error(`Failed to fetch models: ${error.message}`)
  }
}

async function callLLM({ apiBase, apiKey, model, messages, temperature = 0.3, maxTokens, timeout, stream = false, eventSender = null }) {
  const gateway = await ensureLLMGateway()
  const url = `${gateway.baseUrl}/chat/completions`
  const headers = { 'Content-Type': 'application/json' }
  const requestTimeout = typeof timeout === 'number' ? timeout : STREAMING_TIMEOUT
  const body = {
    api_base: apiBase,
    api_key: apiKey,
    model,
    messages,
    temperature,
    timeout: Math.ceil(requestTimeout / 1000),
    stream
  }
  if (typeof maxTokens === 'number') {
    body.max_tokens = maxTokens
  }

  if (stream) {
    if (!eventSender) {
      throw new Error('eventSender is required for streaming mode')
    }

    return makeStreamingRequest({
      url,
      method: 'POST',
      headers,
      body,
      timeout: requestTimeout,
      onChunk: (content) => eventSender.send('llm:stream:chunk', content),
      onEnd: () => eventSender.send('llm:stream:done'),
      onError: (error) => eventSender.send('llm:stream:error', error)
    })
  } else {
    try {
      const response = await makeRequest({ url, method: 'POST', headers, body, timeout: requestTimeout })
      return response.body
    } catch (error) {
      throw new Error(`LLM call failed: ${error.message}`)
    }
  }
}

module.exports = {
  fetchModels,
  callLLM,
  stopLLMGateway
}
