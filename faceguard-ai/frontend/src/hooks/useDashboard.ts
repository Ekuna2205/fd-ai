import { useQuery } from '@tanstack/react-query'
import { getHealth, getOverview } from '@/services/dashboard'

export const useOverview = () =>
  useQuery({ queryKey: ['dashboard', 'overview'], queryFn: getOverview, retry: false, refetchInterval: 30_000 })

export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false, refetchInterval: 15_000 })
