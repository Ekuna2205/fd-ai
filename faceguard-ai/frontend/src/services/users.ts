import { api } from './api'
import type { AuthUser, Role } from '@/types/auth'

export const listUsers = (limit = 200, offset = 0) =>
  api.get<{ items: AuthUser[]; total: number }>('/users', { params: { limit, offset } }).then((r) => r.data)
export const updateUser = (id: string, patch: { role?: Role; is_active?: boolean }) =>
  api.patch<AuthUser>(`/users/${id}`, patch).then((r) => r.data)

export interface ResetLink { path: string; expires_at: string; signed_out: boolean }
/** One-time password-reset link for another user (administrators only; works without SMTP). */
export const createResetLink = (id: string, signOut: boolean) =>
  api.post<ResetLink>(`/users/${id}/reset-link`, { sign_out: signOut }).then((r) => r.data)
