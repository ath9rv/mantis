"""
MANTIS Canonical Domain Models
Defines core data structures for multi-rail financial intelligence.
Zero hardcoded assumptions. Supports cross-rail entities, tripartite edges,
probabilistic links, custody boundaries, and investigation gap requests.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any, Optional

class Rail(str, Enum):
    UPI = "UPI"
    IMPS = "IMPS"
    NEFT = "NEFT"
    RTGS = "RTGS"
    CHEQUE = "CHEQUE"
    ATM = "ATM"
    CASH = "CASH"
    ETH = "ETH"
    TRON = "TRON"
    OTHER = "OTHER"

class EdgeClass(str, Enum):
    FLOW = "flow"               # Financial transfer of funds
    ASSOCIATION = "association" # Entity resolution, co-ownership, shared phone/IP
    SEAM = "seam"               # Fiat-to-Crypto P2P / OTC bridge match

class LinkLabel(str, Enum):
    CONFIRMED = "confirmed"     # Two-sided corroboration or deterministic binding
    INFERRED = "inferred"       # High-confidence multi-signal match (e.g., Fellegi-Sunter / Seam solver)
    POSSIBLE = "possible"       # Single-signal match or date-only ambiguous link
    UNKNOWN = "unknown"         # Missing transaction hop or unseen intermediary

class EntityKind(str, Enum):
    BANK_ACCOUNT = "bank_account"
    WALLET = "wallet"
    EXCHANGE = "exchange"
    SERVICE = "service"
    CASH_EXIT = "cash_exit"
    UNKNOWN = "unknown"

@dataclass
class CanonicalEntity:
    id: str
    kind: EntityKind
    display: str
    observed: bool = True
    risk_tags: List[str] = field(default_factory=list)
    identifiers: Dict[str, str] = field(default_factory=dict) # e.g. {'account_no': '...', 'ifsc': '...', 'vpa': '...'}
    is_custody_boundary: bool = False                          # True if exchange, pooled wallet, or payment aggregator
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CanonicalTransaction:
    id: str
    case_id: str
    rail: Rail
    src_id: str
    dst_id: str
    asset: str                                    # INR, USDT, ETH, etc.
    amount_minor: int                             # Integer minor units (e.g. Paise for INR, 6 decimals for USDT)
    decimals: int                                 # 2 for INR, 6 for USDT, 18 for ETH
    ts_utc: datetime
    ts_precision: str = "minute"                  # 'exact', 'minute', 'date'
    ref: Optional[str] = None                     # 12-digit UPI RRN / UTR / Blockchain Tx Hash
    ref_kind: Optional[str] = None                # 'rrn', 'utr', 'tx_hash'
    corroboration: int = 1                        # Number of independent source documents confirming this
    raw_unmapped_data: Dict[str, Any] = field(default_factory=dict) # Preserves unmapped raw columns
    source_doc_hash: Optional[str] = None

    @property
    def amount_formatted(self) -> str:
        val = Decimal(self.amount_minor) / (Decimal(10) ** self.decimals)
        if self.asset == "INR":
            return f"₹{val:,.2f}"
        return f"{val:,.{min(self.decimals, 4)}f} {self.asset}"

@dataclass
class FlowEdge:
    id: str
    source: str
    target: str
    transfer: CanonicalTransaction
    label: LinkLabel = LinkLabel.CONFIRMED
    evidence_reason: str = ""

@dataclass
class AssocEdge:
    id: str
    entity_a: str
    entity_b: str
    method: str                                   # e.g., 'splink_probabilistic_linkage', 'shared_phone'
    score: float = 0.0                            # 0.0 to 1.0
    label: LinkLabel = LinkLabel.INFERRED
    signals: List[Dict[str, Any]] = field(default_factory=list)
    counter_evidence: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class SeamEdge:
    id: str
    fiat_transfer_id: str
    chain_transfer_id: str
    source_entity: str
    target_entity: str
    score: float
    label: LinkLabel = LinkLabel.INFERRED
    delta_t_seconds: int = 0
    inr_amount_minor: int = 0
    usdt_amount_minor: int = 0
    implied_rate: float = 0.0
    deviation_pct: float = 0.0
    assigned_vasp: Optional[str] = None
    reason: str = ""

@dataclass
class Episode:
    pattern: str
    entity_id: str
    confidence: float
    evidence_tx_ids: List[str]
    metrics: Dict[str, Any]
    benign_hypotheses: List[Dict[str, str]]

@dataclass
class InvestigationDataRequest:
    """Output of the Investigation Gap Planner when hitting custody or jurisdiction boundaries."""
    id: str
    case_id: str
    entity_id: str
    target_institution: str                       # e.g., 'WazirX India', 'Binance Ltd', 'HDFC Bank'
    custody_account_or_wallet: str
    unresolved_amount_formatted: str
    asks: List[str]                               # e.g. ['KYC details', 'Deposit ledger', 'Withdrawal tx hashes', 'IP logs']
    statutory_basis: str                          # e.g. 'Section 94 BNSS 2023 / Section 91 CrPC'
    legal_draft_text: str
    urgency: str                                  # 'Critical', 'High', 'Medium'
    status: str = "open"

@dataclass
class EntityProfile:
    """Entity 360: Comprehensive Intelligence Profile for an Account, Wallet, or Service."""
    entity_id: str
    kind: EntityKind
    display: str
    first_observed: Optional[datetime] = None
    last_observed: Optional[datetime] = None
    total_received_minor: int = 0
    total_sent_minor: int = 0
    transaction_count: int = 0
    connected_entity_ids: List[str] = field(default_factory=list)
    associated_cases: List[str] = field(default_factory=list)
    detected_patterns: List[str] = field(default_factory=list)
    is_custody_boundary: bool = False
    open_leads_count: int = 0
