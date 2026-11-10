import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '@/test/utils'
import ChallengePage from './ChallengePage'

let role = 'operator'
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ user: { role } }) }))
vi.mock('@/services/challenge', () => ({ newChallenge: vi.fn(), submitChallenge: vi.fn() }))

beforeEach(() => { role = 'operator' })

describe('ChallengePage', () => {
  it('states up front that a passed challenge is not proof of a live person', () => {
    renderWithProviders(<ChallengePage />)
    expect(screen.getByRole('note')).toHaveTextContent(/supporting evidence only/i)
    expect(screen.getByRole('note')).toHaveTextContent(/never marks a person as real/i)
  })

  it('does not reach the camera until the user consents', async () => {
    renderWithProviders(<ChallengePage />)
    expect(screen.queryByRole('button', { name: /Start camera/ })).toBeNull()
    const go = screen.getByRole('button', { name: 'Continue to camera' })
    expect(go).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(go)
    expect(await screen.findByRole('button', { name: /Start camera/ })).toBeInTheDocument()
    expect(screen.getByText('Request one to begin')).toBeInTheDocument()
  })

  it('is read-only for viewers', () => {
    role = 'viewer'
    renderWithProviders(<ChallengePage />)
    expect(screen.getByText(/Your role is read-only/)).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })
})
