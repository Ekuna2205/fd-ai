import type { Role } from '@/types/auth'

/** Matches backend: viewers are read-only and cannot submit biometric samples. */
export const canVerify = (role: Role | undefined) => role === 'administrator' || role === 'researcher' || role === 'operator'
