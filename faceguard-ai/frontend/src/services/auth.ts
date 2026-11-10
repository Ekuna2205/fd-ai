import { api } from './api'
import { tokenStore } from '@/utils/tokenStore'
import type { AuthResponse, AuthUser, ChangePasswordPayload, LoginPayload, RegisterPayload } from '@/types/auth'

export const login = (p: LoginPayload) => api.post<AuthResponse>('/auth/login', p).then((r) => r.data)
export const register = (p: RegisterPayload) => api.post<AuthResponse>('/auth/register', p).then((r) => r.data)
export const getMe = () => api.get<AuthUser>('/auth/me').then((r) => r.data)
export const updateMe = (full_name: string) => api.patch<AuthUser>('/auth/me', { full_name }).then((r) => r.data)
export const changePassword = (p: ChangePasswordPayload) => api.post<AuthResponse>('/auth/change-password', p).then((r) => r.data)
export const logout = () => api.post('/auth/logout', { refresh_token: tokenStore.getRefresh() }).then(() => undefined)
export const resetStatus = () => api.get<{ email_reset_available: boolean }>('/auth/password-reset/status').then((r) => r.data)
export const forgotPassword = (email: string) => api.post<{ detail: string }>('/auth/forgot-password', { email }).then((r) => r.data)
export const resetPassword = (token: string, new_password: string) =>
  api.post<{ detail: string }>('/auth/reset-password', { token, new_password }).then((r) => r.data)
