import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  EpistemicBadge,
  InteractiveEvidenceGraph,
  OutcomeBadge,
} from './components/EvidenceWidgets';
import { EvidenceGraph } from './types';

describe('VeriDock EvidenceOS UI Components', () => {
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

  it('renders OutcomeBadge accurately for VeriDock decision states', () => {
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

  it('renders InteractiveEvidenceGraph with provenance nodes and edges', () => {
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
        onSelectEvidenceId={() => {}}
      />
    );
    expect(
      screen.getByText('Purchase Order (PO-2026-1003.pdf)')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Conflict: DAMAGE_QUANTITY_CONTRADICTION')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Decision: MANUAL_REVIEW_REQUIRED')
    ).toBeInTheDocument();
  });
});
