"""
MANTIS Typology Detector Plugin Architecture
Standardized interface for all 6 money-laundering pattern detectors.
Guarantees that every detector returns:
1. Supporting transaction IDs (Evidence)
2. A confidence score
3. An innocent/benign alternative explanation (Court-Defensibility)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Episode:
    pattern: str                           # e.g., 'rapid_passthrough', 'fan_out', 'structuring'
    entity_id: str                         # The primary account or wallet involved
    confidence: float                      # 0.0 to 1.0
    evidence_tx_ids: List[str]             # Must reference exact transaction IDs in DB
    metrics: Dict[str, Any]                # Quantitative metrics (e.g. {'dwell_time_mins': 5.2, 'drain_ratio': 0.98})
    benign_hypotheses: List[Dict[str, str]]# Array of {'explanation': '...', 'likelihood': 'medium'}

class BaseDetector(ABC):
    """Abstract Base Class for all MANTIS Typology Detectors."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    @abstractmethod
    def detect(self, graph_data: Dict[str, Any]) -> List[Episode]:
        """
        Analyzes the reconstructed money trail graph.
        Returns a list of detected pattern episodes.
        """
        pass

# ---------------------------------------------------------------------------
# EXAMPLE DETECTOR 1: RAPID PASS-THROUGH (Dwell Time < T, Balance Drain > 1 - eps)
# ---------------------------------------------------------------------------
class RapidPassThroughDetector(BaseDetector):
    def detect(self, graph_data: Dict[str, Any]) -> List[Episode]:
        episodes = []
        max_dwell_minutes = self.config.get("max_dwell_minutes", 30)
        min_drain_ratio = self.config.get("min_drain_ratio", 0.90)
        
        # Analyze nodes in graph_data
        # In production, this computes (t_out - t_in) and (sum_out / sum_in) per account
        # Demo simulation for Mule 1 (Ramesh Kumar):
        episodes.append(Episode(
            pattern="rapid_passthrough",
            entity_id="node_mule1",
            confidence=0.96,
            evidence_tx_ids=["edge_1", "edge_2a", "edge_2b"],
            metrics={
                "inflow_minor": 10000000,
                "outflow_minor": 10000000,
                "dwell_time_minutes": 5.2,
                "drain_ratio": 1.0
            },
            benign_hypotheses=[
                {
                    "explanation": "Automated e-commerce payment gateway merchant settlement sweep",
                    "evaluation": "Unlikely: Account kind is individual savings account, not a registered corporate current account."
                }
            ]
        ))
        return episodes

# ---------------------------------------------------------------------------
# EXAMPLE DETECTOR 2: STRUCTURING (Smurfing Under Regulatory Reporting Caps)
# ---------------------------------------------------------------------------
class StructuringDetector(BaseDetector):
    def detect(self, graph_data: Dict[str, Any]) -> List[Episode]:
        episodes = []
        # Indian PMLA & Cash Transaction Reporting threshold is ₹50,000 / ₹10,00,000
        # Flag payments clustered in [₹45,000, ₹49,999]
        episodes.append(Episode(
            pattern="structuring",
            entity_id="node_mule2",
            confidence=0.89,
            evidence_tx_ids=["edge_3_p2p"],
            metrics={
                "tx_amount_inr": 49500.0,
                "threshold_inr": 50000.0,
                "proximity_pct": 1.0  # within 1% below reporting threshold
            },
            benign_hypotheses=[
                {
                    "explanation": "Fixed-value service contract or uniform product subscription payment",
                    "evaluation": "Possible, but counterparty is a high-volume P2P crypto trader."
                }
            ]
        ))
        return episodes
