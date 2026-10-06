import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  EpistemicBadge,
  EvidenceInspectorDrawer,
  InteractiveEvidenceGraph,
  OutcomeBadge,
} from './components/EvidenceWidgets';
import { ConflictPresentationList } from './components/ConflictCard';
import { ProvenanceModal } from './components/ProvenanceModal';
import { DecisionReviewPanel } from './components/DecisionReviewPanel';
import { BenchmarkDashboard } from './components/BenchmarkDashboard';
import { AuditTrailPanel } from './components/AuditTrailPanel';
import {
  AuditTrailResponse,
  CaseDecision,
  EvaluationReport,
  EvidenceConflict,
  EvidenceGraph,
  EvidenceItem,
  NormalizedClaim,
} from './types';

describe('VeriDock EvidenceOS Investigation Workstation UI', () => {
  it('renders EpistemicBadge for FACT, INFERENCE, RULE, and UNCERTAINTY', () => {
    render(
      <div>
        <EpistemicBadge type="FACT" />
        <EpistemicBadge type="INFERENCE" />
        <EpistemicBadge type="RULE" />
        <EpistemicBadge type="UNCERTAINTY" />
      </div>
    );
    expect(screen.getByText('FACT')).toBeInTheDocument();
    expect(screen.getByText('INFERENCE')).toBeInTheDocument();
    expect(screen.getByText('RULE')).toBeInTheDocument();
    expect(screen.getByText('UNCERTAINTY')).toBeInTheDocument();
  });

  it('renders OutcomeBadge accurately with accessible non-color-only indicators', () => {
    render(
      <div>
        <OutcomeBadge outcome="approved" />
        <OutcomeBadge outcome="partially_approved" />
        <OutcomeBadge outcome="manual_review_required" />
      </div>
    );
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Partially Approved')).toBeInTheDocument();
    expect(screen.getByText('Manual Review')).toBeInTheDocument();
  });

  it('renders InteractiveEvidenceGraph with provenance nodes and keyboard/click selection', () => {
    const onSelect = vi.fn();
    const sampleGraph: EvidenceGraph = {
      case_id: 'case_03',
      nodes: [
        {
          id: 'ev_1',
          label: 'Purchase Order (PO-2026-1003.pdf)',
          node_type: 'evidence',
          epistemic_type: 'FACT',
          metadata: { confidence: 0.96 },
        },
        {
          id: 'clm_1',
          label: 'ordered_quantity: 10',
          node_type: 'claim',
          epistemic_type: 'FACT',
          metadata: { evidence_id: 'ev_1', confidence: 0.96 },
        },
        {
          id: 'ent_1',
          label: 'Industrial Servo Valve Assembly [SKU-IND-100]',
          node_type: 'entity',
          epistemic_type: 'INFERENCE',
          metadata: { confidence: 0.95 },
        },
        {
          id: 'cnf_1',
          label: 'Conflict: DAMAGE_QUANTITY_CONTRADICTION',
          node_type: 'conflict',
          epistemic_type: 'UNCERTAINTY',
          metadata: {},
        },
        {
          id: 'dec_1',
          label: 'Decision: MANUAL_REVIEW_REQUIRED',
          node_type: 'decision',
          epistemic_type: 'UNCERTAINTY',
          metadata: { confidence: 0.88 },
        },
      ],
      edges: [],
    };

    render(
      <InteractiveEvidenceGraph
        graph={sampleGraph}
        onSelectEvidenceId={onSelect}
      />
    );
    const poNode = screen.getByText('Purchase Order (PO-2026-1003.pdf)');
    expect(poNode).toBeInTheDocument();
    expect(
      screen.getByText('Conflict: DAMAGE_QUANTITY_CONTRADICTION')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Decision: MANUAL_REVIEW_REQUIRED')
    ).toBeInTheDocument();

    fireEvent.click(poNode);
    expect(onSelect).toHaveBeenCalledWith('ev_1');
  });

  it('renders ConflictPresentationList with side-by-side competing values and supporting evidence links', () => {
    const onInspect = vi.fn();
    const conflicts: EvidenceConflict[] = [
      {
        conflict_id: 'cnf_dmg_1',
        case_id: 'case_03',
        conflict_type: 'DAMAGE_QUANTITY_CONTRADICTION',
        severity: 'high',
        entity_key: 'ITEM:SKU-IND-100',
        attribute: 'damaged_quantity',
        description:
          'Voice report claims 5 damaged units while inspection photo supports 2 damaged units.',
        competing_values: [
          {
            evidence_id: 'ev_voice_1',
            document_role: 'voice_report',
            value: 5,
            confidence: 0.9,
          },
          {
            evidence_id: 'ev_img_1',
            document_role: 'inspection_image',
            value: 2,
            confidence: 0.92,
          },
        ],
        epistemic_type: 'UNCERTAINTY',
        detected_at: '2026-10-06T09:41:05Z',
      },
    ];

    render(
      <ConflictPresentationList
        conflicts={conflicts}
        historicalWarnings={[]}
        onInspectEvidenceById={onInspect}
        onSelectCase={() => {}}
      />
    );

    expect(screen.getByText(/DAMAGE QUANTITY CONFLICT/i)).toBeInTheDocument();
    expect(screen.getByText('5 damaged')).toBeInTheDocument();
    expect(screen.getByText('2 damaged')).toBeInTheDocument();

    const viewButtons = screen.getAllByText('View supporting evidence');
    fireEvent.click(viewButtons[0]);
    expect(onInspect).toHaveBeenCalledWith('ev_voice_1');
  });

  it('renders [Why?] ProvenanceModal with Decision -> Rule -> Claim -> Evidence traceability', () => {
    const claim: NormalizedClaim = {
      claim_id: 'clm_dmg_2',
      case_id: 'case_02',
      entity_key: 'ITEM:SKU-IND-100',
      attribute: 'damaged_quantity',
      value: 2,
      unit: 'units',
      epistemic_type: 'FACT',
      reason: 'Extracted from dock inspection photograph.',
      provenance: {
        evidence_id: 'ev_img_02',
        source_type: 'image',
        document_role: 'inspection_image',
        extraction_method: 'blind_pixel_cv',
        timestamp: '2026-10-06T09:41:04Z',
        confidence: 0.94,
        epistemic_type: 'FACT',
      },
    };
    const evidence: EvidenceItem[] = [
      {
        id: 'ev_img_02',
        case_id: 'case_02',
        original_filename: 'damage_photo_02.png',
        safe_filename: 'damage_photo_02.png',
        mime_type: 'image/png',
        modality: 'image',
        document_role: 'inspection_image',
        file_size_bytes: 4096,
        sha256_hash: 'abcdef1234567890abcdef1234567890',
        perceptual_hash: 'f0f0f0f00f0f0f0f',
        uploaded_at: '2026-10-06T09:41:02Z',
      },
    ];

    render(
      <ProvenanceModal
        caseId="case_02"
        claim={claim}
        allEvidence={evidence}
        allClaims={[claim]}
        decision={null}
        onClose={() => {}}
        onInspectEvidence={() => {}}
      />
    );

    expect(
      screen.getByText(/End-to-End Provenance Trace/i)
    ).toBeInTheDocument();
    expect(screen.getByText('damage_photo_02.png')).toBeInTheDocument();
  });

  it('distinguishes System Decision from Human Reviewer Override in DecisionReviewPanel', () => {
    const sysDecision: CaseDecision = {
      decision_id: 'dec_1',
      case_id: 'case_03',
      outcome: 'manual_review_required',
      epistemic_status: 'UNCERTAINTY',
      overall_confidence: 0.88,
      ordered_quantity: 10,
      delivered_quantity: 8,
      verified_damaged_quantity: 2,
      accepted_quantity: 6,
      disputed_quantity: 4,
      recommended_payout_adjustment_usd: 1000,
      summary_reason: 'Evidence conflicts across modalities.',
      detailed_explanation: [
        'Challan reports 8 delivered',
        'Voice report claims 5 damaged',
        'Images support 2 damaged',
      ],
      next_action: 'Inspect physical pallet and record reviewer override.',
      rule_traces: [
        {
          rule_id: 'RULE_03',
          rule_name: 'Cross-Modal Corroboration',
          passed: false,
          epistemic_type: 'RULE',
          inputs_used: { voice_damaged: 5, image_damaged: 2 },
          evidence_ids: ['ev_1', 'ev_2'],
          explanation: 'Voice and image damage counts disagree (5 vs 2).',
        },
      ],
      supporting_evidence_ids: ['ev_1', 'ev_2'],
      conflict_ids: ['cnf_1'],
      historical_warning_ids: [],
      is_human_override: false,
      decided_at: '2026-10-06T09:41:07Z',
    };

    render(
      <DecisionReviewPanel
        decision={sysDecision}
        reviewerName="auditor_1"
        setReviewerName={() => {}}
        reviewOutcome="partially_approved"
        setReviewOutcome={() => {}}
        reviewAcceptedQty={6}
        setReviewAcceptedQty={() => {}}
        reviewDamagedQty={2}
        setReviewDamagedQty={() => {}}
        reviewNotes="Verified dock count."
        setReviewNotes={() => {}}
        onSubmitOverride={(e) => e.preventDefault()}
        onReviewEvidence={() => {}}
        loading={false}
      />
    );

    expect(
      screen.getByText(/Decision Source: Deterministic Rule Engine/i)
    ).toBeInTheDocument();
    expect(screen.getByText('Challan reports 8 delivered')).toBeInTheDocument();
    expect(
      screen.getByText('RULE_03 — Cross-Modal Corroboration')
    ).toBeInTheDocument();
  });

  it('renders BenchmarkDashboard with live API metrics, sample size n, and failure modes', () => {
    const sampleReport: EvaluationReport = {
      benchmark_version: 'veridock-heldout-v3.0 (150-Case Blind Held-Out Suite)',
      suite_type: 'heldout_150',
      total_cases: 150,
      total_evidence_files: 564,
      total_suite_duration_ms: 4200,
      metrics: {
        extraction_accuracy: 0.8933,
        field_level_accuracy: 0.9556,
        entity_matching_accuracy: 1.0,
        conflict_detection_precision: 0.9057,
        conflict_detection_recall: 1.0,
        duplicate_detection_accuracy: 1.0,
        decision_accuracy: 0.94,
        decision_accuracy_ci_95: [0.89, 0.968],
        macro_f1: 0.9132,
        confident_error_rate: 0.0,
        false_positive_rate: 0.0,
        false_negative_rate: 0.06,
        mean_processing_latency_ms: 148,
        p95_processing_latency_ms: 286,
        cost_per_case_usd: 0.0,
        estimated_cloud_llm_cost_per_case_usd: 0.0014,
      },
      category_breakdown: [
        {
          category: 'clean_delivery',
          total_cases: 6,
          passed_cases: 6,
          accuracy: 1.0,
        },
        {
          category: 'multi_sku_dispute',
          total_cases: 6,
          passed_cases: 3,
          accuracy: 0.5,
        },
      ],
      failure_taxonomy_counts: {
        ENTITY_LINKING_ERROR: 3,
        VOICE_INTERPRETATION_ERROR: 2,
      },
      case_results: [],
    };

    render(
      <BenchmarkDashboard
        evalReport={sampleReport}
        evalSuiteType="heldout_150"
        onRunEvaluation={() => {}}
        loading={false}
      />
    );

    expect(screen.getByText('94.0%')).toBeInTheDocument();
    expect(screen.getByText('91.3%')).toBeInTheDocument();
    expect(screen.getAllByText('n = 6').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('3 failures')).toBeInTheDocument();
    expect(screen.getByText('2 failures')).toBeInTheDocument();
  });

  it('renders chronological AuditTrailPanel with SHA-256 chain integrity', () => {
    const sampleAudit: AuditTrailResponse = {
      case_id: 'case_03',
      chain_integrity: {
        valid: true,
        event_count: 2,
        head_hash: '9999abcdef',
      },
      events: [
        {
          id: 'ev_log_1',
          event_type: 'EVIDENCE_INGESTED',
          actor: 'system',
          stage: 'ingestion',
          status: 'success',
          duration_ms: 14,
          details: { filename: 'PO-2026-1003.pdf' },
          previous_event_hash: 'GENESIS',
          event_hash: '1111abcdef',
          created_at: '2026-10-06T09:41:02Z',
        },
        {
          id: 'ev_log_2',
          event_type: 'HUMAN_REVIEW_OVERRIDE',
          actor: 'senior_procurement_auditor',
          stage: 'human_review',
          status: 'success',
          duration_ms: 5,
          details: { outcome: 'partially_approved' },
          previous_event_hash: '1111abcdef',
          event_hash: '9999abcdef',
          created_at: '2026-10-06T09:43:21Z',
        },
      ],
    };

    render(<AuditTrailPanel auditTrail={sampleAudit} />);
    expect(screen.getByText(/Chain Integrity: VERIFIED/i)).toBeInTheDocument();
    expect(
      screen.getByText('Evidence uploaded (PO-2026-1003.pdf)')
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Reviewer override → partially approved/i)
    ).toBeInTheDocument();
  });

  it('highlights extracted PDF line items inline in EvidenceInspectorDrawer when claim pills are clicked', () => {
    const pdfEvidence: EvidenceItem = {
      id: 'ev_pdf_challan',
      case_id: 'case_02',
      original_filename: 'DC-2026-1002.pdf',
      safe_filename: 'DC-2026-1002.pdf',
      mime_type: 'application/pdf',
      modality: 'pdf',
      document_role: 'delivery_challan',
      file_size_bytes: 2048,
      sha256_hash: '1234567890abcdef1234567890abcdef',
      uploaded_at: '2026-10-06T09:41:02Z',
      extracted_payload: {
        document_id: 'DC-2026-1002',
        items: [
          {
            sku: 'SKU-IND-100',
            name: 'Industrial Servo Valve Assembly',
            delivered_quantity: 10,
            damaged_quantity: 2,
            unit_price: 250,
          },
        ],
        provenance: {
          evidence_id: 'ev_pdf_challan',
          source_type: 'pdf',
          document_role: 'delivery_challan',
          location: 'page:1',
          extraction_method: 'evidenceos-semantic-extractor-v1:document_parser',
          timestamp: '2026-10-06T09:41:03Z',
          confidence: 0.96,
          epistemic_type: 'FACT',
          raw_snippet:
            'DELIVERY CHALLAN\nDOCUMENT ID: DC-2026-1002\nITEM | SKU: SKU-IND-100 | NAME: Industrial Servo Valve Assembly | DELIVERED: 10 | DAMAGED: 2 | PRICE: 250.0',
        },
      },
    };

    render(
      <EvidenceInspectorDrawer
        caseId="case_02"
        item={pdfEvidence}
        onClose={() => {}}
      />
    );

    expect(
      screen.getByText(/Inline PDF \/ Source Evidence Highlighting/i)
    ).toBeInTheDocument();
    const dmgChip = screen.getByRole('button', {
      name: /Damaged: 2 units \(SKU-IND-100\)/i,
    });
    fireEvent.click(dmgChip);
    expect(screen.getByText(/← Extracted Claim Span/i)).toBeInTheDocument();
  });

  it('renders side-by-side visual comparison for reused/near-duplicate images in ConflictPresentationList', () => {
    render(
      <ConflictPresentationList
        conflicts={[]}
        historicalWarnings={[
          {
            match_id: 'hm_01',
            case_id: 'case_04_reused_historical_evidence',
            current_evidence_id: 'ev_curr_img',
            historical_case_id: 'case_02_partial_damage',
            historical_evidence_id: 'ev_hist_img',
            match_type: 'PERCEPTUAL_DHASH_NEAR_DUPLICATE',
            similarity_score: 0.984,
            hamming_distance: 1,
            warning_message:
              'Uploaded inspection image matches historical dispute case_02_partial_damage.',
          },
        ]}
        onInspectEvidenceById={() => {}}
        onSelectCase={() => {}}
      />
    );

    expect(screen.getByText(/Potentially reused evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Current Claim Image/i)).toBeInTheDocument();
    expect(screen.getByText(/Historical Image \(Prior Claim\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Hamming Distance: 1\/64/i)).toBeInTheDocument();
  });
});

