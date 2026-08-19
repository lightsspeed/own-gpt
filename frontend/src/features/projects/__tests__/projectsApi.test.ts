import { describe, it, expect, afterEach, vi } from 'vitest'
import { parseProjectsResponse, projectsApi } from '../services/projectsApi'

function mockFetchOnce(status: number, body: unknown) {
  return vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('parseProjectsResponse', () => {
  it('returns projects from a valid response', () => {
    const list = parseProjectsResponse({ projects: [{ id: 'p1' }], total: 1 })
    expect(list).toHaveLength(1)
    expect(list[0].id).toBe('p1')
  })

  it('returns an empty list for an empty response', () => {
    expect(parseProjectsResponse({ projects: [], total: 0 })).toEqual([])
  })

  it('throws on an invalid response shape', () => {
    expect(() => parseProjectsResponse({ items: [] })).toThrow()
  })
})

describe('projectsApi.list', () => {
  it('fetches /projects and parses the list', async () => {
    const body = { projects: [{ id: 'p1', name: 'Alpha' }], total: 1 }
    mockFetchOnce(200, body)
    const projects = await projectsApi.list()
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/v1/projects')
    expect(projects).toHaveLength(1)
    expect(projects[0].name).toBe('Alpha')
  })

  it('throws when the request fails', async () => {
    mockFetchOnce(500, {})
    await expect(projectsApi.list()).rejects.toThrow('HTTP 500')
  })
})

describe('projectsApi.create', () => {
  it('posts the project name and returns the created project', async () => {
    mockFetchOnce(201, { id: 'p2', name: 'Beta' })
    const project = await projectsApi.create(' Beta ')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/projects',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Beta', description: undefined }),
      }),
    )
    expect(project.id).toBe('p2')
  })

  it('throws when creation fails', async () => {
    mockFetchOnce(409, {})
    await expect(projectsApi.create('X')).rejects.toThrow('HTTP 409')
  })
})