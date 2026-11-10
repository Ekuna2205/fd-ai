import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ScoreBar } from './ScoreBar'

describe('ScoreBar', () => {
  it('shows the score, the threshold band and the model', () => {
    render(<ScoreBar score={{ model: 'cnn v2', bona_fide_score: 0.873, threshold: 0.55, uncertainty_margin: 0.1, frames_scored: 12 }} />)
    expect(screen.getByText('87.3%')).toBeInTheDocument()
    expect(screen.getByText('threshold 0.55 ± 0.10')).toBeInTheDocument()
    expect(screen.getByText(/cnn v2 · mean of 12 frames/)).toBeInTheDocument()
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '0.873')
  })
})
