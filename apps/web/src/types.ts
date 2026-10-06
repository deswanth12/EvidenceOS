export type EpistemologicalType = 'FACT' | 'INFERENCE' | 'RULE' | 'UNCERTAINTY';

export type DecisionOutcome =
  | 'approved'
  | 'partially_approved'
  | 'disputed'
  | 'manual_review_required'
  | 'insufficient_evidence';

export interface Provenance {
  evidence_id: string;
  source_type: string;
  document_role: string;
  location?: string | null;
  extraction_method: string;
  timestamp: string;
  confidence: number;
  epistemic_type: EpistemologicalType;
  raw_snippet?: string | null;
}

export interface EvidenceItem {
  id: string;
  case_id: string;
  original_filename: string;
  safe_filename: string;
  mime_type: string;
  modality: string;
  document_role: string;
  file_size_bytes: number;
  sha256_hash: string;
  perceptual_hash?: string | null;
  extracted_payload?: Record<string, any> | null;
  extraction_metadata?: Record<string, any> | null;
  uploaded_at: string;
  processed_at?: string | null;
}

export interface NormalizedClaim {
  claim_id: string;
  case_id: string;
  entity_key: string;
  attribute: string;
  value: any;
  unit?: string | null;
  epistemic_type: EpistemologicalType;
  reason: string;
  provenance: Provenance;
}

export interface ResolvedEntity {
  entity_id: string;
  case_id: string;
  entity_type: string;
  canonical_key: string;
  display_name: string;
  sku?: string | null;
  linked_evidence_ids: string[];
  linked_claim_ids: string[];
  attributes_by_source: Record<string, any[]>;
  resolution_method: string;
  confidence: number;
}

export interface EvidenceConflict {
  conflict_id: string;
  case_id: string;
  conflict_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  entity_key: string;
  attribute: string;
  description: string;
  competing_values: Array<{
    evidence_id: string;
    document_role: string;
    attribute?: string;
    value: any;
    confidence: number;
    location?: string;
  }>;
  epistemic_type: EpistemologicalType;
  detected_at: string;
}

export interface HistoricalWarning {
  match_id: string;
  case_id: string;
  current_evidence_id: string;
  historical_case_id: string;
  historical_evidence_id: string;
  match_type: string;
  similarity_score: number;
  hamming_distance?: number | null;
  warning_message: string;
  detected_at?: string | null;
}

export interface RuleEvaluationTrace {
  rule_id: string;
  rule_name: string;
  passed: boolean;
  epistemic_type: EpistemologicalType;
  inputs_used: Record<string, any>;
  evidence_ids: string[];
  explanation: string;
}

export interface CaseDecision {
  decision_id: string;
  case_id: string;
  outcome: DecisionOutcome;
  epistemic_status: EpistemologicalType;
  overall_confidence: number;
  ordered_quantity: number;
  delivered_quantity: number;
  verified_damaged_quantity: number;
  accepted_quantity: number;
  disputed_quantity: number;
  recommended_payout_adjustment_usd: number;
  summary_reason: string;
  detailed_explanation: string[];
  next_action: string;
  rule_traces: RuleEvaluationTrace[];
  supporting_evidence_ids: string[];
  conflict_ids: string[];
  historical_warning_ids: string[];
  is_human_override: boolean;
  human_reviewer?: string | null;
  human_override_notes?: string | null;
  decided_at: string;
}

export interface GraphNode {
  id: string;
  label: string;
  node_type: 'case' | 'evidence' | 'entity' | 'claim' | 'conflict' | 'decision';
  epistemic_type?: EpistemologicalType | null;
  metadata: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  metadata: Record<string, any>;
}

export interface EvidenceGraph {
  case_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface PipelineChecklist {
  evidence_received?: boolean;
  documents_processed?: boolean;
  images_analyzed?: boolean;
  voice_analyzed?: boolean;
  evidence_linked?: boolean;
  conflicts_detected?: boolean;
  rules_evaluated?: boolean;
  decision?: string | null;
}

export interface CaseSummary {
  id: string;
  title: string;
  description?: string | null;
  supplier_name?: string | null;
  buyer_name?: string | null;
  po_number?: string | null;
  status: string;
  pipeline_checklist: PipelineChecklist;
  evidence_count: number;
  conflict_count: number;
  historical_warning_count: number;
  latest_decision_outcome?: DecisionOutcome | null;
  created_at: string;
  updated_at: string;
}

export interface CaseDetail {
  id: string;
  title: string;
  description?: string | null;
  supplier_name?: string | null;
  buyer_name?: string | null;
  po_number?: string | null;
  status: string;
  contract_sla_config: Record<string, any>;
  pipeline_checklist: PipelineChecklist;
  evidence_items: EvidenceItem[];
  claims: NormalizedClaim[];
  entities: ResolvedEntity[];
  conflicts: EvidenceConflict[];
  historical_warnings: HistoricalWarning[];
  latest_decision?: CaseDecision | null;
  graph: EvidenceGraph;
  created_at: string;
  updated_at: string;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  actor: string;
  stage: string;
  status: string;
  duration_ms?: number | null;
  model_used?: string | null;
  details: Record<string, any>;
  previous_event_hash?: string | null;
  event_hash: string;
  created_at: string;
}

export interface AuditTrailResponse {
  case_id: string;
  chain_integrity: {
    valid: boolean;
    event_count: number;
    head_hash?: string | null;
  };
  events: AuditEvent[];
}

export interface EvaluationReport {
  benchmark_version: string;
  total_cases: number;
  total_evidence_files: number;
  total_suite_duration_ms: number;
  metrics: {
    extraction_accuracy: number;
    field_level_accuracy: number;
    entity_matching_accuracy: number;
    conflict_detection_precision: number;
    conflict_detection_recall: number;
    duplicate_detection_accuracy: number;
    decision_accuracy: number;
    false_positive_rate: number;
    false_negative_rate: number;
    mean_processing_latency_ms: number;
    p95_processing_latency_ms: number;
    cost_per_case_usd: number;
    estimated_cloud_llm_cost_per_case_usd: number;
  };
  case_results: Array<{
    case_id: string;
    title: string;
    expected_outcome: string;
    actual_outcome: string;
    passed: boolean;
    ordered_qty: number;
    delivered_qty: number;
    verified_damaged_qty: number;
    conflicts_detected: number;
    expected_conflicts: number;
    historical_warnings: number;
    latency_ms: number;
  }>;
}
