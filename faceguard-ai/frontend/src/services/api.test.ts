import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type Handler = (cfg: InternalAxiosRequestConfig) => { status: number; data?: unknown }
let handler: Handler
let calls: { url: string; auth?: string }[]

const adapter: AxiosAdapter = async (config) => {
  calls.push({ url: config.url ?? '', auth: config.headers.get('Authorization') as string | undefined })
  const { status, data } = handler(config)
  const response = { data: data ?? {}, status, statusText: '', headers: {}, config }
  if (status >= 400) throw new AxiosError('failed', 'ERR_BAD_REQUEST', config, null, response)
  return response
}

async function load() {
  vi.resetModules()
  axios.defaults.adapter = adapter // both the API client and the bare refresh client inherit this
  const { api, UNAUTHORIZED_EVENT } = await import('./api')
  const { tokenStore } = await import('@/utils/tokenStore')
  return { api, tokenStore, UNAUTHORIZED_EVENT }
}

beforeEach(() => { calls = []; sessionStorage.clear() })
afterEach(() => { delete (axios.defaults as { adapter?: unknown }).adapter })

describe('silent token refresh', () => {
  it('refreshes once on 401, retries with the new token, and stores the rotated pair', async () => {
    const { api, tokenStore } = await load()
    tokenStore.set('old-access', 'refresh-1')
    handler = (cfg) => cfg.url === '/auth/refresh' ? { status: 200, data: { access_token: 'new-access', refresh_token: 'refresh-2' } }
      : cfg.headers.get('Authorization') === 'Bearer new-access' ? { status: 200, data: { ok: true } } : { status: 401 }
    expect((await api.get('/dashboard/overview')).data).toEqual({ ok: true })
    expect(calls.map((c) => c.url)).toEqual(['/dashboard/overview', '/auth/refresh', '/dashboard/overview'])
    expect(tokenStore.get()).toBe('new-access')
    expect(tokenStore.getRefresh()).toBe('refresh-2')
  })

  it('shares one refresh between concurrent 401s (refresh tokens are single-use)', async () => {
    const { api, tokenStore } = await load()
    tokenStore.set('old', 'r1')
    handler = (cfg) => cfg.url === '/auth/refresh' ? { status: 200, data: { access_token: 'new', refresh_token: 'r2' } }
      : cfg.headers.get('Authorization') === 'Bearer new' ? { status: 200 } : { status: 401 }
    await Promise.all([api.get('/a'), api.get('/b'), api.get('/c')])
    expect(calls.filter((c) => c.url === '/auth/refresh')).toHaveLength(1)
  })

  it('ends the session when the refresh itself is rejected', async () => {
    const { api, tokenStore, UNAUTHORIZED_EVENT } = await load()
    tokenStore.set('old', 'revoked')
    const onEnd = vi.fn(); window.addEventListener(UNAUTHORIZED_EVENT, onEnd)
    handler = () => ({ status: 401 })
    await expect(api.get('/dashboard/overview')).rejects.toBeTruthy()
    expect(tokenStore.get()).toBeNull(); expect(tokenStore.getRefresh()).toBeNull()
    expect(onEnd).toHaveBeenCalledTimes(1)
    expect(calls.filter((c) => c.url === '/auth/refresh')).toHaveLength(1) // no refresh loop
    window.removeEventListener(UNAUTHORIZED_EVENT, onEnd)
  })

  it('does not loop when the retried request is rejected again', async () => {
    const { api, tokenStore } = await load()
    tokenStore.set('old', 'r1')
    handler = (cfg) => cfg.url === '/auth/refresh' ? { status: 200, data: { access_token: 'n', refresh_token: 'r2' } } : { status: 401 }
    await expect(api.get('/x')).rejects.toBeTruthy()
    expect(calls.map((c) => c.url)).toEqual(['/x', '/auth/refresh', '/x'])
  })

  it('signs out without calling refresh when there is no refresh token', async () => {
    const { api, tokenStore, UNAUTHORIZED_EVENT } = await load()
    tokenStore.set('only-access')
    const onEnd = vi.fn(); window.addEventListener(UNAUTHORIZED_EVENT, onEnd)
    handler = () => ({ status: 401 })
    await expect(api.get('/x')).rejects.toBeTruthy()
    expect(calls).toHaveLength(1); expect(onEnd).toHaveBeenCalledTimes(1)
    window.removeEventListener(UNAUTHORIZED_EVENT, onEnd)
  })

  it('does not treat a wrong password (401 on login) as an expired session', async () => {
    const { api, tokenStore, UNAUTHORIZED_EVENT } = await load()
    tokenStore.set('a', 'r')
    const onEnd = vi.fn(); window.addEventListener(UNAUTHORIZED_EVENT, onEnd)
    handler = () => ({ status: 401 })
    await expect(api.post('/auth/login', {})).rejects.toBeTruthy()
    expect(calls).toHaveLength(1); expect(onEnd).not.toHaveBeenCalled(); expect(tokenStore.get()).toBe('a')
    window.removeEventListener(UNAUTHORIZED_EVENT, onEnd)
  })

  it('attaches the bearer token to requests', async () => {
    const { api, tokenStore } = await load()
    tokenStore.set('tok', 'r')
    handler = () => ({ status: 200 })
    await api.get('/auth/me')
    expect(calls[0].auth).toBe('Bearer tok')
  })
})
