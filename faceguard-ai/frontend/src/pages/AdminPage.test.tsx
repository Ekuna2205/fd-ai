import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as users from '@/services/users'
import { renderWithProviders } from '@/test/utils'
import type { AuthUser } from '@/types/auth'
import AdminPage from './AdminPage'

vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user: { id: 'me', role: 'administrator' } }) }))
vi.mock('@/services/users', () => ({ listUsers: vi.fn(), updateUser: vi.fn(), createResetLink: vi.fn() }))
vi.mock('@/services/history', () => ({ listAudit: vi.fn().mockResolvedValue({ items: [{ id: '1', created_at: '2026-11-06T10:00:00Z', action: 'auth.login', user_email: 'ada@example.com', ip_address: '10.0.0.1', entity_type: null, entity_id: null, details: null }], total: 1, page: 1, page_size: 25 }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const u = (id: string, email: string, role = 'viewer', active = true) => ({ id, email, full_name: email.split('@')[0], role, is_active: active, created_at: '2026-11-01T00:00:00Z', last_login_at: null }) as AuthUser

beforeEach(() => {
  vi.mocked(users.listUsers).mockResolvedValue({ items: [u('me', 'me@example.com', 'administrator'), u('u2', 'bob@example.com')], total: 2 })
  vi.mocked(users.updateUser).mockReset().mockResolvedValue(u('u2', 'bob@example.com', 'operator'))
})

describe('AdminPage', () => {
  it('stops administrators from changing their own role or status', async () => {
    renderWithProviders(<AdminPage />)
    expect(await screen.findByLabelText('Role for me@example.com')).toBeDisabled()
    expect(screen.getByLabelText('Role for bob@example.com')).toBeEnabled()
    const mineRow = screen.getByText('me@example.com').closest('tr')!
    expect(within(mineRow).getByRole('button', { name: /disable/i })).toBeDisabled()
  })

  it('changes another user’s role through the API', async () => {
    renderWithProviders(<AdminPage />)
    await userEvent.selectOptions(await screen.findByLabelText('Role for bob@example.com'), 'operator')
    await waitFor(() => expect(users.updateUser).toHaveBeenCalled())
    expect(vi.mocked(users.updateUser).mock.calls[0].slice(0, 2)).toEqual(['u2', { role: 'operator' }])
  })

  it('confirms before disabling an account, then disables it', async () => {
    renderWithProviders(<AdminPage />)
    const row = (await screen.findByText('bob@example.com')).closest('tr')!
    await userEvent.click(within(row).getByRole('button', { name: /disable/i }))
    const dialog = await screen.findByRole('dialog')
    expect(users.updateUser).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Disable' }))
    await waitFor(() => expect(users.updateUser).toHaveBeenCalled())
    expect(vi.mocked(users.updateUser).mock.calls[0].slice(0, 2)).toEqual(['u2', { is_active: false }])
  })

  it('filters users by search text', async () => {
    renderWithProviders(<AdminPage />)
    await screen.findByText('bob@example.com')
    await userEvent.type(screen.getByLabelText('Search users'), 'nobody')
    expect(await screen.findByText('No users match')).toBeInTheDocument()
  })

  it('shows the audit log tab', async () => {
    renderWithProviders(<AdminPage />)
    await userEvent.click(screen.getByRole('tab', { name: 'Audit log' }))
    expect(await screen.findByText('auth.login')).toBeInTheDocument()
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
  })

  it('creates a one-time reset link for another user and shows it once', async () => {
    vi.mocked(users.createResetLink).mockReset().mockResolvedValue({ path: '/reset-password?token=abc123', expires_at: '2026-11-09T12:00:00Z', signed_out: true })
    renderWithProviders(<AdminPage />)
    expect(screen.queryByRole('button', { name: 'Reset link for me@example.com' })).toBeNull() // not for yourself
    await userEvent.click(await screen.findByRole('button', { name: 'Reset link for bob@example.com' }))
    await userEvent.click(screen.getByLabelText(/sign them out/))
    await userEvent.click(screen.getByRole('button', { name: 'Create link' }))
    await waitFor(() => expect(users.createResetLink).toHaveBeenCalledWith('u2', true))
    expect(await screen.findByLabelText('Reset link')).toHaveValue(`${window.location.origin}/reset-password?token=abc123`)
    expect(screen.getByText(/will not be shown again/)).toBeInTheDocument()
  })
})
