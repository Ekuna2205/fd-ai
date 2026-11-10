import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as svc from '@/services/history'
import { renderWithProviders } from '@/test/utils'
import HistoryPage from './HistoryPage'

vi.mock('@/services/history', () => ({ listVerifications: vi.fn(), deleteVerification: vi.fn(), exportVerifications: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const row = (id: string, status: string) => ({ id, created_at: '2026-11-06T10:00:00Z', mode: 'LIVE', status, spoof_type: null, confidence: null, face_count: 1, processing_ms: 120 })
const page = (items: unknown[], total = items.length) => ({ items, total, page: 1, page_size: 20 })

beforeEach(() => { vi.mocked(svc.listVerifications).mockReset(); vi.mocked(svc.deleteVerification).mockReset() })

describe('HistoryPage', () => {
  it('lists my verifications with status and links to details', async () => {
    vi.mocked(svc.listVerifications).mockResolvedValue(page([row('a1', 'UNCERTAIN'), row('b2', 'NO_FACE')]) as never)
    renderWithProviders(<HistoryPage />)
    // status names also appear as filter options, so wait for the table itself first
    expect(await screen.findByText(/1–2 of 2/)).toBeInTheDocument()
    expect(screen.getAllByText('Uncertain').length).toBeGreaterThan(1)
    expect(screen.getAllByText('No face').length).toBeGreaterThan(1)
    expect(screen.getAllByRole('link').some((l) => l.getAttribute('href') === '/verifications/a1')).toBe(true)
    expect(screen.getByText(/1–2 of 2/)).toBeInTheDocument()
  })

  it('shows an honest empty state, and a different one when filters match nothing', async () => {
    vi.mocked(svc.listVerifications).mockResolvedValue(page([]) as never)
    renderWithProviders(<HistoryPage />)
    expect(await screen.findByText('No verifications yet')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'FAKE')
    expect(await screen.findByText('No verifications match these filters')).toBeInTheDocument()
  })

  it('sends filters and a debounced search to the API and resets to page 1', async () => {
    vi.mocked(svc.listVerifications).mockResolvedValue(page([row('a1', 'REAL')], 45) as never)
    renderWithProviders(<HistoryPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Next page' }))
    await waitFor(() => expect(vi.mocked(svc.listVerifications).mock.calls.at(-1)![0].page).toBe(2))
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'REAL')
    await waitFor(() => { const q = vi.mocked(svc.listVerifications).mock.calls.at(-1)![0]; expect(q.status).toBe('REAL'); expect(q.page).toBe(1) })
    await userEvent.type(screen.getByLabelText('Search'), 'abc')
    await waitFor(() => expect(vi.mocked(svc.listVerifications).mock.calls.at(-1)![0].q).toBe('abc'))
  })

  it('toggles sort direction on a column header', async () => {
    vi.mocked(svc.listVerifications).mockResolvedValue(page([row('a1', 'REAL')]) as never)
    renderWithProviders(<HistoryPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Status' }))
    await waitFor(() => expect(vi.mocked(svc.listVerifications).mock.calls.at(-1)![0]).toMatchObject({ sort: 'status', order: 'desc' }))
    await userEvent.click(screen.getByRole('button', { name: 'Status' }))
    await waitFor(() => expect(vi.mocked(svc.listVerifications).mock.calls.at(-1)![0]).toMatchObject({ sort: 'status', order: 'asc' }))
  })

  it('asks for confirmation before deleting and does nothing on cancel', async () => {
    vi.mocked(svc.listVerifications).mockResolvedValue(page([row('a1', 'REAL')]) as never)
    renderWithProviders(<HistoryPage />)
    await userEvent.click(await screen.findByRole('button', { name: /Delete verification/ }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Delete this verification?')).toBeInTheDocument()
    expect(svc.deleteVerification).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(svc.deleteVerification).not.toHaveBeenCalled()
  })

  it('deletes the record after confirming', async () => {
    vi.mocked(svc.listVerifications).mockResolvedValue(page([row('a1', 'REAL')]) as never)
    vi.mocked(svc.deleteVerification).mockResolvedValue(undefined)
    renderWithProviders(<HistoryPage />)
    await userEvent.click(await screen.findByRole('button', { name: /Delete verification/ }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(svc.deleteVerification).toHaveBeenCalled())
    expect(vi.mocked(svc.deleteVerification).mock.calls[0][0]).toBe('a1') // TanStack also passes a context argument
  })

  it('shows an error state with retry when the API fails', async () => {
    vi.mocked(svc.listVerifications).mockRejectedValue(new Error('The API is not reachable.'))
    renderWithProviders(<HistoryPage />)
    expect(await screen.findByText('History is unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})
