import { describe, it, expect } from 'vitest'
import { buildChatRequestBody } from '../chatApi'

describe('buildChatRequestBody', () => {
  it('includes project_id when a project is selected', () => {
    const body = buildChatRequestBody({
      sessionId: 's-1',
      message: 'hello',
      systemPrompt: '',
      projectId: 'proj-alpha',
    })
    expect(body.project_id).toBe('proj-alpha')
  })

  it('omits project_id when no project is selected', () => {
    const body = buildChatRequestBody({
      sessionId: 's-1',
      message: 'hello',
      systemPrompt: '',
      projectId: null,
    })
    expect('project_id' in body).toBe(false)
  })

  it('omits project_id when undefined', () => {
    const body = buildChatRequestBody({
      sessionId: 's-1',
      message: 'hello',
      systemPrompt: '',
      projectId: undefined,
    })
    expect('project_id' in body).toBe(false)
  })

  it('switching projects updates the project_id field', () => {
    const a = buildChatRequestBody({ sessionId: 's-1', message: 'x', systemPrompt: '', projectId: 'proj-a' })
    const b = buildChatRequestBody({ sessionId: 's-1', message: 'x', systemPrompt: '', projectId: 'proj-b' })
    expect(a.project_id).toBe('proj-a')
    expect(b.project_id).toBe('proj-b')
  })

  it('maps active tools to web/kb booleans', () => {
    const body = buildChatRequestBody({
      sessionId: 's-1',
      message: 'x',
      systemPrompt: '',
      activeTools: { web_search: 'auto', knowledge_base: 'disabled' },
    })
    expect(body.active_tools).toEqual({ web: true, kb: false })
  })
})