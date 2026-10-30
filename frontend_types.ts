/**
 * MANTIS Frontend Data Contracts & Types
 * Pinned TypeScript definitions matching the backend schema and Cytoscape.js model.
 * Copy into: frontend/src/types/mantis.ts
 */

export type Rail = 'UPI' | 'IMPS' | 'NEFT' | 'RTGS' | 'CHEQUE' | 'ATM' | 'CASH' | 'ETH' | 'TRON' | 'OTHER';

export type EdgeClass = 'flow' | 'association' | 'seam';

export type LinkLabel = 'confirmed' | 'inferred' | 'possible' | 'unknown';

export type EntityKind = 'bank_account' | 'wallet' | 'exchange' | 'service' | 'cash_exit' | 'unknown';

export interface MantisNodeData {
  id: string;
  label: string;
  sublabel?: string;
  kind: EntityKind;
  rail?: Rail;
  risk_tags: string[];
  balance: string;
  taint_residual: string;
  is_victim?: boolean;
  is_freeze_target?: boolean;
}

export interface MantisEdgeData {
  id: string;
  source: string;
  target: string;
  edge_class: EdgeClass;
  label: LinkLabel;
  amount: string;
  rail?: string;
  ref?: string;
  score?: number; // 0.0 to 1.0 (for inferred/seam edges)
  reason: string;
}

export interface CytoscapeElement {
  data: MantisNodeData | MantisEdgeData;
}

export interface CytoscapeGraphPayload {
  elements: {
    nodes: Array<{ data: MantisNodeData }>;
    edges: Array<{ data: MantisEdgeData }>;
  };
  recovery_summary: {
    total_lost_inr: string;
    recoverable_fiat_inr: string;
    recoverable_crypto_usdt: string;
    action_targets: Array<{
      target: string;
      account?: string;
      wallet?: string;
      action: string;
      urgency: 'Critical' | 'High' | 'Medium' | 'Low';
    }>;
  };
}

export interface TypologyEpisode {
  pattern: 'fan_out' | 'fan_in' | 'rapid_passthrough' | 'peel_chain' | 'structuring' | 'circular' | 'dormant_activation';
  entity_id: string;
  confidence: number;
  evidence_tx_ids: string[];
  metrics: Record<string, any>;
  benign_hypotheses: Array<{
    explanation: string;
    evaluation: string;
  }>;
}

export interface Section63Certificate {
  case_number: string;
  generated_at: string;
  investigating_officer: string;
  documents: Array<{
    filename: string;
    sha256: string;
    bytes: number;
    corroboration: string;
  }>;
  part_a_certified: boolean;
  part_b_expert_signoff: boolean;
}
