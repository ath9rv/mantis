"""Deterministic case-record query engine with source IDs and limitations."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
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
        inr_rows = [t for t in self.transactions if t.asset.upper() == "INR"]
        usdt_rows = [t for t in self.transactions if t.asset.upper() == "USDT"]
        total_inr = sum(
            (Decimal(t.amount_minor) / (Decimal(10) ** t.decimals) for t in inr_rows), Decimal(0)
        )
        total_usdt = sum(
            (Decimal(t.amount_minor) / (Decimal(10) ** t.decimals) for t in usdt_rows), Decimal(0)
        )
        usdt_places = max((t.decimals for t in usdt_rows), default=6)
        ordered = sorted(self.transactions, key=lambda t: (t.ts_utc, t.id))
        return {
            "answer": (
                f"Case records contain {len(self.transactions)} transfer rows, {len(self.flow_edges)} stored flow edges, "
                f"{len(self.seam_edges)} candidate cross-rail links, and {len(self.episodes)} heuristic indicators. "
                f"Gross observed row volume: ₹{total_inr:,.2f} and {total_usdt:,.{usdt_places}f} USDT. "
                "Gross volume counts each recorded movement and may count the same value again at later hops."
            ),
            "cited_tx_ids": [t.id for t in ordered[:10]],
            "confidence": "Summary of stored records",
            "limitations": "Source completeness is unknown. Gross row volume is not unique principal, loss, balance, or recoverable value."
        }

    def _query_gaps(self) -> Dict[str, Any]:
        if not self.gap_requests:
            return {
                "answer": "No custody-boundary request is stored in the currently available case records.",
                "cited_tx_ids": [],
                "confidence": "No stored request",
                "limitations": "Absence of a stored request does not establish that the trail is complete."
            }

        priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        requests = sorted(
            self.gap_requests,
            key=lambda item: (priority.get(item.urgency.casefold(), 4), item.id),
        )[:5]
        summaries = [
            f"{req.target_institution} / {req.custody_account_or_wallet}: {req.unresolved_amount_formatted} ({req.urgency})"
            for req in requests
        ]
        req = requests[0]
        return {
            "answer": (
                f"Stored review requests ({len(self.gap_requests)} total; showing {len(requests)}): "
                f"{'; '.join(summaries)}. For the highest-priority draft, review the proposed basis "
                f"({req.statutory_basis}) and requested records: {', '.join(req.asks[:3])}."
            ),
            "gap_request_id": req.id,
            "statutory_basis": req.statutory_basis,
            "cited_tx_ids": [],
            "confidence": "Stored review draft",
            "limitations": "This is not a legal notice. Authority, relevance, scope, and procedure require authorized review."
        }

    def _query_patterns(self) -> Dict[str, Any]:
        if not self.episodes:
            return {
                "answer": "No typology episode is stored in the currently available case records.",
                "cited_tx_ids": [],
                "confidence": "No stored episode",
                "limitations": "Analysis may not have been run, and absence of a stored episode does not clear activity."
            }

        episodes = sorted(self.episodes, key=lambda ep: (-ep.confidence, ep.pattern, ep.entity_id))[:5]
        summaries = []
        citations = []
        for ep in episodes:
            alt = ep.benign_hypotheses[0]["explanation"] if ep.benign_hypotheses else "No alternative recorded"
            summaries.append(
                f"{ep.pattern} at {ep.entity_id} (heuristic score {ep.confidence:.3f}/1; "
                f"evidence {', '.join(ep.evidence_tx_ids)}; alternative: {alt})"
            )
            citations.extend(ep.evidence_tx_ids)
        return {
            "answer": (
                f"Stored heuristic indicators ({len(self.episodes)} total; showing {len(episodes)}): "
                f"{'; '.join(summaries)}."
            ),
            "cited_tx_ids": list(dict.fromkeys(citations)),
            "confidence": "Uncalibrated heuristic indicators",
            "limitations": "Heuristic score is not a calibrated probability. Indicator only; does not establish criminal guilt."
        }

    def _query_largest_transactions(self) -> Dict[str, Any]:
        # Minor units across different assets are not comparable; rank each asset separately.
        by_asset: Dict[str, List[CanonicalTransaction]] = {}
        for tx in self.transactions:
            by_asset.setdefault(tx.asset, []).append(tx)
        sorted_txs = [
            tx
            for asset_txs in by_asset.values()
            for tx in sorted(asset_txs, key=lambda item: item.amount_minor, reverse=True)[:3]
        ]
        summaries = [f"{t.amount_formatted} via {t.rail.value} (ID: {t.id}, Ref: {t.ref or 'N/A'})" for t in sorted_txs]
        return {
            "answer": f"The largest observed movements per asset (up to 3 each) are: {'; '.join(summaries)}." if summaries else "No transactions found.",
            "cited_tx_ids": [t.id for t in sorted_txs],
            "confidence": "Exact Database Record",
            "limitations": "Assets are ranked separately; nominal amounts across different assets are not directly comparable."
        }

    def _query_crypto_seam(self) -> Dict[str, Any]:
        if not self.seam_edges:
            return {
                "answer": "No fiat-to-crypto seam match is stored in the currently available case records.",
                "cited_tx_ids": [],
                "confidence": "None",
                "limitations": "No stored candidate may mean missing inputs, no investigator-supplied FX rate, or no pair met configured rules."
            }

        seams = sorted(self.seam_edges, key=lambda item: (-item.score, item.delta_t_seconds, item.id))[:5]
        summaries = [f"{seam.reason} (solver score {seam.score:.3f}/1; label {seam.label.value})" for seam in seams]
        return {
            "answer": (
                f"Stored cross-rail candidates ({len(self.seam_edges)} total; showing {len(seams)}): "
                f"{'; '.join(summaries)}."
            ),
            "cited_tx_ids": list(dict.fromkeys(
                transfer_id for seam in seams for transfer_id in (seam.fiat_transfer_id, seam.chain_transfer_id)
            )),
            "confidence": "Uncalibrated solver ranking",
            "limitations": "These are candidates from configured rules, not identity or payment proof; request independent provider records."
        }

    def _query_time_window(self, question: str) -> Dict[str, Any]:
        sorted_txs = sorted(self.transactions, key=lambda t: t.ts_utc)
        if not sorted_txs:
            return {"answer": "No transactions found.", "cited_tx_ids": [], "confidence": "Zero", "limitations": ""}

        match = re.search(r"\bwithin\s+(\d+(?:\.\d+)?)\s*(minutes?|mins?|hours?|hrs?)\b", question.lower())
        window_minutes = 30.0
        if match:
            window_minutes = float(match.group(1)) * (60 if match.group(2).startswith(("hour", "hr")) else 1)

        seed = sorted_txs[0]
        # Find records within the requested window of the earliest dated transaction.
        window_txs = [
            t for t in sorted_txs
            if t.ts_precision != "date" and seed.ts_precision != "date"
            and 0 <= (t.ts_utc - seed.ts_utc).total_seconds() <= window_minutes * 60
        ]
        return {
            "answer": f"Found {len(window_txs)} transactions within {window_minutes:g} minutes of the earliest dated transfer at {seed.ts_utc.strftime('%H:%M:%S UTC')}.",
            "cited_tx_ids": [t.id for t in window_txs],
            "confidence": "Timestamp comparison",
            "limitations": "Statements with date-only precision are excluded from sub-hourly queries."
        }

    def _query_evidence(self, question: str) -> Dict[str, Any]:
        requested = re.findall(r"\b(?:tx|chain)_[a-z0-9_-]+\b|\b[0-9a-f]{64}\b", question.lower())
        edges = [edge for edge in self.flow_edges if edge.evidence_reason]
        if requested:
            wanted = set(requested)
            edges = [edge for edge in edges if edge.transfer.id.lower() in wanted or (edge.transfer.ref or "").lower() in wanted]
        edges = sorted(edges, key=lambda edge: (edge.transfer.ts_utc, edge.transfer.id))[:10]
        if not edges:
            return {
                "answer": "No matching stored flow evidence was found for that reference." if requested else "No explicit flow-edge evidence is stored.",
                "cited_tx_ids": [], "confidence": "Stored-record lookup",
                "limitations": "A missing match does not establish that a transfer did not occur."
            }
        summaries = [
            f"{edge.transfer.id}: {edge.source} → {edge.target}; {edge.evidence_reason}; source label {edge.label.value}"
            for edge in edges
        ]
        return {
            "answer": f"Stored flow evidence ({len(edges)} rows): {'; '.join(summaries)}.",
            "cited_tx_ids": [edge.transfer.id for edge in edges],
            "confidence": "Stored-record lookup",
            "limitations": "The source label describes record corroboration, not proof of beneficial ownership or fund attribution."
        }
