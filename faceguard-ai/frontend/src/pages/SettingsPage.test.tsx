import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as auth from '@/services/auth'
import { renderWithProviders } from '@/test/utils'
import SettingsPage from './SettingsPage'

const accept = vi.fn(); const setUser = vi.fn()
const user = { id: 'me', email: 'ada@example.com', full_name: 'Ada Lovelace', role: 'operator', is_active: true, created_at: '2026-11-01T00:00:00Z', last_login_at: null }
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user, accept, setUser, logout: vi.fn() }) }))
vi.mock('@/services/auth', () => ({ changePassword: vi.fn(), updateMe: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

beforeEach(() => { accept.mockReset(); setUser.mockReset(); vi.mocked(auth.changePassword).mockReset(); vi.mocked(auth.updateMe).mockReset() })

describe('SettingsPage', () => {
  it('shows account facts and keeps email and role read-only', () => {
    renderWithProviders(<SettingsPage />)
    expect(screen.getByLabelText('Email')).toBeDisabled()
    expect(screen.getByText('Operator')).toBeInTheDocument()
  })

  it('updates the display name', async () => {
    vi.mocked(auth.updateMe).mockResolvedValue({ ...user, full_name: 'Ada King' } as never)
    renderWithProviders(<SettingsPage />)
    const name = screen.getByLabelText('Full name')
    await userEvent.clear(name); await userEvent.type(name, 'Ada King')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(auth.updateMe).toHaveBeenCalledWith('Ada King'))
    expect(setUser).toHaveBeenCalled()
  })

  it('validates the new password before calling the API', async () => {
    renderWithProviders(<SettingsPage />)
    await userEvent.type(screen.getByLabelText('Current password'), 'Old-password-1')
    await userEvent.type(screen.getByLabelText('New password'), 'short')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'different')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Password does not meet the requirements.')).toBeInTheDocument()
    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument()
    expect(auth.changePassword).not.toHaveBeenCalled()
  })

  it('rejects reusing the current password', async () => {
    renderWithProviders(<SettingsPage />)
    for (const l of ['Current password', 'New password', 'Confirm new password']) await userEvent.type(screen.getByLabelText(l), 'Same-password-1')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText(/different from the current one/)).toBeInTheDocument()
    expect(auth.changePassword).not.toHaveBeenCalled()
  })

  it('changes the password and adopts the fresh tokens', async () => {
    const fresh = { access_token: 'a', refresh_token: 'r', user }
    vi.mocked(auth.changePassword).mockResolvedValue(fresh as never)
    renderWithProviders(<SettingsPage />)
    await userEvent.type(screen.getByLabelText('Current password'), 'Old-password-1')
    await userEvent.type(screen.getByLabelText('New password'), 'Brand-new-pass-2')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'Brand-new-pass-2')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    await waitFor(() => expect(auth.changePassword).toHaveBeenCalledWith({ current_password: 'Old-password-1', new_password: 'Brand-new-pass-2' }))
    expect(accept).toHaveBeenCalledWith(fresh)
  })

  it('shows the server error for a wrong current password', async () => {
    vi.mocked(auth.changePassword).mockRejectedValue(new Error('Current password is incorrect.'))
    renderWithProviders(<SettingsPage />)
    await userEvent.type(screen.getByLabelText('Current password'), 'Wrong-password-1')
    await userEvent.type(screen.getByLabelText('New password'), 'Brand-new-pass-2')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'Brand-new-pass-2')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Current password is incorrect.')
    expect(accept).not.toHaveBeenCalled()
  })

  it('switches the theme and remembers it', async () => {
    renderWithProviders(<SettingsPage />)
    await userEvent.click(screen.getByRole('radio', { name: /Light/ }))
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('faceguard.theme')).toBe('light')
  })
})
