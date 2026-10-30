"""
MANTIS Investigation Gap Planner & Custody Boundary Engine
Recognizes when a financial trail reaches an Exchange, Custodial Wallet, or Blind Spot.
Instead of silently halting or hallucinating internal movements, it synthesizes
structured requests for later review by an authorized officer and counsel.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from mantis.core.models import CanonicalTransaction, CanonicalEntity, InvestigationDataRequest, EntityKind
from mantis.config import CustodyBoundaryConfig

class InvestigationGapPlanner:
    """
    Identifies custody boundaries and drafts requests for authorized review.
    """

    def __init__(self, config: Optional[CustodyBoundaryConfig] = None):
        self.config = config or CustodyBoundaryConfig()

    def inspect_boundary(self, case_id: str, terminal_tx: CanonicalTransaction,
                         terminal_entity: CanonicalEntity) -> Optional[InvestigationDataRequest]:
        """
        Evaluates if a terminal transaction hit a custodial boundary (e.g. centralized exchange or P2P escrow).
        If yes, generates a non-legal draft request packet.
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

        asks = [
            "Records sufficient to identify the account associated with the specified transaction, subject to lawful authority and data minimization",
            "Deposit ledger entries corresponding to the specified transaction reference and time window",
            "Relevant order and counterparty records for the specified transaction",
            "Subsequent withdrawal records linked to the specified deposit, including destination address and transaction reference where available",
            "Relevant access logs for the specified time window, where lawfully obtainable and necessary",
        ]

        legal_draft = f"""
DRAFT RECORDS REQUEST — AUTHORIZED LEGAL REVIEW REQUIRED
Proposed statutory basis: To be confirmed by the issuing authority and legal counsel.

To: Compliance Officer / Nodal Grievance Officer, {institution_name}
Subject: Production of Documents / Records in connection with Cybercrime Investigation Case Ref: {case_id}

The available case records indicate a transfer of {terminal_tx.amount_formatted} associated with
'{terminal_entity.display}' on {terminal_tx.ts_utc.strftime('%d-%b-%Y %H:%M:%S UTC')} (reference: {terminal_tx.ref or terminal_tx.id}).
This is an investigative lead and does not, by itself, establish the source or ownership of funds.

Please review whether the records listed below may be requested under the authority and process applicable to this case:
{chr(10).join(f'- {ask}' for ask in asks)}

This draft is not a legal notice. Confirm jurisdiction, statutory authority, scope, service method,
retention period, and any required approvals before use.

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
            statutory_basis="To be confirmed by authorized issuing authority / legal counsel",
            legal_draft_text=legal_draft,
            urgency="Critical"
        )
