import type { VerificationStatus } from './dashboard'

/** Mirrors backend schemas/face.py. Coordinates are normalised 0..1 of the analysed image. */
export interface Box { x: number; y: number; w: number; h: number }
export interface Face { box: Box; landmarks: [number, number][] | null; roll_degrees: number | null }
export interface QualityCheck { name: string; label: string; value: number | null; ok: boolean; message: string | null }
export interface Quality { ready: boolean; checks: QualityCheck[] }
export interface DetectorInfo { name: string; landmarks: boolean }

export interface DetectionResult {
  image: { width: number; height: number }
  face_count: number
  faces: Face[]
  quality: Quality | null
  guidance: string[]
  detector: DetectorInfo
  processing_ms: number
}

export interface LivenessInfo { available: boolean; reason: string | null; model: string | null }

/** What the active anti-spoofing model measured. Present only when a model scored the sample. */
export interface LivenessScore {
  model: string
  bona_fide_score: number
  threshold: number
  uncertainty_margin: number
  frames_scored: number
}

export interface VideoSummary {
  frames_analyzed: number
  frames_single_face: number
  frames_no_face: number
  frames_multiple_faces: number
  duration_seconds: number | null
  face_presence_ratio: number
  quality_pass_ratio: number | null
  position_jitter: number | null
  size_variation: number | null
}

export type SessionMode = 'LIVE' | 'UPLOAD_IMAGE' | 'UPLOAD_VIDEO'

export interface VerificationResult {
  id: string
  created_at: string
  mode: SessionMode
  status: VerificationStatus
  spoof_type: string | null
  confidence: number | null
  face_count: number | null
  quality: Quality | null
  video: VideoSummary | null
  explanation: string | null
  model_version: string | null
  processing_ms: number | null
  liveness: LivenessInfo
  score: LivenessScore | null
}

export interface Capabilities {
  detector: DetectorInfo
  liveness: LivenessInfo
  limits: { max_image_mb: number; max_video_mb: number; max_video_seconds: number; image_types: string[]; video_types: string[] }
  consent_required: true
}
