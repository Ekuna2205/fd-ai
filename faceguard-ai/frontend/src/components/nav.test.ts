import { describe, expect, it } from 'vitest'
import { visibleGroups } from './nav'

const links = (role?: Parameters<typeof visibleGroups>[0]) => visibleGroups(role).flatMap((g) => g.items.map((i) => i.to))

describe('role-aware navigation', () => {
  it('shows viewers only read-only areas', () => {
    const l = links('viewer')
    expect(l).toEqual(expect.arrayContaining(['/', '/history', '/reports', '/models', '/settings']))
    for (const hidden of ['/verify', '/challenge', '/uploads', '/datasets', '/admin']) expect(l).not.toContain(hidden)
  })
  it('lets operators verify but not manage datasets or users', () => {
    const l = links('operator')
    expect(l).toEqual(expect.arrayContaining(['/verify', '/challenge', '/uploads']))
    expect(l).not.toContain('/datasets'); expect(l).not.toContain('/admin')
  })
  it('gives researchers datasets but not administration', () => {
    const l = links('researcher'); expect(l).toContain('/datasets'); expect(l).not.toContain('/admin')
  })
  it('gives administrators everything', () => { expect(links('administrator')).toEqual(expect.arrayContaining(['/datasets', '/admin', '/verify'])) })
  it('shows nothing restricted without a role', () => { expect(links(undefined)).not.toContain('/admin') })
})
