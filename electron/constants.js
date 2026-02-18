const STREAM_EVENTS = {
  CHUNK: 'llm:stream:chunk',
  DONE: 'llm:stream:done',
  ERROR: 'llm:stream:error'
}

const TIMEOUTS = {
  LLM_DEFAULT: 30000,
  LLM_STREAMING: 180000,
  NODE_DEFAULT: 600000
}

module.exports = {
  STREAM_EVENTS,
  TIMEOUTS
}
