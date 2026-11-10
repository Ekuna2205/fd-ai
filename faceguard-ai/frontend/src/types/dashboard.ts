export type VerificationStatus =
  | 'REAL' | 'FAKE' | 'UNCERTAIN' | 'NO_FACE' | 'MULTIPLE_FACES' | 'PROCESSING' | 'ERROR'

/** Contract for GET /api/dashboard/overview (implemented in Phase 2). */
export interface DashboardOverview {
  totals: {
    attempts: number
    real: number
    fake: number
    uncertain: number
    failed: number // NO_FACE + MULTIPLE_FACES + ERROR
    success_rate: number | null // 0..1, null when there are no attempts
  }
  daily: { date: string; real: number; fake: number; uncertain: number }[]
  spoof_categories: { category: string; count: number }[]
  recent: {
    id: string
    created_at: string
    status: VerificationStatus
    spoof_type: string | null
    confidence: number | null
  }[]
  active_model: {
    name: string
    version: string
    trained: boolean
    apcer: number | null
    bpcer: number | null
    acer: number | null
    evaluated_at: string | null
  } | null
}

/** Contract for GET /api/health */
export interface HealthStatus {
  status: 'ok' | 'degraded'
  database: boolean
  model_loaded: boolean
  model_trained: boolean
}
