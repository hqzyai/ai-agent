import { describe, expect, it, vi } from 'vitest'

import plugin from './plugin'


describe('channels plugin registration', () => {
  it('registers one channels route and one sidebar entry', () => {
    const registerMany = vi.fn()

    plugin.register({
      registerMany,
      os: { openExternal: vi.fn(async () => true) }
    } as never)

    expect(registerMany).toHaveBeenCalledTimes(1)
    const contributions = registerMany.mock.calls[0]?.[0] ?? []
    expect(
      contributions.map(({ id, order, data }: { id: string; order?: number; data: unknown }) => ({
        id,
        order,
        data
      }))
    ).toEqual([
      { id: 'page', order: undefined, data: { path: '/channels' } },
      {
        id: 'nav',
        order: 32,
        data: { codicon: 'comment-discussion', label: 'IM频道', path: '/channels' }
      }
    ])
  })
})
