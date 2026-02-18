class SerializedTaskQueue {
  private queue: Promise<void> = Promise.resolve()

  async run<T>(task: () => Promise<T>): Promise<T> {
    const previous = this.queue
    let releaseCurrent: () => void = () => {}
    this.queue = new Promise<void>((resolve) => {
      releaseCurrent = resolve
    })

    await previous
    try {
      return await task()
    } finally {
      releaseCurrent()
    }
  }
}

const RATE_LIMIT_PATTERN = /HTTP\s*429|insufficient_quota|负载已饱和/i
const TIMEOUT_PATTERN = /request timeout|timeout|超时/i

function getErrorMessage(error: unknown): string {
  if (!error || typeof error !== 'object') return ''
  return String((error as { message?: unknown }).message || '').trim()
}

export function isRateLimitedError(error: unknown): boolean {
  return RATE_LIMIT_PATTERN.test(getErrorMessage(error))
}

export function isTimeoutError(error: unknown): boolean {
  return TIMEOUT_PATTERN.test(getErrorMessage(error))
}

export function toUserFacingErrorMessage(error: unknown, fallback: string): string {
  const rawMessage = getErrorMessage(error)
  if (!rawMessage) return fallback

  if (isRateLimitedError(error)) {
    return 'LLM 服务当前繁忙（429），请稍后重试。'
  }

  if (isTimeoutError(error)) {
    return 'LLM 请求超时，请稍后重试或在设置中增加超时时间。'
  }

  return rawMessage
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export const serializedLLMQueue = new SerializedTaskQueue()
