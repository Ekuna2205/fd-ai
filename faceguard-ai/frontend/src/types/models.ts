export interface Evaluation {
  id: string; evaluated_at: string; sample_count: number | null; threshold: number | null
  accuracy: number | null; precision: number | null; recall: number | null; f1: number | null; roc_auc: number | null
  apcer: number | null; bpcer: number | null; acer: number | null; identity_disjoint: boolean | null
}
export interface ModelInfo {
  id: string; name: string; version: string; architecture: string; description: string | null
  is_trained: boolean; is_active: boolean; trained_at: string | null; created_at: string
  has_onnx: boolean; input_crop: "full" | "face"; latest_evaluation: Evaluation | null; blockers: string[]
}
export interface ModelDetail extends ModelInfo { evaluations: Evaluation[] }
