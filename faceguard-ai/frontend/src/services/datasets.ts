import { api } from './api'
import { downloadFile } from '@/utils/download'
import type { DatasetImage, DatasetPage, DatasetStats, DatasetSummary, DatasetValidation } from '@/types/datasets'

export const listDatasets = () => api.get<DatasetSummary[]>('/datasets').then((r) => r.data)
export const createDataset = (name: string, description: string) => api.post<DatasetSummary>('/datasets', { name, description }).then((r) => r.data)
export const deleteDataset = (id: string) => api.delete(`/datasets/${id}`).then(() => undefined)
export const getDataset = (id: string, offset: number, limit: number, label?: string) =>
  api.get<DatasetPage>(`/datasets/${id}`, { params: { offset, limit, ...(label ? { label } : {}) } }).then((r) => r.data)
export const getStats = (id: string) => api.get<DatasetStats>(`/datasets/${id}/stats`).then((r) => r.data)
export const getValidation = (id: string) => api.get<DatasetValidation>(`/datasets/${id}/validation`).then((r) => r.data)
export const addImage = (id: string, file: File, meta: { label?: string; identity?: string; group?: string }) => {
  const f = new FormData()
  f.append('file', file, file.name)
  for (const [k, v] of Object.entries(meta)) if (v) f.append(k, v)
  return api.post<DatasetImage>(`/datasets/${id}/images`, f, { timeout: 60_000 }).then((r) => r.data)
}
export const patchImage = (id: string, sha: string, patch: { label?: 'REAL' | 'FAKE' | null; identity?: string | null; group?: string | null }) =>
  api.patch<DatasetImage>(`/datasets/${id}/images/${sha}`, patch).then((r) => r.data)
export const deleteImage = (id: string, sha: string) => api.delete(`/datasets/${id}/images/${sha}`).then(() => undefined)
/** crop='face': one square face crop per image, made by the same detector + crop the API uses at inference time. */
export const exportDataset = (id: string, crop: 'full' | 'face' = 'full') =>
  downloadFile(`/datasets/${id}/export`, crop === 'face' ? { crop } : {}, `dataset-${id.slice(0, 8)}${crop === 'face' ? '-faces' : ''}.zip`)
/** Images need the bearer token, so they are fetched as blobs and shown through object URLs. */
export const fetchImageBlob = (id: string, sha: string) => api.get<Blob>(`/datasets/${id}/images/${sha}/file`, { responseType: 'blob' }).then((r) => r.data)
