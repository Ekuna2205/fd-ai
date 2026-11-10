import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as svc from '@/services/history'
import { renderWithProviders } from '@/test/utils'
import ReportsPage from './ReportsPage'

let role = 'operator'
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user: { role } }) }))
vi.mock('@/services/history', () => ({ getReport: vi.fn(), exportReport: vi.fn() }))
vi.mock('@/components/charts/SeriesChart', () => ({ SeriesChart: () => <div data-testid="series-chart" /> }))
vi.mock('@/components/charts/DistributionChart', () => ({ DistributionChart: () => <div data-testid="dist-chart" /> }))
vi.mock('@/components/charts/CategoryChart', () => ({ CategoryChart: () => <div data-testid="cat-chart" /> }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const base = { scope: 'own', period: 'day', days: 30, status_distribution: [], avg_processing_ms: null }
const empty = { ...base, totals: { attempts: 0, real: 0, fake: 0, uncertain: 0, failed: 0, success_rate: null }, series: [], spoof_categories: [] }
const full = { ...base, avg_processing_ms: 250, totals: { attempts: 4, real: 1, fake: 1, uncertain: 2, failed: 0, success_rate: 0.25 },
  series: [{ bucket: '2026-11-06', real: 1, fake: 1, uncertain: 2, failed: 0 }], spoof_categories: [{ category: 'PHONE_SCREEN', count: 1 }] }

beforeEach(() => { role = 'operator'; vi.mocked(svc.getReport).mockReset(); vi.mocked(svc.exportReport).mockReset().mockResolvedValue(undefined) })

describe('ReportsPage', () => {
  it('shows empty states and no export when there is no data', async () => {
    vi.mocked(svc.getReport).mockResolvedValue(empty as never)
    renderWithProviders(<ReportsPage />)
    expect(await screen.findByText('No verifications in this period')).toBeInTheDocument()
    expect(screen.queryByTestId('series-chart')).toBeNull()
    expect(screen.getByRole('button', { name: /Export CSV/ })).toBeDisabled()
  })

  it('renders figures from the API and exports', async () => {
    vi.mocked(svc.getReport).mockResolvedValue(full as never)
    renderWithProviders(<ReportsPage />)
    expect(await screen.findByTestId('series-chart')).toBeInTheDocument()
    expect(screen.getByText('25.0%')).toBeInTheDocument()
    expect(screen.getByTestId('cat-chart')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Export CSV/ }))
    await waitFor(() => expect(svc.exportReport).toHaveBeenCalledWith('day', 30, 'own'))
  })

  it('re-queries when the period changes', async () => {
    vi.mocked(svc.getReport).mockResolvedValue(full as never)
    renderWithProviders(<ReportsPage />)
    await screen.findByTestId('series-chart')
    await userEvent.selectOptions(screen.getByLabelText('Group by'), 'week')
    await waitFor(() => expect(vi.mocked(svc.getReport).mock.calls.at(-1)).toEqual(['week', 30, 'own']))
  })

  it('offers the all-users aggregate to administrators only', async () => {
    vi.mocked(svc.getReport).mockResolvedValue(full as never)
    const { unmount } = renderWithProviders(<ReportsPage />)
    await screen.findByTestId('series-chart')
    expect(screen.queryByLabelText('Scope')).toBeNull()
    unmount(); role = 'administrator'
    renderWithProviders(<ReportsPage />)
    await userEvent.selectOptions(await screen.findByLabelText('Scope'), 'all')
    await waitFor(() => expect(vi.mocked(svc.getReport).mock.calls.at(-1)![2]).toBe('all'))
  })

  it('shows the API error with a retry button', async () => {
    vi.mocked(svc.getReport).mockRejectedValue(new Error('boom'))
    renderWithProviders(<ReportsPage />)
    expect(await screen.findByText('Report unavailable')).toBeInTheDocument()
  })
})
