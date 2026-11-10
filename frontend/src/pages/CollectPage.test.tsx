import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as svc from '@/services/collect'
import { renderWithProviders } from '@/test/utils'
import CollectPage from './CollectPage'

vi.mock('@/services/collect', () => ({ getCollectInfo: vi.fn(), sendCollectFrame: vi.fn(), submitCollect: vi.fn(), setCollection: vi.fn() }))

const page = () => renderWithProviders(<Routes><Route path="/collect/:token" element={<CollectPage />} /></Routes>, '/collect/tok')

describe('CollectPage', () => {
  beforeEach(() => {
    localStorage.setItem('faceguard.lang', 'en')
    vi.mocked(svc.getCollectInfo).mockResolvedValue({ name: 'Set A', description: '', step_seconds: 6, max_video_mb: 50,
      attack_types: ['PRINTED_PHOTO', 'PHONE_SCREEN'] })
  })

  it('needs a label (and an attack type for fake) before continuing, then asks for consent', async () => {
    page()
    const next = await screen.findByRole('button', { name: 'Continue' })
    expect(next).toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: /Fake/ }))
    expect(next).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Phone screen' }))
    expect(next).toBeEnabled()
    await userEvent.click(next)
    const start = screen.getByRole('button', { name: 'Start' })
    expect(start).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox'))
    expect(start).toBeEnabled()
  })

  it('explains an invalid link', async () => {
    vi.mocked(svc.getCollectInfo).mockRejectedValue(new Error('404'))
    page()
    expect(await screen.findByText('This collection link is not valid or has been turned off.')).toBeInTheDocument()
  })
})
