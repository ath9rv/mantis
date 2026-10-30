"""
MANTIS Recovery Intelligence & Asset Management Engine
Ranks candidate recovery targets by a transparent heuristic.
Calculates proposed disputed-amount figures for human review; generated text is not legal advice or a directive.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

@dataclass
class RecoveryTarget:
    target_id: str
    entity_id: str
    entity_display: str
    kind: str                                     # 'bank_account' | 'wallet' | 'exchange'
    institution: str                              # Bank Name / VASP Name
    account_or_address: str
    tainted_residual_minor: int
    current_balance_minor: int
    disputed_lien_minor: int                      # Min(Current_Balance, Tainted_Residual)
    decimals: int
    asset: str
    priority_score: float                         # 0.0 to 1.0 (Transparent calculation)
    urgency: str                                  # 'Critical' | 'High' | 'Medium' | 'Low'
    statutory_action: str
    notice_draft: str
    time_elapsed_hours: float

class RecoveryManager:
    """
    Manages fund-location tracking and court-compliant freeze actions.
    """

    def evaluate_targets(self, case_id: str,
                         tainted_residuals: Dict[str, int],
                         account_balances: Dict[str, int],
                         entity_directory: Dict[str, Any],
                         last_seen_times: Dict[str, datetime]) -> List[RecoveryTarget]:
        """
        Calculates candidate amounts and ranks them by a heuristic score.
        """
        targets: List[RecoveryTarget] = []
        now = datetime.now(timezone.utc)

        for entity_id, tainted_minor in tainted_residuals.items():
            if tainted_minor <= 0:
                continue

            entity = entity_directory.get(entity_id, {})
            current_bal_minor = account_balances.get(entity_id, tainted_minor)
            
            # This caps the proposed amount arithmetically; it does not establish legal authority.
            disputed_lien = min(current_bal_minor, tainted_minor)

            last_seen = last_seen_times.get(entity_id, now)
            hours_elapsed = max(0.1, (now - last_seen).total_seconds() / 3600.0)

            # Transparent Recovery Priority Score Formulation
            # Factors: Value Weight (0.45) + Time Freshness (0.35) + Destination Identifiability (0.20)
            val_norm = min(1.0, disputed_lien / 10000000.0)
            time_freshness = max(0.05, 1.0 - min(1.0, hours_elapsed / 72.0))
            identifiable_score = 1.0 if entity.get("kind") == "bank_account" else 0.6

            score = 0.45 * val_norm + 0.35 * time_freshness + 0.20 * identifiable_score

            urgency = "Low"
            if score >= 0.75:
                urgency = "Critical"
            elif score >= 0.50:
                urgency = "High"
            elif score >= 0.30:
                urgency = "Medium"

            kind = entity.get("kind", "bank_account")
            inst_name = entity.get("bank") or entity.get("vasp") or "Target Financial Institution"
            acct_val = entity.get("account_no") or entity.get("address") or entity_id

            decimals = 2 if entity.get("asset", "INR") == "INR" else 6
            asset = entity.get("asset", "INR")
            factor = 10 ** decimals
            lien_fmt = f"₹{disputed_lien / factor:,.2f}" if asset == "INR" else f"{disputed_lien / factor:.2f} {asset}"

            if kind == "bank_account":
                stat_action = f"Proposed disputed-amount review ({lien_fmt})"
                notice = f"""
PROPOSED RECOVERY ACTION — AUTHORIZED LEGAL REVIEW REQUIRED

To: The Branch Manager / Nodal Cyber Crime Officer, {inst_name}
Case FIR / NCRP Acknowledgement: {case_id}

Pursuant to cybercrime trail reconstruction, illicit proceeds of crime have been traced to 
Account No: {acct_val} standing in the name of '{entity.get('name', 'Account Holder')}'.

Proposed disputed amount for review: {lien_fmt}

No action has been taken by this software. Confirm the legal basis, procedure, notice, court or
magistrate requirements, and any applicable time limits with the authorized officer and counsel.
                """.strip()
            else:
                stat_action = f"Proposed VASP recovery inquiry ({lien_fmt})"
                notice = f"""
PROPOSED DIGITAL ASSET RECOVERY INQUIRY — AUTHORIZED REVIEW REQUIRED
To: Law Enforcement Liaison Division, {inst_name}
Target Wallet: {acct_val}
Disputed Asset: {lien_fmt}
Reference: Case {case_id}. This software has not verified ownership, legal authority, or an actual freeze.
                """.strip()

            targets.append(RecoveryTarget(
                target_id=f"rec_{uuid.uuid4().hex[:8]}",
                entity_id=entity_id,
                entity_display=entity.get("name", entity_id),
                kind=kind,
                institution=inst_name,
                account_or_address=acct_val,
                tainted_residual_minor=tainted_minor,
                current_balance_minor=current_bal_minor,
                disputed_lien_minor=disputed_lien,
                decimals=decimals,
                asset=asset,
                priority_score=round(score, 3),
                urgency=urgency,
                statutory_action=stat_action,
                notice_draft=notice,
                time_elapsed_hours=round(hours_elapsed, 1)
            ))

        # Rank descending by priority score
        targets.sort(key=lambda t: t.priority_score, reverse=True)
        return targets
