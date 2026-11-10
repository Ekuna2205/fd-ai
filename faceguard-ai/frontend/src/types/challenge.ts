export type StepKind = 'BLINK' | 'TURN_LEFT' | 'TURN_RIGHT' | 'LOOK_UP' | string
export interface Challenge {
  token: string; expires_at: number; steps: { kind: StepKind; instruction: string }[]
  step_timeout_seconds: number; max_recording_seconds: number; mirrored_display: boolean
}
export interface ChallengeResult {
  verification_id: string; status: 'REAL' | 'FAKE' | 'UNCERTAIN' | string
  assessment: {
    face_detected: boolean; image_quality_passed: boolean | null; challenge_completed: boolean
    challenge_outcome: string | null; liveness_assessed: boolean; ai_classification_available: boolean; statement: string
  }
  outcome: 'PASSED' | 'FAILED' | 'TIMED_OUT' | string
  progress: { steps: { kind: string; state: string; reason: string | null }[] }
  note: string; can_retry: boolean; retry_requires_new_challenge: boolean
}
