"""
MANTIS Investigation Gap Planner & Custody Boundary Engine
Recognizes when a financial trail reaches an Exchange, Custodial Wallet, or Blind Spot.
Instead of silently halting or hallucinating internal movements, it synthesizes
structured Investigation Data Requests and statutory Section 94 BNSS / Section 91 CrPC notice drafts.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from mantis.core.models import CanonicalTransaction, CanonicalEntity, InvestigationDataRequest, EntityKind
from mantis.config import CustodyBoundaryConfig

class InvestigationGapPlanner:
    """
    Identifies custody boundaries and generates actionable statutory data requests.
    """

    def __init__(self, config: Optional[CustodyBoundaryConfig] = None):
        self.config = config or CustodyBoundaryConfig()

    def inspect_boundary(self, case_id: str, terminal_tx: CanonicalTransaction,
                         terminal_entity: CanonicalEntity) -> Optional[InvestigationDataRequest]:
        """
        Evaluates if a terminal transaction hit a custodial boundary (e.g. centralized exchange or P2P escrow).
        If yes, generates an actionable legal request packet.
        """
        is_exchange = False
        institution_name = "Centralized Virtual Digital Asset Service Provider (VASP)"

        # Check known risk tags or display name
        display_lower = terminal_entity.display.lower()
        for tag in self.config.known_exchange_tags:
            if tag in display_lower or any(tag in t.lower() for t in terminal_entity.risk_tags):
                is_exchange = True
                institution_name = tag.capitalize()
                break

        # Check entity kind
        if terminal_entity.kind in [EntityKind.EXCHANGE, EntityKind.SERVICE] or terminal_entity.is_custody_boundary:
            is_exchange = True

        if not is_exchange:
            return None

        # Build formal statutory data request under Section 94 Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023
        asks = [
            "Full Customer Due Diligence (CDD) and verified e-KYC documents (Aadhaar, PAN, Passport)",
            "Complete Internal Deposit Ledger corresponding to on-chain tx / order reference",
            "Off-chain order book matched counterparty details and trading records",
            "Downstream withdrawal logs (Destination blockchain addresses, timestamps, TxIDs)",
            "Registered Login IP access logs with timestamps and device IMEI/fingerprints"
        ]

        legal_draft = f"""
NOTICE UNDER SECTION 94 OF BHARATIYA NAGARIK SURAKSHA SANHITA (BNSS), 2023
(Successor to Section 91 of Code of Criminal Procedure, 1973)

To: Compliance Officer / Nodal Grievance Officer, {institution_name}
Subject: Production of Documents / Records in connection with Cybercrime Investigation Case Ref: {case_id}

Whereas it has been made to appear before me that proceeds of cyber fraud aggregating to {terminal_tx.amount_formatted} 
have arrived at your custodial address / order reference '{terminal_entity.display}' on {terminal_tx.ts_utc.strftime('%d-%b-%Y %H:%M:%S UTC')} 
via Transaction Ref: {terminal_tx.ref or terminal_tx.id}.

You are hereby legally directed to produce forthwith before the undersigned:
1. Complete KYC / Account opening dossier of the registered account holder.
2. Internal trading & ledger logs showing subsequent dispersal or withdrawal of the aforementioned credit.
3. Destination wallet addresses with on-chain TxIDs for any crypto withdrawals executed thereafter.
4. Access audit logs (IP, Device ID, User-Agent) used during the relevant session window.

Take notice that failure to comply with this requisition attracts legal proceedings under Section 223 of BNS, 2023.

Investigating Officer, Cyber Crime Police Station
        """.strip()

        return InvestigationDataRequest(
            id=f"gap_{uuid.uuid4().hex[:10]}",
            case_id=case_id,
            entity_id=terminal_entity.id,
            target_institution=institution_name,
            custody_account_or_wallet=terminal_entity.display,
            unresolved_amount_formatted=terminal_tx.amount_formatted,
            asks=asks,
            statutory_basis="Section 94 BNSS 2023 (Sec 91 CrPC)",
            legal_draft_text=legal_draft,
            urgency="Critical"
        )
