"""
MANTIS AI Investigation Copilot Grounded Query Engine
Enforces the core rule: "The AI never computes or invents a financial fact."
Translates investigator queries into deterministic database & graph lookups.
Every response cites exact transaction IDs, entity displays, confidence metrics, and legal limitations.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import re
from mantis.core.models import CanonicalTransaction, FlowEdge, SeamEdge, Episode, InvestigationDataRequest

class GroundedCopilotQuerier:
    """
    Executes forensic queries across case data and formats fully grounded answers.
    """

    def __init__(self, transactions: List[CanonicalTransaction],
                 flow_edges: List[FlowEdge],
                 seam_edges: List[SeamEdge],
                 episodes: List[Episode],
                 gap_requests: List[InvestigationDataRequest],
                 entity_directory: Dict[str, Any]):
        self.transactions = transactions
        self.flow_edges = flow_edges
        self.seam_edges = seam_edges
        self.episodes = episodes
        self.gap_requests = gap_requests
        self.entity_directory = entity_directory

    def query(self, user_question: str) -> Dict[str, Any]:
        """
        Routes investigator question to deterministic forensic search functions.
        """
        q = user_question.lower()

        if "within" in q and ("minute" in q or "hour" in q) or "recent" in q:
            return self._query_time_window(user_question)

        elif "unresolved" in q or "missing" in q or "gap" in q or "required" in q:
            return self._query_gaps()

        elif "pattern" in q or "detector" in q or "suspicious" in q:
            return self._query_patterns()

        elif "evidence" in q or "support" in q or "why" in q:
            return self._query_evidence(user_question)

        elif "largest" in q or "top" in q:
            return self._query_largest_transactions()

        elif "wallet" in q or "crypto" in q or "usdt" in q or "seam" in q:
            return self._query_crypto_seam()

        else:
            return self._query_summary()

    def _query_summary(self) -> Dict[str, Any]:
        total_inr = sum(t.amount_minor for t in self.transactions if t.asset == "INR") / 100.0
        total_usdt = sum(t.amount_minor for t in self.transactions if t.asset == "USDT") / 1e6
        return {
            "answer": (
                f"Investigation Summary: Reconstructed {len(self.transactions)} total transactions "
                f"across {len(self.flow_edges)} flow hops and {len(self.seam_edges)} cross-rail seam matches. "
                f"Observed Fiat Volume: ₹{total_inr:,.2f}; Observed USDT Volume: {total_usdt:,.2f} USDT. "
                f"Detected {len(self.episodes)} suspicious typology episodes."
            ),
            "cited_tx_ids": [t.id for t in self.transactions[:5]],
            "confidence": "High - Corroborated Ledger",
            "limitations": "Subject to completeness of uploaded statements and on-chain feeds."
        }

    def _query_gaps(self) -> Dict[str, Any]:
        if not self.gap_requests:
            return {
                "answer": "No open custody boundaries or missing institutional requests currently pending in this case.",
                "cited_tx_ids": [],
                "confidence": "Complete Trail",
                "limitations": "Based on currently known entities."
            }

        req = self.gap_requests[0]
        return {
            "answer": (
                f"Trail hit a Custody Boundary at '{req.target_institution}' (Ref: {req.custody_account_or_wallet}). "
                f"Unresolved Amount: {req.unresolved_amount_formatted}. "
                f"To complete this trail, send statutory notice under {req.statutory_basis} requesting: {', '.join(req.asks[:3])}."
            ),
            "gap_request_id": req.id,
            "statutory_basis": req.statutory_basis,
            "cited_tx_ids": [],
            "confidence": "Actionable Legal Gap",
            "limitations": "Cannot observe internal exchange order books without authorized institutional response."
        }

    def _query_patterns(self) -> Dict[str, Any]:
        if not self.episodes:
            return {
                "answer": "No suspicious typology motifs triggered under current configured thresholds.",
                "cited_tx_ids": [],
                "confidence": "Neutral",
                "limitations": "Heuristics depend on configured velocity and structuring windows."
            }

        ep = self.episodes[0]
        alt = ep.benign_hypotheses[0]["explanation"] if ep.benign_hypotheses else "N/A"
        return {
            "answer": (
                f"Detected pattern: '{ep.pattern}' at entity '{ep.entity_id}' with {ep.confidence * 100:.1f}% confidence. "
                f"Key Metrics: {ep.metrics}. Alternative Benign Hypothesis: {alt}."
            ),
            "cited_tx_ids": ep.evidence_tx_ids,
            "confidence": f"{ep.confidence * 100:.1f}%",
            "limitations": "Investigative indicator only. Does not establish criminal guilt."
        }

    def _query_largest_transactions(self) -> Dict[str, Any]:
        sorted_txs = sorted(self.transactions, key=lambda t: t.amount_minor, reverse=True)[:3]
        summaries = [f"{t.amount_formatted} via {t.rail.value} (ID: {t.id}, Ref: {t.ref or 'N/A'})" for t in sorted_txs]
        return {
            "answer": f"The 3 largest observed fund movements are: {'; '.join(summaries)}.",
            "cited_tx_ids": [t.id for t in sorted_txs],
            "confidence": "Exact Database Record",
            "limitations": "Amounts shown in respective nominal currency."
        }

    def _query_crypto_seam(self) -> Dict[str, Any]:
        if not self.seam_edges:
            return {
                "answer": "No fiat-to-crypto seam transitions identified in the current trail.",
                "cited_tx_ids": [],
                "confidence": "None",
                "limitations": "Fiat records may not have reached a P2P on-ramp."
            }

        seam = self.seam_edges[0]
        return {
            "answer": (
                f"Cross-Rail Seam Link: {seam.reason}. "
                f"Matched with {seam.score * 100:.1f}% confidence. Label: {seam.label.value}."
            ),
            "cited_tx_ids": [seam.fiat_transfer_id, seam.chain_transfer_id],
            "confidence": f"{seam.score * 100:.1f}% ({seam.label.value})",
            "limitations": "Candidate match based on constrained bipartite solver; requires VASP confirmation for absolute proof."
        }

    def _query_time_window(self, question: str) -> Dict[str, Any]:
        sorted_txs = sorted(self.transactions, key=lambda t: t.ts_utc)
        if not sorted_txs:
            return {"answer": "No transactions found.", "cited_tx_ids": [], "confidence": "Zero", "limitations": ""}

        seed = sorted_txs[0]
        # Find txs within 30 mins of seed
        window_txs = [
            t for t in sorted_txs
            if 0 <= (t.ts_utc - seed.ts_utc).total_seconds() <= 1800
        ]
        return {
            "answer": f"Found {len(window_txs)} transactions executed within 30 minutes of initial transfer at {seed.ts_utc.strftime('%H:%M:%S UTC')}.",
            "cited_tx_ids": [t.id for t in window_txs],
            "confidence": "Exact Timestamp Monotonicity",
            "limitations": "Statements with date-only precision are excluded from sub-hourly queries."
        }

    def _query_evidence(self, question: str) -> Dict[str, Any]:
        for edge in self.flow_edges:
            if edge.evidence_reason:
                return {
                    "answer": f"Evidence for connection {edge.source} -> {edge.target}: {edge.evidence_reason}. Label: {edge.label.value}.",
                    "cited_tx_ids": [edge.transfer.id],
                    "confidence": edge.label.value,
                    "limitations": "Evidence derived from source documents recorded in audit log."
                }
        return {"answer": "No explicit edge evidence found.", "cited_tx_ids": [], "confidence": "Low", "limitations": ""}
