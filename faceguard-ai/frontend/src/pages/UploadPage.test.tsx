import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as face from '@/services/face'
import { renderWithProviders } from '@/test/utils'
import UploadPage from './UploadPage'

let role = 'operator'
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user: { role } }) }))
vi.mock('@/services/face', () => ({ getCapabilities: vi.fn(), uploadMedia: vi.fn() }))

const caps = { detector: { name: 'd', landmarks: true }, liveness: { available: false, reason: 'none', model: null }, consent_required: true,
  limits: { max_image_mb: 1, max_video_mb: 2, max_video_seconds: 30, image_types: ['.jpg', '.jpeg', '.png'], video_types: ['.mp4', '.webm'] } }
const verdict = { id: 'abc', created_at: '2026-11-06T10:00:00Z', mode: 'UPLOAD_IMAGE', status: 'UNCERTAIN', spoof_type: null, confidence: null,
  face_count: 1, quality: null, video: null, explanation: 'One face was detected.', model_version: null, processing_ms: 120,
  liveness: { available: false, reason: 'No model.', model: null }, score: null }

beforeEach(() => {
  role = 'operator'
  vi.mocked(face.getCapabilities).mockResolvedValue(caps as never)
  vi.mocked(face.uploadMedia).mockReset()
  URL.createObjectURL = vi.fn(() => 'blob:x'); URL.revokeObjectURL = vi.fn()
})

async function pick(file: File) {
  const input = await waitFor(() => { const el = document.querySelector('input[type=file]') as HTMLInputElement; expect(el).not.toBeDisabled(); return el })
  fireEvent.change(input, { target: { files: [file] } })
}

describe('UploadPage', () => {
  it('rejects unsupported types and oversized files before uploading', async () => {
    renderWithProviders(<UploadPage />)
    await pick(new File(['x'], 'malware.exe'))
    expect(await screen.findByText(/Unsupported file type/)).toBeInTheDocument()
    await pick(new File([new Uint8Array(2 * 1024 * 1024)], 'big.png'))
    expect(await screen.findByText(/File is too large. The limit is 1 MB/)).toBeInTheDocument()
    expect(face.uploadMedia).not.toHaveBeenCalled()
  })

  it('requires consent, uploads, and shows the result', async () => {
    vi.mocked(face.uploadMedia).mockResolvedValue(verdict as never)
    renderWithProviders(<UploadPage />)
    const file = new File(['abc'], 'me.jpg', { type: 'image/jpeg' })
    await pick(file)
    const analyse = await screen.findByRole('button', { name: 'Analyse' })
    expect(analyse).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(analyse)
    await waitFor(() => expect(face.uploadMedia).toHaveBeenCalledWith(file, 'image', expect.any(Function)))
    expect(await screen.findByText('One face was detected.')).toBeInTheDocument()
    expect(screen.getByText(/Liveness was not assessed/)).toBeInTheDocument()
  })

  it('treats .mp4 as video', async () => {
    vi.mocked(face.uploadMedia).mockResolvedValue({ ...verdict, mode: 'UPLOAD_VIDEO' } as never)
    renderWithProviders(<UploadPage />)
    await pick(new File(['v'], 'clip.mp4', { type: 'video/mp4' }))
    await userEvent.click(await screen.findByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Analyse' }))
    await waitFor(() => expect(face.uploadMedia).toHaveBeenCalledWith(expect.anything(), 'video', expect.any(Function)))
  })

  it('shows the server error when analysis fails', async () => {
    vi.mocked(face.uploadMedia).mockRejectedValue(new Error('The image is corrupted or cannot be read.'))
    renderWithProviders(<UploadPage />)
    await pick(new File(['abc'], 'me.png'))
    await userEvent.click(await screen.findByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Analyse' }))
    expect(await screen.findByText(/corrupted or cannot be read/)).toBeInTheDocument()
  })

  it('is read-only for viewers', () => {
    role = 'viewer'
    renderWithProviders(<UploadPage />)
    expect(screen.getByText(/Your role is read-only/)).toBeInTheDocument()
    expect(document.querySelector('input[type=file]')).toBeNull()
  })
})
