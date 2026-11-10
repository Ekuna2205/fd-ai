export interface DatasetSummary {
  id: string; name: string; description: string; created_at: string; updated_at: string
  images: number; real: number; fake: number; unlabeled: number
  collect?: { enabled: boolean; token: string | null; participants: number }
}
export interface DatasetImage {
  sha256: string; ext: string; label: 'REAL' | 'FAKE' | null; identity: string | null; group: string | null
  size: number; width: number; height: number; original_name: string; added_at: string
}
export interface DatasetPage extends DatasetSummary { total_filtered: number; offset: number; limit: number; items: DatasetImage[] }
export interface DatasetStats {
  images: number; labels: { REAL: number; FAKE: number; UNLABELED: number }; identities: number
  images_without_identity: number; identities_by_label: { REAL: number; FAKE: number }
  max_images_per_identity: number; total_bytes: number; min_side_px: number | null; max_side_px: number | null
}
export interface DatasetValidation { ready: boolean; problems: string[]; warnings: string[]; stats: DatasetStats }
