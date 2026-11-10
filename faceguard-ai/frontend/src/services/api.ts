import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getLang, translate, translateServer } from '@/i18n'
import { tokenStore } from '@/utils/tokenStore'

export const UNAUTHORIZED_EVENT = 'faceguard:unauthorized'
const BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api`

export const api = axios.create({ baseURL: BASE, timeout: 15_000 })
// A bare client for /auth/refresh so the refresh call itself never triggers the refresh logic (no loops).
const bare = axios.create({ baseURL: BASE, timeout: 15_000 })

api.interceptors.request.use((config) => {
  config.headers['Accept-Language'] = getLang() // the API writes its messages (explanations, errors) in this language
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let inflight: Promise<string> | null = null

/** One refresh at a time: concurrent 401s wait for the same rotation (refresh tokens are single-use). */
function refreshSession(): Promise<string> {
  inflight ??= (async () => {
    const refresh = tokenStore.getRefresh()
    if (!refresh) throw new Error('no refresh token')
    const { data } = await bare.post('/auth/refresh', { refresh_token: refresh })
    tokenStore.set(data.access_token, data.refresh_token)
    return data.access_token as string
  })().finally(() => { inflight = null })
  return inflight
}

type Retriable = InternalAxiosRequestConfig & { _retried?: boolean }
const isCredentialCall = (url = '') => /^\/auth\/(login|register|refresh|forgot-password|reset-password)/.test(url)

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as Retriable | undefined
    if (error.response?.status !== 401 || !original || !tokenStore.get() || isCredentialCall(original.url)) throw error
    if (!original._retried && tokenStore.getRefresh()) {
      original._retried = true
      try {
        const access = await refreshSession()
        original.headers.Authorization = `Bearer ${access}`
        return api.request(original)
      } catch { /* fall through: the session is really over */ }
    }
    tokenStore.clear()
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw error
  },
)

export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return translate('The API is not reachable.')
    const detail = err.response.data?.detail
    return typeof detail === 'string' ? translateServer(detail) : translate('Request failed ({status}).', { status: err.response.status })
  }
  return err instanceof Error ? translateServer(err.message) : translate('Unexpected error.')
}

/** Field-level messages from a 422 response: { email: '...', password: '...' } */
export function fieldErrors(err: unknown): Record<string, string> {
  if (!axios.isAxiosError(err) || err.response?.status !== 422) return {}
  const list = err.response.data?.errors
  if (!Array.isArray(list)) return {}
  const out: Record<string, string> = {}
  for (const e of list) if (e?.field && !out[e.field]) out[e.field] = translateServer(String(e.message))
  return out
}
