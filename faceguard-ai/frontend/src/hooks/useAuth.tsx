import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { UNAUTHORIZED_EVENT } from '@/services/api'
import * as authApi from '@/services/auth'
import type { AuthResponse, AuthUser, LoginPayload, RegisterPayload } from '@/types/auth'
import { tokenStore } from '@/utils/tokenStore'
import { translate } from '@/i18n'

type Status = 'loading' | 'authenticated' | 'anonymous'

interface AuthContextValue {
  user: AuthUser | null
  status: Status
  login: (p: LoginPayload) => Promise<AuthUser>
  register: (p: RegisterPayload) => Promise<AuthUser>
  /** Applies a fresh token pair (e.g. after a password change) and/or an updated profile. */
  accept: (res: AuthResponse) => AuthUser
  setUser: (u: AuthUser) => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] = useState<Status>(() => (tokenStore.get() ? 'loading' : 'anonymous'))

  // Restore the session after a page reload.
  useEffect(() => {
    if (!tokenStore.get()) return
    let cancelled = false
    authApi.getMe().then(
      (u) => { if (!cancelled) { setUser(u); setStatus('authenticated') } },
      () => { if (!cancelled) { tokenStore.clear(); setUser(null); setStatus('anonymous') } },
    )
    return () => { cancelled = true }
  }, [])

  // The API client fires this when any request comes back 401 (expired or revoked token).
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null); setStatus('anonymous'); queryClient.clear()
      toast.error(translate('Your session has ended. Sign in again.'))
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [queryClient])

  const accept = useCallback((res: AuthResponse) => {
    queryClient.clear() // never show a previous account's cached verifications/dashboard to the new one
    tokenStore.set(res.access_token, res.refresh_token)
    queryClient.clear() // never show the previous session's cached data to a new one
    setUser(res.user); setStatus('authenticated')
    return res.user
  }, [queryClient])

  const value = useMemo<AuthContextValue>(() => ({
    user, status, accept, setUser,
    login: async (p) => accept(await authApi.login(p)),
    register: async (p) => accept(await authApi.register(p)),
    logout: async () => {
      try { await authApi.logout() } catch { /* the token is dropped locally either way */ }
      tokenStore.clear(); setUser(null); setStatus('anonymous'); queryClient.clear()
    },
  }), [user, status, accept, queryClient])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
