import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'

const state: { status: string; user: { role: string } | null } = { status: 'anonymous', user: null }
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => state }))

const app = (roles?: ('administrator' | 'viewer')[]) => (
  <MemoryRouter initialEntries={['/secret']}>
    <Routes>
      <Route path="/login" element={<p>login page</p>} />
      <Route path="/" element={<p>home</p>} />
      <Route element={<ProtectedRoute roles={roles} />}><Route path="/secret" element={<p>secret</p>} /></Route>
    </Routes>
  </MemoryRouter>
)

describe('ProtectedRoute', () => {
  it('sends anonymous users to the login page', () => {
    Object.assign(state, { status: 'anonymous', user: null })
    render(app()); expect(screen.getByText('login page')).toBeInTheDocument()
  })
  it('shows a loader while the session is restored', () => {
    Object.assign(state, { status: 'loading', user: null })
    render(app()); expect(screen.getByRole('status')).toBeInTheDocument()
  })
  it('lets authenticated users in, and enforces roles', () => {
    Object.assign(state, { status: 'authenticated', user: { role: 'viewer' } })
    render(app()); expect(screen.getByText('secret')).toBeInTheDocument()
    render(app(['administrator'])); expect(screen.getAllByText('home').length).toBe(1)
  })
})
