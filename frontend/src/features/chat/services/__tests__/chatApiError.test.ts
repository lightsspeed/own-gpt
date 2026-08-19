import { describe, it, expect, vi, afterEach } from 'vitest'
import { api, responseError } from '../chatApi'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('responseError', () => {
  it('surfaces the backend error envelope message', async () => {
    const err = await responseError(jsonResponse(404, {
      error: { code: 'project_not_found', message: 'Project not found' },
    }))
    expect(err.message).toBe('Project not found')
  })

  it('surfaces plain detail strings (FastAPI HTTPException)', async () => {
    const err = await responseError(jsonResponse(400, { detail: "Unsupported file type '.xyz'" }))
    expect(err.message).toBe("Unsupported file type '.xyz'")
  })

  it('falls back to Server error for opaque bodies', async () => {
    const err = await responseError(jsonResponse(500, { unexpected: true }))
    expect(err.message).toBe('Server error')
  })
})

describe('api.sendMessage error contract', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('throws backend message for non-OK responses', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      jsonResponse(404, { error: { code: 'project_not_found', message: 'Project not found' } }),
    ))
    await expect(api.sendMessage({
      sessionId: 's-1',
      message: 'hello',
      systemPrompt: '',
      projectId: 'missing-project',
    })).rejects.toThrow('Project not found')
  })

  it('returns the response when OK', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      jsonResponse(200, new Uint8Array(0)),
    ))
    const res = await api.sendMessage({ sessionId: 's-1', message: 'hello', systemPrompt: '', projectId: null })
    expect(res.ok).toBe(true)
  })
})