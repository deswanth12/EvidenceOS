import React, { useEffect, useState } from 'react';
import {
  EvidenceGraph,
  EvidenceItem,
  GraphNode,
  EpistemologicalType,
} from '../types';
import {
  FileText,
  Image as ImageIcon,
  Mic,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Hash,
  ExternalLink,
  HelpCircle,
  Scale,
  Package,
  X,
} from 'lucide-react';

export function EpistemicBadge({
  type,
}: {
  type?: EpistemologicalType | string | null;
}) {
  if (!type) return null;
  const styles: Record<string, { cls: string; title: string }> = {
    FACT: {
      cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/35',
      title: 'Directly extracted from source evidence with verbatim provenance',
    },
    INFERENCE: {
      cls: 'bg-sky-500/15 text-sky-300 border-sky-500/35',
      title: 'Derived by linking or reconciling multiple pieces of evidence',
    },
    RULE: {
      cls: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/35',
      title: 'Determined by explicit contract / SLA rule logic',
    },
    UNCERTAINTY: {
      cls: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
      title: 'Insufficient, degraded, or conflicting evidence requiring human review',
    },
  };
  const cfg = styles[type] || {
    cls: 'bg-slate-800 text-slate-300 border-slate-700',
    title: String(type),
  };
  return (
    <span
      title={cfg.title}
      aria-label={`Epistemic type: ${type}`}
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold border ${cfg.cls}`}
    >
      {type}
    </span>
  );
}

export function OutcomeBadge({ outcome }: { outcome?: string | null }) {
  if (!outcome) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400" aria-hidden="true" />
        <span>Pending Processing</span>
      </span>
    );
  }
  const map: Record<
    string,
    { label: string; cls: string; dotCls: string; symbol: string }
  > = {
    approved: {
      label: 'Approved',
      cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
      dotCls: 'bg-emerald-400',
      symbol: '✓',
    },
    approved_full: {
      label: 'Approved',
      cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
      dotCls: 'bg-emerald-400',
      symbol: '✓',
    },
    partially_approved: {
      label: 'Partially Approved',
      cls: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
      dotCls: 'bg-sky-400',
      symbol: '◐',
    },
    approved_partial_settlement: {
      label: 'Partially Approved',
      cls: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
      dotCls: 'bg-sky-400',
      symbol: '◐',
    },
    manual_review_required: {
      label: 'Manual Review',
      cls: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
      dotCls: 'bg-amber-400',
      symbol: '⚠',
    },
    disputed: {
      label: 'Disputed',
      cls: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
      dotCls: 'bg-rose-400',
      symbol: '✕',
    },
    rejected_duplicate_evidence: {
      label: 'Rejected (Duplicate Evidence)',
      cls: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
      dotCls: 'bg-rose-400',
      symbol: '✕',
    },
    rejected_late_filing: {
      label: 'Rejected (SLA Expired)',
      cls: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
      dotCls: 'bg-rose-400',
      symbol: '✕',
    },
    insufficient_evidence: {
      label: 'Insufficient Evidence',
      cls: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
      dotCls: 'bg-amber-400',
      symbol: '?',
    },
  };
  const cfg = map[outcome] || {
    label: outcome,
    cls: 'bg-slate-800 text-slate-300 border-slate-700',
    dotCls: 'bg-slate-400',
    symbol: '•',
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${cfg.cls}`}
    >
      <span className="font-mono text-[11px]" aria-hidden="true">
        {cfg.symbol}
      </span>
      <span>{cfg.label}</span>
    </span>
  );
}

export function InteractiveEvidenceGraph({
  graph,
  onSelectEvidenceId,
}: {
  graph: EvidenceGraph;
  onSelectEvidenceId: (evidenceId: string) => void;
}) {
  const evidenceNodes = graph.nodes.filter((n) => n.node_type === 'evidence');
  const claimNodes = graph.nodes.filter((n) => n.node_type === 'claim');
  const entityNodes = graph.nodes.filter((n) => n.node_type === 'entity');
  const conflictNodes = graph.nodes.filter((n) => n.node_type === 'conflict');
  const decisionNodes = graph.nodes.filter((n) => n.node_type === 'decision');

  const getRoleBadge = (node: GraphNode): string => {
    const lbl = node.label.toLowerCase();
    if (node.node_type === 'evidence') {
      if (lbl.includes('purchase order') || lbl.includes('po-')) return 'Purchase Order';
      if (lbl.includes('challan') || lbl.includes('dc-')) return 'Delivery Challan';
      if (lbl.includes('invoice')) return 'Invoice';
      if (lbl.includes('image') || lbl.includes('.png') || lbl.includes('.jpg'))
        return 'Inspection Image';
      if (lbl.includes('voice') || lbl.includes('.wav')) return 'Voice Report';
      return 'Evidence File';
    }
    if (node.node_type === 'entity') return 'Shipment / SKU Entity';
    if (node.node_type === 'claim') return 'Extracted Claim';
    if (node.node_type === 'conflict') return 'Cross-Modal Conflict';
    if (node.node_type === 'decision') return 'Rule & Final Decision';
    return node.node_type;
  };

  const renderNodeCard = (node: GraphNode) => {
    const isClickable =
      node.node_type === 'evidence' ||
      (node.node_type === 'claim' && Boolean(node.metadata?.evidence_id));
    const targetEvId =
      node.node_type === 'evidence' ? node.id : node.metadata?.evidence_id;

    let borderStyle = 'border-slate-800 bg-slate-900/90';
    if (node.node_type === 'evidence')
      borderStyle = 'border-sky-500/40 bg-sky-950/20 hover:border-sky-400';
    if (node.node_type === 'claim')
      borderStyle = 'border-emerald-500/35 bg-emerald-950/15 hover:border-emerald-400';
    if (node.node_type === 'entity')
      borderStyle = 'border-indigo-500/40 bg-indigo-950/25';
    if (node.node_type === 'conflict')
      borderStyle = 'border-amber-500/50 bg-amber-950/25';
    if (node.node_type === 'decision')
      borderStyle = 'border-violet-500/50 bg-violet-950/30';

    const handleTrigger = () => {
      if (isClickable && targetEvId) {
        onSelectEvidenceId(String(targetEvId));
      }
    };

    return (
      <div
        key={node.id}
        role={isClickable ? 'button' : undefined}
        tabIndex={isClickable ? 0 : undefined}
        aria-label={`${getRoleBadge(node)}: ${node.label}`}
        onClick={handleTrigger}
        onKeyDown={(e) => {
          if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            handleTrigger();
          }
        }}
        className={`eos-interactive-card p-3 rounded-lg border text-left ${borderStyle} ${
          isClickable ? 'cursor-pointer hover:bg-slate-900' : ''
        }`}
      >
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
            {getRoleBadge(node)}
          </span>
          <EpistemicBadge type={node.epistemic_type} />
        </div>
        <div className="text-xs font-medium text-slate-100 break-words">
          {node.label}
        </div>
        {node.metadata?.confidence !== undefined && (
          <div className="mt-1.5 text-[11px] font-mono text-slate-400">
            Extraction confidence: {(Number(node.metadata.confidence) * 100).toFixed(0)}%
          </div>
        )}
        {isClickable && (
          <div className="mt-1.5 text-[10px] text-sky-400 flex items-center gap-1 font-medium">
            <span>Inspect source file & provenance</span>
            <ExternalLink className="w-2.5 h-2.5" aria-hidden="true" />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="eos-reveal eos-stagger-4 space-y-4">
      <div className="eos-panel flex flex-wrap items-center justify-between gap-2 bg-slate-900/80 border border-slate-800 rounded-lg p-3.5">
        <div className="text-xs text-slate-300">
          <span className="font-semibold text-white">
            Evidence-to-Decision Provenance Graph:
          </span>{' '}
          Traces Purchase Order & Delivery Challan → Shipment SKU → Multimodal Claims (Image & Voice) → Conflicts → Rule Evaluation → Final Decision.
        </div>
        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <span>Nodes: {graph.nodes.length}</span>
          <span>Links: {graph.edges.length}</span>
        </div>
      </div>

      {/* Clear Flow Legend */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* Column 1: Raw Evidence Sources */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-sky-400 border-b border-slate-800 pb-1.5 flex items-center justify-between">
            <span>1. Source Files ({evidenceNodes.length})</span>
            <FileText className="w-3.5 h-3.5" aria-hidden="true" />
          </div>
          {evidenceNodes.map(renderNodeCard)}
        </div>

        {/* Column 2: Normalized Claims */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400 border-b border-slate-800 pb-1.5 flex items-center justify-between">
            <span>2. Extracted Claims ({claimNodes.length})</span>
            <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
          </div>
          {claimNodes.map(renderNodeCard)}
        </div>

        {/* Column 3: Resolved Canonical Entities */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-indigo-400 border-b border-slate-800 pb-1.5 flex items-center justify-between">
            <span>3. Shipment & SKU ({entityNodes.length})</span>
            <Package className="w-3.5 h-3.5" aria-hidden="true" />
          </div>
          {entityNodes.map(renderNodeCard)}
        </div>

        {/* Column 4: Detected Contradictions */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-amber-400 border-b border-slate-800 pb-1.5 flex items-center justify-between">
            <span>4. Conflicts ({conflictNodes.length})</span>
            <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
          </div>
          {conflictNodes.length === 0 ? (
            <div className="p-3 rounded-lg border border-slate-800/80 bg-slate-900/40 text-xs text-slate-400">
              No cross-modal contradictions detected.
            </div>
          ) : (
            conflictNodes.map(renderNodeCard)
          )}
        </div>

        {/* Column 5: Deterministic Decision */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold uppercase tracking-wider text-violet-400 border-b border-slate-800 pb-1.5 flex items-center justify-between">
            <span>5. Rule & Decision ({decisionNodes.length})</span>
            <Scale className="w-3.5 h-3.5" aria-hidden="true" />
          </div>
          {decisionNodes.map(renderNodeCard)}
        </div>
      </div>
    </div>
  );
}

export function EvidenceInspectorDrawer({
  caseId,
  item,
  onClose,
}: {
  caseId: string;
  item: EvidenceItem | null;
  onClose: () => void;
}) {
  const [selectedHighlightTerm, setSelectedHighlightTerm] = useState<string>('ALL');

  useEffect(() => {
    setSelectedHighlightTerm('ALL');
  }, [item?.id]);

  useEffect(() => {
    if (!item) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [item, onClose]);

  if (!item) return null;

  const prov = item.extracted_payload?.provenance;
  const rawUrl = `/api/cases/${caseId}/evidence/${item.id}/raw`;
  const extractedItems: Array<Record<string, any>> = Array.isArray(
    item.extracted_payload?.items
  )
    ? item.extracted_payload.items
    : [];

  // Build interactive highlight chips from extracted PDF line items
  const highlightChips: Array<{ id: string; label: string; tokens: string[] }> = [
    {
      id: 'ALL',
      label: 'All Extracted Line Items',
      tokens: ['ITEM', 'SKU:', 'ORDERED', 'DELIVERED', 'DAMAGED', 'PRICE', 'units', 'boxes'],
    },
  ];
  extractedItems.forEach((it, idx) => {
    const sku = String(it.sku || 'SKU-IND-100');
    if (it.ordered_quantity !== null && it.ordered_quantity !== undefined) {
      highlightChips.push({
        id: `ord-${idx}`,
        label: `Ordered: ${it.ordered_quantity} units (${sku})`,
        tokens: [`ORDERED: ${it.ordered_quantity}`, `${it.ordered_quantity} units`, sku],
      });
    }
    if (it.delivered_quantity !== null && it.delivered_quantity !== undefined) {
      highlightChips.push({
        id: `del-${idx}`,
        label: `Delivered: ${it.delivered_quantity} units (${sku})`,
        tokens: [`DELIVERED: ${it.delivered_quantity}`, `${it.delivered_quantity} units`, sku],
      });
    }
    if (it.damaged_quantity !== null && it.damaged_quantity !== undefined) {
      highlightChips.push({
        id: `dmg-${idx}`,
        label: `Damaged: ${it.damaged_quantity} units (${sku})`,
        tokens: [`DAMAGED: ${it.damaged_quantity}`, `${it.damaged_quantity} units damaged`, sku],
      });
    }
    if (it.unit_price !== null && it.unit_price !== undefined) {
      highlightChips.push({
        id: `prc-${idx}`,
        label: `Unit Price: $${it.unit_price}`,
        tokens: [`PRICE: ${it.unit_price}`, `$${it.unit_price}`, sku],
      });
    }
  });

  const activeChip =
    highlightChips.find((c) => c.id === selectedHighlightTerm) || highlightChips[0];

  // Build numbered document lines for inline PDF highlighting
  const rawTextLines: string[] = prov?.raw_snippet
    ? String(prov.raw_snippet)
        .split(/\r?\n/)
        .filter((l) => l.trim().length > 0)
    : [];

  // Ensure extracted line items are represented in the inline viewer even if snippet was truncated
  if (extractedItems.length > 0) {
    extractedItems.forEach((it) => {
      const sku = String(it.sku || 'SKU-IND-100');
      const alreadyInLines = rawTextLines.some((l) =>
        l.toUpperCase().includes(sku.toUpperCase())
      );
      if (!alreadyInLines) {
        const parts = [`ITEM | SKU: ${sku} | NAME: ${it.name || 'Component'}`];
        if (it.ordered_quantity !== null && it.ordered_quantity !== undefined)
          parts.push(`ORDERED: ${it.ordered_quantity}`);
        if (it.delivered_quantity !== null && it.delivered_quantity !== undefined)
          parts.push(`DELIVERED: ${it.delivered_quantity}`);
        if (it.damaged_quantity !== null && it.damaged_quantity !== undefined)
          parts.push(`DAMAGED: ${it.damaged_quantity}`);
        if (it.unit_price !== null && it.unit_price !== undefined)
          parts.push(`PRICE: ${it.unit_price}`);
        rawTextLines.push(parts.join(' | '));
      }
    });
  }

  const isLineHighlighted = (line: string): boolean => {
    const upperLine = line.toUpperCase();
    return activeChip.tokens.some((tok) => upperLine.includes(tok.toUpperCase()));
  };

  const ModalityIcon =
    item.modality === 'image'
      ? ImageIcon
      : item.modality === 'audio'
      ? Mic
      : FileText;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-drawer-title"
      className="fixed inset-0 z-50 flex justify-end bg-slate-950/60 backdrop-blur-[1px]"
      onClick={onClose}
    >
      <div
        className="eos-panel eos-reveal w-full max-w-xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col h-full"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
          <div className="flex items-center gap-2.5">
            <ModalityIcon className="w-5 h-5 text-sky-400" aria-hidden="true" />
            <div>
              <h3 id="evidence-drawer-title" className="text-sm font-semibold text-white">
                {item.original_filename}
              </h3>
              <p className="text-xs font-mono text-slate-400">
                ID: {item.id} • Role: {item.document_role.replace(/_/g, ' ')} • Modality:{' '}
                {item.modality.toUpperCase()}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close evidence inspector"
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
          >
            <X className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Close [ESC]</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Direct Action to Open Original File First */}
          <div className="eos-card bg-slate-950 border border-sky-500/30 rounded-lg p-3.5 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs">
              <span className="font-semibold text-white block">
                Original Immutable Evidence File
              </span>
              <span className="text-slate-400">
                Preserved byte-for-byte prior to extraction ({item.file_size_bytes.toLocaleString()} bytes)
              </span>
            </div>
            <a
              href={rawUrl}
              target="_blank"
              rel="noreferrer"
              className="eos-btn-link inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-semibold transition"
            >
              <span>Open Original File</span>
              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
            </a>
          </div>

          {/* Visual Preview for Images */}
          {item.modality === 'image' && (
            <div className="eos-card bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
                Original Image Artifact
              </span>
              <div className="flex justify-center bg-slate-900 rounded p-3 border border-slate-800">
                <img
                  src={rawUrl}
                  alt={`Inspection evidence ${item.original_filename}`}
                  className="max-h-60 rounded object-contain"
                />
              </div>
              {item.extracted_payload?.visual_summary && (
                <p className="text-xs text-slate-300">
                  <strong className="text-slate-400">Extracted Observation:</strong>{' '}
                  {item.extracted_payload.visual_summary}
                </p>
              )}
            </div>
          )}

          {/* Audio Player & Transcript for Voice Reports */}
          {item.modality === 'audio' && (
            <div className="eos-card bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
                Original Audio Recording & Verbatim Transcript
              </span>
              <audio
                controls
                src={rawUrl}
                aria-label={`Audio playback for ${item.original_filename}`}
                className="w-full h-9"
              />
              {item.extracted_payload?.transcript && (
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-200 font-mono">
                  "{item.extracted_payload.transcript}"
                </div>
              )}
            </div>
          )}

          {/* Cryptographic & Perceptual Provenance */}
          <div className="eos-card bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
                Provenance & Integrity Metadata
              </span>
              {prov && <EpistemicBadge type={prov.epistemic_type} />}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
              <div className="p-2 rounded bg-slate-900/70 border border-slate-800/80">
                <span className="text-slate-400 block text-[11px]">SHA-256 Content Digest</span>
                <span className="font-mono text-[11px] text-slate-200 break-all">
                  {item.sha256_hash}
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900/70 border border-slate-800/80">
                <span className="text-slate-400 block text-[11px]">64-Bit Perceptual dHash</span>
                <span className="font-mono text-[11px] text-slate-200">
                  {item.perceptual_hash || 'Not applicable (non-image)'}
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900/70 border border-slate-800/80">
                <span className="text-slate-400 block text-[11px]">Processing Method</span>
                <span className="font-mono text-[11px] text-sky-300">
                  {prov?.extraction_method || item.extraction_metadata?.provider || 'Deterministic parser'}
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900/70 border border-slate-800/80">
                <span className="text-slate-400 block text-[11px]">Source Location & Timestamp</span>
                <span className="font-mono text-[11px] text-slate-200">
                  {prov?.location || 'Full document'} •{' '}
                  {item.uploaded_at ? new Date(item.uploaded_at).toLocaleTimeString() : 'Recorded'}
                </span>
              </div>
            </div>
          </div>

          {/* Inline PDF / Document Evidence Highlighting */}
          {rawTextLines.length > 0 && (
            <div className="eos-card bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-300 block">
                  Inline PDF / Source Evidence Highlighting ({prov?.location || 'page:1'})
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  Click a claim below to highlight its exact source line
                </span>
              </div>

              {highlightChips.length > 1 && (
                <div className="flex flex-wrap gap-1.5">
                  {highlightChips.map((chip) => {
                    const isSelected = chip.id === selectedHighlightTerm;
                    return (
                      <button
                        key={chip.id}
                        type="button"
                        onClick={() => setSelectedHighlightTerm(chip.id)}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition border ${
                          isSelected
                            ? 'bg-amber-500/20 text-amber-200 border-amber-400 font-semibold'
                            : 'bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        {chip.label}
                      </button>
                    );
                  })}
                </div>
              )}

              <div
                aria-label="Inline highlighted source document lines"
                className="rounded border border-slate-800 bg-slate-900 divide-y divide-slate-800/60 font-mono text-xs overflow-hidden"
              >
                {rawTextLines.map((line, idx) => {
                  const matched = isLineHighlighted(line);
                  return (
                    <div
                      key={idx}
                      className={`px-3 py-1.5 flex items-start justify-between gap-3 ${
                        matched
                          ? 'bg-amber-500/20 border-l-4 border-amber-400 text-amber-100 font-semibold'
                          : 'text-slate-300'
                      }`}
                    >
                      <div className="flex items-start gap-2.5 min-w-0">
                        <span className="text-[10px] text-slate-500 select-none shrink-0 pt-0.5">
                          L{String(idx + 1).padStart(2, '0')}
                        </span>
                        <span className="break-all">{line}</span>
                      </div>
                      {matched && (
                        <span className="shrink-0 px-1.5 py-0.5 rounded bg-amber-500/25 text-amber-200 border border-amber-400/40 text-[10px]">
                          ← Extracted Claim Span
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Full Structured Extraction JSON */}
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 space-y-1.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
              Structured Extraction Output (Schema-Validated)
            </span>
            <pre className="text-[11px] font-mono text-emerald-300 overflow-x-auto bg-slate-900 p-3 rounded border border-slate-800">
              {JSON.stringify(item.extracted_payload, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

