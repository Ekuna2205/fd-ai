import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as auth from '@/services/auth'
import { renderWithProviders } from '@/test/utils'
import ForgotPasswordPage from './ForgotPasswordPage'

vi.mock('@/services/auth', () => ({ resetStatus: vi.fn(), forgotPassword: vi.fn() }))

beforeEach(() => { vi.mocked(auth.resetStatus).mockReset(); vi.mocked(auth.forgotPassword).mockReset() })

describe('ForgotPasswordPage', () => {
  it('tells the truth when the server cannot send e-mail, and offers no form', async () => {
    vi.mocked(auth.resetStatus).mockResolvedValue({ email_reset_available: false })
    renderWithProviders(<ForgotPasswordPage />)
    expect(await screen.findByText(/not set up on this server/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send reset link' })).toBeNull()
  })

  it('validates the address, then shows the neutral confirmation from the server', async () => {
    vi.mocked(auth.resetStatus).mockResolvedValue({ email_reset_available: true })
    vi.mocked(auth.forgotPassword).mockResolvedValue({ detail: 'If that address has an account, a reset link is on its way.' })
    renderWithProviders(<ForgotPasswordPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Send reset link' }))
    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(auth.forgotPassword).not.toHaveBeenCalled()
    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }))
    await waitFor(() => expect(auth.forgotPassword).toHaveBeenCalledWith('ada@example.com'))
    expect(await screen.findByText(/a reset link is on its way/)).toBeInTheDocument()
  })
})
