import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as svc from '@/services/datasets'
import { renderWithProviders } from '@/test/utils'
import DatasetsPage from './DatasetsPage'

vi.mock('@/services/datasets', () => ({ listDatasets: vi.fn(), createDataset: vi.fn(), deleteDataset: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const ds = (id: string, name: string, images = 3) => ({ id, name, description: '', created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-02T00:00:00Z', images, real: 2, fake: 1, unlabeled: 0 })

beforeEach(() => {
  vi.mocked(svc.listDatasets).mockReset().mockResolvedValue([ds('d1', 'faces-v1'), ds('d2', 'attacks-v2', 9)])
  vi.mocked(svc.createDataset).mockReset().mockResolvedValue(ds('d3', 'new') as never)
  vi.mocked(svc.deleteDataset).mockReset().mockResolvedValue(undefined)
})

describe('DatasetsPage', () => {
  it('lists datasets with their real counts and links to details', async () => {
    renderWithProviders(<DatasetsPage />)
    const link = await screen.findByRole('link', { name: 'faces-v1' })
    expect(link).toHaveAttribute('href', '/datasets/d1')
    expect(screen.getByText('9')).toBeInTheDocument()
  })

  it('shows an empty state when there are no datasets', async () => {
    vi.mocked(svc.listDatasets).mockResolvedValue([])
    renderWithProviders(<DatasetsPage />)
    expect(await screen.findByText('No datasets yet')).toBeInTheDocument()
  })

  it('requires a name, then creates with trimmed input', async () => {
    renderWithProviders(<DatasetsPage />)
    await screen.findByText('faces-v1')
    await userEvent.click(screen.getByRole('button', { name: /Create/ }))
    expect(await screen.findByText('Enter a name.')).toBeInTheDocument()
    expect(svc.createDataset).not.toHaveBeenCalled()
    await userEvent.type(screen.getByLabelText('New dataset name'), '  my set  ')
    await userEvent.click(screen.getByRole('button', { name: /Create/ }))
    await waitFor(() => expect(svc.createDataset).toHaveBeenCalledWith('my set', ''))
  })

  it('shows the server error when the name is taken', async () => {
    vi.mocked(svc.createDataset).mockRejectedValue(new Error('A dataset with this name already exists.'))
    renderWithProviders(<DatasetsPage />)
    await userEvent.type(await screen.findByLabelText('New dataset name'), 'faces-v1')
    await userEvent.click(screen.getByRole('button', { name: /Create/ }))
    expect(await screen.findByText('A dataset with this name already exists.')).toBeInTheDocument()
  })

  it('filters by search text', async () => {
    renderWithProviders(<DatasetsPage />)
    await screen.findByText('faces-v1')
    await userEvent.type(screen.getByLabelText('Search datasets'), 'attack')
    expect(screen.queryByText('faces-v1')).toBeNull()
    expect(screen.getByText('attacks-v2')).toBeInTheDocument()
  })

  it('deletes only after confirmation, and the dialog states how many images go', async () => {
    renderWithProviders(<DatasetsPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Delete dataset attacks-v2' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/its 9 images/)).toBeInTheDocument()
    expect(svc.deleteDataset).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(svc.deleteDataset).toHaveBeenCalled())
    expect(vi.mocked(svc.deleteDataset).mock.calls[0][0]).toBe('d2')
  })
})
