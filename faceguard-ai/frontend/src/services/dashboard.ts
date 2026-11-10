import { api } from './api'
import type { DashboardOverview, HealthStatus } from '@/types/dashboard'

export const getOverview = () => api.get<DashboardOverview>('/dashboard/overview').then((r) => r.data)
export const getHealth = () => api.get<HealthStatus>('/health').then((r) => r.data)
