"""
MANTIS Dynamic Configuration Framework
Adheres to Engineering Philosophy: "Hardcode the framework, not the investigation logic."
All thresholds, windows, FX tolerances, and detection parameters are runtime-configurable.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class TracerConfig:
    hop_cap: int = 10
    dust_floor_minor: int = 10000              # e.g., ₹100.00 (in paise)
    max_window_hours: float = 72.0             # Flow continuity window
    tie_policy: str = "optimistic"             # optimistic vs pessimistic

@dataclass
class SeamConfig:
    p2p_window_hours: float = 2.0              # Max time elapsed between bank debit and crypto credit
    fx_tolerance_pct: float = 3.5              # Max acceptable deviation from market FX rate
    default_inr_usdt_rate: float = 90.0        # Baseline benchmark rate
    weight_time: float = 0.40                  # Temporal proximity weight in affiliation scoring
    weight_value: float = 0.45                 # Value parity weight in affiliation scoring
    weight_reputation: float = 0.15            # Counterparty risk weight
    min_match_confidence: float = 0.70         # Threshold to emit candidate seam match

@dataclass
class TypologyConfig:
    rapid_passthrough_max_minutes: float = 30.0
    rapid_passthrough_min_drain: float = 0.90
    fan_out_min_degree: int = 5
    fan_out_window_hours: float = 2.0
    fan_in_min_degree: int = 5
    fan_in_sweep_ratio: float = 0.85
    structuring_threshold_inr: float = 50000.0  # PMLA / Cash transaction threshold
    structuring_window_pct: float = 0.10        # e.g. within 10% below threshold (₹45,000 - ₹49,999)
    peel_chain_min_ratio: float = 0.88          # Forward ratio
    peel_chain_max_ratio: float = 0.99
    dormant_min_days: int = 90
    dormant_burst_count: int = 5

@dataclass
class CustodyBoundaryConfig:
    """Detects Centralized Exchanges, Custodial Wallets, and Payment Gateways."""
    known_exchange_tags: List[str] = field(default_factory=lambda: [
        "binance", "wazirx", "coindcx", "krypton", "huione", "okx", "bybit", "kucoin"
    ])
    exchange_like_in_degree: int = 50          # Address receiving from 50+ unrelated senders
    exchange_like_out_ratio: float = 0.98      # Sweeps 98%+ to a master consolidation hub

@dataclass
class MantisConfig:
    tracer: TracerConfig = field(default_factory=TracerConfig)
    seam: SeamConfig = field(default_factory=SeamConfig)
    typology: TypologyConfig = field(default_factory=TypologyConfig)
    custody: CustodyBoundaryConfig = field(default_factory=CustodyBoundaryConfig)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MantisConfig":
        tracer = TracerConfig(**data.get("tracer", {}))
        seam = SeamConfig(**data.get("seam", {}))
        typology = TypologyConfig(**data.get("typology", {}))
        custody = CustodyBoundaryConfig(**data.get("custody", {}))
        return cls(tracer=tracer, seam=seam, typology=typology, custody=custody)
