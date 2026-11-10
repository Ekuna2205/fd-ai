import { api } from './api'
import { downloadFile } from '@/utils/download'
import type { AuditPage, HistoryPage, HistoryQuery, Period, ReportSummary } from '@/types/history'

const clean = (o: object) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== '' && v != null))

export const listVerifications = (q: HistoryQuery) => api.get<HistoryPage>('/verifications', { params: clean(q) }).then((r) => r.data)
export const deleteVerification = (id: string) => api.delete(`/verifications/${id}`).then(() => undefined)
export const exportVerifications = (q: Partial<HistoryQuery>) =>
  downloadFile('/verifications/export', clean({ ...q, page: undefined, page_size: undefined }), 'verifications.csv')

export const getReport = (period: Period, days: number, scope: 'own' | 'all') =>
  api.get<ReportSummary>('/reports/summary', { params: { period, days, scope } }).then((r) => r.data)
export const exportReport = (period: Period, days: number, scope: 'own' | 'all') =>
  downloadFile('/reports/export', { period, days, scope }, 'faceguard-report.csv')

export const listAudit = (page: number, action: string) =>
  api.get<AuditPage>('/admin/audit-logs', { params: clean({ page, page_size: 25, action }) }).then((r) => r.data)
