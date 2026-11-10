import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConsentCard } from './ConsentCard'

describe('ConsentCard', () => {
  it('blocks the action until the user explicitly consents', async () => {
    const onConsent = vi.fn()
    render(<ConsentCard action="Continue to camera" onConsent={onConsent} />)
    const button = screen.getByRole('button', { name: 'Continue to camera' })
    expect(button).toBeDisabled()
    await userEvent.click(button)
    expect(onConsent).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('checkbox'))
    expect(button).toBeEnabled()
    await userEvent.click(button)
    expect(onConsent).toHaveBeenCalledOnce()
  })

  it('states that images are not stored and no template is created', () => {
    render(<ConsentCard action="Go" onConsent={() => {}} />)
    expect(screen.getByText(/They are not saved/)).toBeInTheDocument()
    expect(screen.getByText(/No biometric template/)).toBeInTheDocument()
  })
})
