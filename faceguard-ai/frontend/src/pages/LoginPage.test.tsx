import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/utils'
import LoginPage from './LoginPage'

const login = vi.fn()
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ login }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

describe('LoginPage', () => {
  it('validates fields before calling the API', async () => {
    renderWithProviders(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('submits credentials and surfaces the server error', async () => {
    login.mockRejectedValueOnce(new Error('Incorrect email or password.'))
    renderWithProviders(<LoginPage />)
    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Wrong-pass-1')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(login).toHaveBeenCalledWith({ email: 'ada@example.com', password: 'Wrong-pass-1' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
  })
})
