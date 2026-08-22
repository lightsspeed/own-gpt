import { describe, it, expect, vi, afterEach } from 'vitest'
import { api } from '../chatApi'

describe('api.sendMessage abort signal', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('passes the stop() AbortSignal through to fetch', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn(async (_url: string, _options: RequestInit) =>
      new Response(new Uint8Array(0), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.sendMessage({
      sessionId: 's-1',
      message: 'hello',
      systemPrompt: '',
      projectId: null,
      signal: controller.signal,
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const options = fetchMock.mock.calls[0][1] as RequestInit
    expect(options.signal).toBe(controller.signal)
  })

  it('aborting the controller rejects the in-flight request with AbortError', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn((_url: string, opts: RequestInit) => new Promise((_resolve, reject) => {
      opts.signal?.addEventListener('abort', () => {
        reject(new DOMException('The operation was aborted.', 'AbortError'))
      })
    }))
    vi.stubGlobal('fetch', fetchMock)

    const promise = api.sendMessage({
      sessionId: 's-1',
      message: 'hello',
      systemPrompt: '',
      projectId: null,
      signal: controller.signal,
    })
    controller.abort()

    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('omits the signal when stop() never created a controller', async () => {
    const fetchMock = vi.fn(async (_url: string, _options: RequestInit) =>
      new Response(new Uint8Array(0), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.sendMessage({ sessionId: 's-1', message: 'hello', systemPrompt: '', projectId: null })

    const options = fetchMock.mock.calls[0][1] as RequestInit
    expect(options.signal).toBeUndefined()
  })
})