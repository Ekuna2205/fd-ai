import type { VerificationStatus } from './dashboard'
import type { SessionMode } from './face'

/** Mirror backend schemas/history.py */
export interface HistoryItem {
  id: string; created_at: string; mode: SessionMode; status: VerificationStatus
  spoof_type: string | null; confidence: number | null; face_count: number | null; processing_ms: number | null
}
export interface HistoryPage { items: HistoryItem[]; total: number; page: number; page_size: number }
export interface HistoryQuery {
  q?: string; status?: VerificationStatus | ''; mode?: SessionMode | ''; date_from?: string; date_to?: string
  sort: 'created_at' | 'status' | 'processing_ms' | 'confidence'; order: 'asc' | 'desc'; page: number; page_size: number
}

export type Period = 'day' | 'week' | 'month'
export interface SeriesPoint { bucket: string; real: number; fake: number; uncertain: number; failed: number }
export interface ReportSummary {
  scope: 'own' | 'all'; period: Period; days: number
  totals: { attempts: number; real: number; fake: number; uncertain: number; failed: number; success_rate: number | null }
  series: SeriesPoint[]
  status_distribution: { status: VerificationStatus; count: number }[]
  spoof_categories: { category: string; count: number }[]
  avg_processing_ms: number | null
}

export interface AuditItem {
  id: string; created_at: string; action: string; user_email: string | null; ip_address: string | null
  entity_type: string | null; entity_id: string | null; details: Record<string, unknown> | null
}
export interface AuditPage { items: AuditItem[]; total: number; page: number; page_size: number }
