import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as svc from '@/services/models'
import { renderWithProviders } from '@/test/utils'
import ModelsPage from './ModelsPage'

let role = 'researcher'
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user: { role } }) }))
vi.mock('@/services/models', () => ({ listModels: vi.fn(), getModel: vi.fn(), activateModel: vi.fn(), deactivateModel: vi.fn(), registerModel: vi.fn(), deleteModel: vi.fn() }))
vi.mock('@/services/datasets', () => ({ listDatasets: vi.fn().mockResolvedValue([{ id: 'd1', name: 'faces-v1', images: 10 }]), getValidation: vi.fn().mockResolvedValue({ ready: false, problems: ['Only 2 identities.'], warnings: [], stats: {} }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const ev = { id: 'e1', evaluated_at: '2026-11-01T00:00:00Z', sample_count: 500, threshold: 0.5, accuracy: 0.97, precision: 0.96, recall: 0.95, f1: 0.95, roc_auc: 0.99, apcer: 0.04, bpcer: 0.03, acer: 0.035, identity_disjoint: true }
const model = (over = {}) => ({ id: 'm1', name: 'cnn', version: '1', architecture: 'SmallCNN', description: null, is_trained: true, is_active: false, trained_at: '2026-10-30T00:00:00Z', created_at: '2026-10-30T00:00:00Z', has_onnx: true, input_crop: 'face', latest_evaluation: ev, blockers: [], ...over })

beforeEach(() => { role = 'researcher'; vi.mocked(svc.listModels).mockReset(); vi.mocked(svc.activateModel).mockReset().mockResolvedValue(model({ is_active: true }) as never) })

describe('ModelsPage', () => {
  it('says plainly when there are no models and that none is in use', async () => {
    vi.mocked(svc.listModels).mockResolvedValue([])
    renderWithProviders(<ModelsPage />)
    expect(await screen.findByText('No models registered')).toBeInTheDocument()
    expect(screen.getByText('No model is active.')).toBeInTheDocument()
  })

  it('never shows metrics for a model that was not evaluated, and blocks activation with reasons', async () => {
    vi.mocked(svc.listModels).mockResolvedValue([model({ is_trained: false, has_onnx: false, latest_evaluation: null, blockers: ['The model is not trained (baseline weights are never production-ready).', 'The model has not been evaluated.'] })] as never)
    renderWithProviders(<ModelsPage />)
    expect(await screen.findByText('Untrained baseline')).toBeInTheDocument()
    expect(screen.getByText(/No metrics are shown because none were measured/)).toBeInTheDocument()
    expect(screen.getByText('Cannot be activated yet')).toBeInTheDocument()
    expect(screen.getByText(/not trained/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Activate' })).toBeDisabled()
  })

  it('shows PAD metrics and activates a model that has evidence', async () => {
    vi.mocked(svc.listModels).mockResolvedValue([model()] as never)
    renderWithProviders(<ModelsPage />)
    expect(await screen.findByText('ACER')).toBeInTheDocument()
    expect(screen.getByText('3.5%')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Activate' }))
    await waitFor(() => expect(svc.activateModel).toHaveBeenCalled())
    expect(vi.mocked(svc.activateModel).mock.calls[0][0]).toBe('m1')
  })

  it('hides activation and the training guide from read-only roles', async () => {
    role = 'viewer'
    vi.mocked(svc.listModels).mockResolvedValue([model()] as never)
    renderWithProviders(<ModelsPage />)
    await screen.findByText('ACER')
    expect(screen.queryByRole('button', { name: 'Activate' })).toBeNull()
    expect(screen.queryByText('Training')).toBeNull()
  })

  it('builds a training command and states that nothing trains from the page', async () => {
    vi.mocked(svc.listModels).mockResolvedValue([])
    renderWithProviders(<ModelsPage />)
    expect(await screen.findByText(/records no training jobs and shows no progress/)).toBeInTheDocument()
    await userEvent.selectOptions(await screen.findByLabelText('Dataset'), 'd1')
    expect(await screen.findByText('Only 2 identities.')).toBeInTheDocument()
    expect(screen.getByText(/python -m faceguard_ai.train --config config.json/)).toBeInTheDocument()
    expect(screen.getByText(/scripts\/register_model.py --run-dir .* --crop face/)).toBeInTheDocument()
    expect(screen.getByText(/Export face crops/)).toBeInTheDocument()
  })

  it('names the active model that decides liveness', async () => {
    vi.mocked(svc.listModels).mockResolvedValue([model({ is_active: true })] as never)
    renderWithProviders(<ModelsPage />)
    expect(await screen.findByText('cnn v1 decides liveness.')).toBeInTheDocument()
    expect(screen.getByText('Input: face crop')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Delete model/ })).toBeNull() // active models cannot be deleted
  })

  it('registers a model from the three run files', async () => {
    vi.mocked(svc.listModels).mockResolvedValue([])
    vi.mocked(svc.registerModel).mockReset().mockResolvedValue(model() as never)
    renderWithProviders(<ModelsPage />)
    const submit = await screen.findByRole('button', { name: 'Register model' })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Name'), 'smallcnn')
    const f = (name: string) => new File(['x'], name)
    await userEvent.upload(screen.getByLabelText('model.onnx'), f('model.onnx'))
    await userEvent.upload(screen.getByLabelText('test_metrics.json'), f('test_metrics.json'))
    await userEvent.upload(screen.getByLabelText('split_report.json'), f('split_report.json'))
    await userEvent.click(submit)
    await waitFor(() => expect(svc.registerModel).toHaveBeenCalled())
    const arg = vi.mocked(svc.registerModel).mock.calls[0][0]
    expect(arg.name).toBe('smallcnn')
    expect(arg.input_crop).toBe('face')
    expect(arg.onnx.name).toBe('model.onnx')
  })

  it('confirms before deleting an inactive model', async () => {
    vi.mocked(svc.listModels).mockResolvedValue([model()] as never)
    vi.mocked(svc.deleteModel).mockReset().mockResolvedValue(undefined)
    renderWithProviders(<ModelsPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Delete model cnn v1' }))
    expect(svc.deleteModel).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(svc.deleteModel).toHaveBeenCalledWith('m1'))
  })
})
