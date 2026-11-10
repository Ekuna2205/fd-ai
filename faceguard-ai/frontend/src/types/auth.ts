export type Role = 'administrator' | 'researcher' | 'operator' | 'viewer'

/** Mirrors backend schemas/auth.py::UserOut */
export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

/** Mirrors backend schemas/auth.py::AuthResponse */
export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  refresh_token: string
  refresh_expires_in: number
  user: AuthUser
}

export interface RegisterPayload { email: string; full_name: string; password: string }
export interface LoginPayload { email: string; password: string }
export interface ChangePasswordPayload { current_password: string; new_password: string }
