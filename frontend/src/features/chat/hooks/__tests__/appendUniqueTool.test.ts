import { describe, it, expect } from 'vitest'
import { appendUniqueTool } from '../useChat'

describe('appendUniqueTool', () => {
  it('adds a new tool name', () => {
    expect(appendUniqueTool(['web_search'], 'search_knowledge_base')).toEqual([
      'web_search',
      'search_knowledge_base',
    ])
  })

  it('does not duplicate an existing tool name', () => {
    expect(appendUniqueTool(['web_search'], 'web_search')).toEqual(['web_search'])
  })

  it('handles an empty list', () => {
    expect(appendUniqueTool([], 'memory')).toEqual(['memory'])
  })
})