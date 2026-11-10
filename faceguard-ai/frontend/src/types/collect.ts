export type CollectLabel = 'REAL' | 'FAKE'
export interface CollectInfo { name: string; description: string; step_seconds: number; max_video_mb: number; attack_types: string[] }
export interface CollectFrame {
  face_count: number
  box: { x: number; y: number; w: number; h: number } | null
  yaw: number | null // -1..1, raw camera image; the participant's LEFT is positive
  ear: number | null
  quality_ready: boolean | null
}
export interface CollectScore { model: string; bona_fide_score: number; status: 'REAL' | 'FAKE' | 'UNCERTAIN'; threshold: number }
export interface CollectResult {
  added: number; skipped: number; frames_analyzed: number; label: CollectLabel; group: string
  score: CollectScore | null; message: string
}
