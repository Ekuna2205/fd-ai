import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as auth from '@/services/auth'
import { renderWithProviders } from '@/test/utils'
import ResetPasswordPage from './ResetPasswordPage'

vi.mock('@/services/auth', () => ({ resetPassword: vi.fn() }))
beforeEach(() => { vi.mocked(auth.resetPassword).mockReset() }) // braces: a returned function would run as teardown

describe('ResetPasswordPage', () => {
  it('rejects a link without a token', () => {
    renderWithProviders(<ResetPasswordPage />, '/reset-password')
    expect(screen.getByRole('alert')).toHaveTextContent(/incomplete/)
  })

  it('validates the new password, then sends the token from the link', async () => {
    vi.mocked(auth.resetPassword).mockResolvedValue({ detail: 'ok' })
    renderWithProviders(<ResetPasswordPage />, '/reset-password?token=abc123')
    await userEvent.type(screen.getByLabelText('New password'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Password does not meet the requirements.')).toBeInTheDocument()
    expect(auth.resetPassword).not.toHaveBeenCalled()
    await userEvent.clear(screen.getByLabelText('New password'))
    await userEvent.type(screen.getByLabelText('New password'), 'Brand-new-pass-2')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'Brand-new-pass-2')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    await waitFor(() => expect(auth.resetPassword).toHaveBeenCalledWith('abc123', 'Brand-new-pass-2'))
    expect(await screen.findByText('Your password has been changed.')).toBeInTheDocument()
  })

  it('shows the server error for an expired or used link', async () => {
    vi.mocked(auth.resetPassword).mockRejectedValue(new Error('This reset link is invalid or has expired.'))
    renderWithProviders(<ResetPasswordPage />, '/reset-password?token=old')
    await userEvent.type(screen.getByLabelText('New password'), 'Brand-new-pass-2')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'Brand-new-pass-2')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or has expired/)
  })
})
