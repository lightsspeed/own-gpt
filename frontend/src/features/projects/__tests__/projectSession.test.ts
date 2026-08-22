import { describe, it, expect } from 'vitest'
import {
  GENERAL_PROJECT_KEY,
  projectSessionKey,
  ensureProjectSession,
  removeSessionFromRegistry,
} from '../projectSession'

describe('projectSessionKey', () => {
  it('uses the general key when no project is active', () => {
    expect(projectSessionKey(null)).toBe(GENERAL_PROJECT_KEY)
    expect(projectSessionKey(undefined)).toBe(GENERAL_PROJECT_KEY)
    expect(projectSessionKey('')).toBe(GENERAL_PROJECT_KEY)
  })

  it('uses the project id when a project is active', () => {
    expect(projectSessionKey('proj-alpha')).toBe('proj-alpha')
  })
})

describe('ensureProjectSession', () => {
  it('creates a session for the no-project state', () => {
    const { registry, sessionId } = ensureProjectSession({}, null, () => 's-1')
    expect(sessionId).toBe('s-1')
    expect(registry[GENERAL_PROJECT_KEY]).toBe('s-1')
  })

  it('creates a separate session when switching projects', () => {
    let n = 0
    const first = ensureProjectSession({}, 'proj-a', () => `s-${++n}`)
    const second = ensureProjectSession(first.registry, 'proj-b', () => `s-${++n}`)
    expect(first.sessionId).toBe('s-1')
    expect(second.sessionId).toBe('s-2')
    expect(second.registry['proj-a']).toBe('s-1')
    expect(second.registry['proj-b']).toBe('s-2')
    expect(second.sessionId).not.toBe(first.sessionId)
  })

  it('switching projects does not reuse the previous project session', () => {
    const first = ensureProjectSession({}, 'proj-a', () => 's-a')
    const second = ensureProjectSession(first.registry, 'proj-b', () => 's-b')
    expect(second.sessionId).toBe('s-b')
    expect(second.sessionId).not.toBe('s-a')
  })

  it('reuses the existing session when returning to a project', () => {
    const first = ensureProjectSession({}, 'proj-a', () => 's-a')
    const switched = ensureProjectSession(first.registry, 'proj-b', () => 's-b')
    const back = ensureProjectSession(switched.registry, 'proj-a', () => 's-new')
    expect(back.sessionId).toBe('s-a')
    expect(back.sessionId).not.toBe('s-new')
  })

  it('never reuses a project session for the no-project state', () => {
    const first = ensureProjectSession({}, 'proj-a', () => 's-a')
    const general = ensureProjectSession(first.registry, null, () => 's-gen')
    expect(general.sessionId).toBe('s-gen')
    expect(general.sessionId).not.toBe('s-a')
  })
})

describe('removeSessionFromRegistry', () => {
  it('removes the entry pointing at the deleted session', () => {
    const registry = ensureProjectSession({}, 'proj-a', () => 's-a').registry
    const next = removeSessionFromRegistry(registry, 's-a')
    expect(next).toEqual({})
  })

  it('leaves other project sessions intact', () => {
    const { registry } = ensureProjectSession(ensureProjectSession({}, 'proj-a', () => 's-a').registry, 'proj-b', () => 's-b')
    const next = removeSessionFromRegistry(registry, 's-a')
    expect(next['proj-b']).toBe('s-b')
  })

  it('returns the same reference when nothing changed', () => {
    const registry = { 'proj-a': 's-a' }
    expect(removeSessionFromRegistry(registry, 's-other')).toBe(registry)
  })
})