"""
MANTIS Typology & Network Intelligence Engine
Registry of dynamic, configurable detectors for money-laundering patterns.
Every detector outputs supporting transaction IDs, quantitative metrics,
and alternative benign hypotheses.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import networkx as nx
from mantis.core.models import CanonicalTransaction, Episode
from mantis.config import TypologyConfig

class BaseDetector:
    """Abstract base class for all MANTIS typology detectors."""
    pattern_name: str = "base"

    def __init__(self, config: Optional[TypologyConfig] = None):
        self.config = config or TypologyConfig()

    def analyze(self, transactions: List[CanonicalTransaction]) -> List[Episode]:
        raise NotImplementedError

# ---------------------------------------------------------------------------
# 1. RAPID PASS-THROUGH DETECTOR (Layering Mule)
# ---------------------------------------------------------------------------
class RapidPassThroughDetector(BaseDetector):
    pattern_name = "rapid_passthrough"

    def analyze(self, transactions: List[CanonicalTransaction]) -> List[Episode]:
        episodes = []
        # Group inflows and outflows by entity
        inflows: Dict[str, List[CanonicalTransaction]] = {}
        outflows: Dict[str, List[CanonicalTransaction]] = {}

        for tx in transactions:
            inflows.setdefault(tx.dst_id, []).append(tx)
            outflows.setdefault(tx.src_id, []).append(tx)

        for entity_id in set(inflows.keys()).intersection(set(outflows.keys())):
            # Adapter-generated cp_* nodes stand for a transaction/reference pairing,
            # not a verified account that can meaningfully be labeled a pass-through.
            if entity_id.startswith("cp_"):
                continue
            for in_tx in inflows[entity_id]:
                for out_tx in outflows[entity_id]:
                    if out_tx.ts_utc < in_tx.ts_utc:
                        continue
                    dwell_minutes = (out_tx.ts_utc - in_tx.ts_utc).total_seconds() / 60.0
                    drain_ratio = out_tx.amount_minor / in_tx.amount_minor if in_tx.amount_minor > 0 else 0

                    if dwell_minutes <= self.config.rapid_passthrough_max_minutes and (
                        self.config.rapid_passthrough_min_drain <= drain_ratio <= 1.05
                    ):
                        episodes.append(Episode(
                            pattern=self.pattern_name,
                            entity_id=entity_id,
                            confidence=0.95 if dwell_minutes < 10 else 0.85,
                            evidence_tx_ids=[in_tx.id, out_tx.id],
                            metrics={
                                "dwell_time_minutes": round(dwell_minutes, 1),
                                "inflow_minor": in_tx.amount_minor,
                                "outflow_minor": out_tx.amount_minor,
                                "drain_ratio": round(drain_ratio, 2)
                            },
                            benign_hypotheses=[
                                {
                                    "explanation": "Automated payment gateway merchant settlement sweep",
                                    "evaluation": "Check whether account is registered current merchant account or individual savings."
                                }
                            ]
                        ))
        return episodes

# ---------------------------------------------------------------------------
# 2. FAN-OUT DETECTOR (Distribution Smurfing)
# ---------------------------------------------------------------------------
class FanOutDetector(BaseDetector):
    pattern_name = "fan_out"

    def analyze(self, transactions: List[CanonicalTransaction]) -> List[Episode]:
        episodes = []
        outflows_by_src: Dict[str, List[CanonicalTransaction]] = {}
        for tx in transactions:
            outflows_by_src.setdefault(tx.src_id, []).append(tx)

        for src_id, txs in outflows_by_src.items():
            if src_id.startswith("cp_"):
                continue
            if len(txs) < self.config.fan_out_min_degree:
                continue
            # Check time span of outflows
            txs_sorted = sorted(txs, key=lambda t: t.ts_utc)
            time_span_hours = (txs_sorted[-1].ts_utc - txs_sorted[0].ts_utc).total_seconds() / 3600.0

            if time_span_hours <= self.config.fan_out_window_hours:
                episodes.append(Episode(
                    pattern=self.pattern_name,
                    entity_id=src_id,
                    confidence=0.92,
                    evidence_tx_ids=[t.id for t in txs_sorted],
                    metrics={
                        "out_degree": len(txs_sorted),
                        "time_span_hours": round(time_span_hours, 2),
                        "total_volume_minor": sum(t.amount_minor for t in txs_sorted)
                    },
                    benign_hypotheses=[
                        {
                            "explanation": "Corporate payroll disbursement or vendor batch payments",
                            "evaluation": "Verify if disbursements match registered employee roster."
                        }
                    ]
                ))
        return episodes

# ---------------------------------------------------------------------------
# 3. STRUCTURING DETECTOR (Smurfing Under Reporting Limits)
# ---------------------------------------------------------------------------
class StructuringDetector(BaseDetector):
    pattern_name = "structuring"

    def analyze(self, transactions: List[CanonicalTransaction]) -> List[Episode]:
        episodes = []
        threshold = self.config.structuring_threshold_inr
        window_lower = threshold * (1.0 - self.config.structuring_window_pct)

        for tx in transactions:
            if tx.asset != "INR":
                continue
            val_inr = tx.amount_minor / 100.0
            if window_lower <= val_inr < threshold:
                proximity_pct = round((threshold - val_inr) / threshold * 100.0, 1)
                episodes.append(Episode(
                    pattern=self.pattern_name,
                    entity_id=tx.src_id,
                    confidence=0.88,
                    evidence_tx_ids=[tx.id],
                    metrics={
                        "amount_inr": val_inr,
                        "threshold_inr": threshold,
                        "proximity_under_threshold_pct": proximity_pct
                    },
                    benign_hypotheses=[
                        {
                            "explanation": "Standard fixed subscription or recurring professional service contract",
                            "evaluation": "Review whether amount coincides with standard vendor price list."
                        }
                    ]
                ))
        return episodes

# ---------------------------------------------------------------------------
# 4. PEEL CHAIN DETECTOR (Blockchain Layering)
# ---------------------------------------------------------------------------
class PeelChainDetector(BaseDetector):
    pattern_name = "peel_chain"

    def analyze(self, transactions: List[CanonicalTransaction]) -> List[Episode]:
        episodes = []
        # Applies to on-chain transfers (TRON, ETH) with 2 outbound branches: ~90% forward and ~10% residue
        outflows_by_src: Dict[str, List[CanonicalTransaction]] = {}
        for tx in transactions:
            if tx.rail in ["TRON", "ETH"]:
                outflows_by_src.setdefault(tx.src_id, []).append(tx)

        for src_id, txs in outflows_by_src.items():
            if len(txs) == 2:
                sorted_txs = sorted(txs, key=lambda t: t.amount_minor, reverse=True)
                total = sum(t.amount_minor for t in sorted_txs)
                if total > 0:
                    main_ratio = sorted_txs[0].amount_minor / total
                    if self.config.peel_chain_min_ratio <= main_ratio <= self.config.peel_chain_max_ratio:
                        episodes.append(Episode(
                            pattern=self.pattern_name,
                            entity_id=src_id,
                            confidence=0.91,
                            evidence_tx_ids=[t.id for t in sorted_txs],
                            metrics={
                                "forward_ratio": round(main_ratio, 3),
                                "peeled_residue_minor": sorted_txs[1].amount_minor
                            },
                            benign_hypotheses=[
                                {
                                    "explanation": "Standard HD crypto wallet change address output",
                                    "evaluation": "Compare with typical non-custodial wallet change generation behaviors."
                                }
                            ]
                        ))
        return episodes

# ---------------------------------------------------------------------------
# 5. MULTI-VICTIM CONVERGENCE DETECTOR (MANTIS 2.0 Network Motif)
# ---------------------------------------------------------------------------
class MultiVictimConvergenceDetector:
    """
    Identifies common recipient hubs receiving laundered proceeds from multiple complaints.
    """
    pattern_name = "multi_victim_convergence"

    def analyze_convergence(self, convergent_map: Dict[str, List[str]],
                            transactions: List[CanonicalTransaction]) -> List[Episode]:
        episodes = []
        for hub_entity, complaint_ids in convergent_map.items():
            if len(complaint_ids) >= 2:
                # Find transactions leading into this hub
                relevant_txs = [t.id for t in transactions if t.dst_id == hub_entity]
                episodes.append(Episode(
                    pattern=self.pattern_name,
                    entity_id=hub_entity,
                    confidence=0.98,
                    evidence_tx_ids=relevant_txs,
                    metrics={
                        "converging_complaints_count": len(complaint_ids),
                        "complaint_refs": complaint_ids
                    },
                    benign_hypotheses=[
                        {
                            "explanation": "Shared merchant, utility provider, or popular retail platform",
                            "evaluation": "Examine if hub is registered public entity or private individual mule."
                        }
                    ]
                ))
        return episodes

# Detector Registry
ALL_DETECTORS = [
    RapidPassThroughDetector,
    FanOutDetector,
    StructuringDetector,
    PeelChainDetector
]
