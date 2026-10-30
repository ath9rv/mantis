"""
MANTIS Dynamic Bank Statement Adapter
Bank-Agnostic CSV / Tabular Statement Ingestion Engine.
Auto-detects header aliases, normalizes UPI/IMPS rails, checks running balance invariant,
and preserves unmapped columns in raw metadata.
"""

import csv
import io
import uuid
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from mantis.core.models import CanonicalTransaction, CanonicalEntity, Rail, EntityKind
from mantis.ingest.base import BaseStatementAdapter

class DynamicBankStatementAdapter(BaseStatementAdapter):
    """
    Parses CSV/TSV statements from ANY bank without hardcoding institution rules.
    """

    # Flexible column header aliases
    DATE_ALIASES = ["date", "txn date", "tran date", "transaction date", "value date"]
    DESC_ALIASES = ["description", "transaction details", "particulars", "narration", "remarks"]
    REF_ALIASES = ["chq/ref no", "ref no", "ref no./cheque no.", "reference", "utr", "rrn", "cheque no"]
    DR_ALIASES = ["withdrawal (dr)", "withdrawal", "debit", "dr", "debit amount"]
    CR_ALIASES = ["deposit (cr)", "deposit", "credit", "cr", "credit amount"]
    BAL_ALIASES = ["balance", "closing balance", "running balance", "bal"]

    def __init__(self, document_id: str, case_id: str, raw_bytes: bytes, filename: str,
                 account_owner_id: Optional[str] = None):
        super().__init__(document_id, case_id, raw_bytes, filename)
        self.account_owner_id = account_owner_id or f"entity_{uuid.uuid4().hex[:8]}"

    def parse(self) -> Tuple[List[CanonicalTransaction], Dict[str, Any]]:
        text_stream = io.StringIO(self.raw_bytes.decode("utf-8", errors="replace"))
        reader = csv.reader(text_stream)
        
        headers = []
        for row in reader:
            if not row or all(c.strip() == "" for c in row):
                continue
            # Look for header line containing date and amount/balance markers
            row_lower = [c.lower().strip() for c in row]
            if any(d in row_lower for d in self.DATE_ALIASES) and (
                any(dr in row_lower for dr in self.DR_ALIASES) or any(cr in row_lower for cr in self.CR_ALIASES)
            ):
                headers = row_lower
                raw_headers = row
                break

        if not headers:
            raise ValueError("Unable to auto-detect valid transaction table headers in statement.")

        # Map indices
        idx_date = self._find_best_match(headers, self.DATE_ALIASES)
        idx_desc = self._find_best_match(headers, self.DESC_ALIASES)
        idx_ref = self._find_best_match(headers, self.REF_ALIASES)
        idx_dr = self._find_best_match(headers, self.DR_ALIASES)
        idx_cr = self._find_best_match(headers, self.CR_ALIASES)
        idx_bal = self._find_best_match(headers, self.BAL_ALIASES)

        transactions: List[CanonicalTransaction] = []
        total_debits = 0
        total_credits = 0
        opening_balance: Optional[int] = None
        closing_balance: Optional[int] = None

        for row_idx, row in enumerate(reader):
            if not row or len(row) <= max(filter(lambda x: x is not None, [idx_date, idx_desc])):
                continue

            # Extract fields
            date_raw = row[idx_date] if idx_date is not None else ""
            desc_raw = row[idx_desc] if idx_desc is not None else ""
            ref_raw = row[idx_ref] if idx_ref is not None and idx_ref < len(row) else ""
            dr_raw = row[idx_dr] if idx_dr is not None and idx_dr < len(row) else ""
            cr_raw = row[idx_cr] if idx_cr is not None and idx_cr < len(row) else ""
            bal_raw = row[idx_bal] if idx_bal is not None and idx_bal < len(row) else ""

            # Check if this row is an explicit Opening Balance record
            if "opening balance" in desc_raw.lower() or "b/f" in desc_raw.lower():
                opening_balance = self.parse_amount_to_minor(bal_raw or cr_raw or dr_raw)
                continue

            dt_utc, precision = self.parse_datetime_flexible(date_raw)
            dr_minor = self.parse_amount_to_minor(dr_raw)
            cr_minor = self.parse_amount_to_minor(cr_raw)
            bal_minor = self.parse_amount_to_minor(bal_raw)

            if opening_balance is None and bal_minor > 0:
                # If first row has balance and is debit, opening was bal + dr - cr
                opening_balance = bal_minor + dr_minor - cr_minor

            if bal_minor > 0:
                closing_balance = bal_minor

            # Detect rail
            rail = Rail.OTHER
            desc_upper = desc_raw.upper()
            if "UPI" in desc_upper:
                rail = Rail.UPI
            elif "IMPS" in desc_upper:
                rail = Rail.IMPS
            elif "NEFT" in desc_upper:
                rail = Rail.NEFT
            elif "RTGS" in desc_upper:
                rail = Rail.RTGS
            elif "ATM" in desc_upper:
                rail = Rail.ATM

            # Extract 12-digit UTR / RRN
            rrn = self.extract_upi_rrn(f"{ref_raw} {desc_raw}")

            # Collect unmapped columns for lossless audit
            unmapped = {}
            for col_i, col_val in enumerate(row):
                if col_i not in [idx_date, idx_desc, idx_ref, idx_dr, idx_cr, idx_bal] and col_i < len(raw_headers):
                    unmapped[raw_headers[col_i].strip()] = col_val.strip()

            if dr_minor > 0:
                total_debits += dr_minor
                dest_counterparty_id = f"cp_{uuid.uuid5(uuid.NAMESPACE_DNS, desc_raw).hex[:8]}"
                tx = CanonicalTransaction(
                    id=f"tx_{uuid.uuid4().hex[:12]}",
                    case_id=self.case_id,
                    rail=rail,
                    src_id=self.account_owner_id,
                    dst_id=dest_counterparty_id,
                    asset="INR",
                    amount_minor=dr_minor,
                    decimals=2,
                    ts_utc=dt_utc,
                    ts_precision=precision,
                    ref=rrn or ref_raw or None,
                    ref_kind="rrn" if rrn else "other",
                    raw_unmapped_data=unmapped,
                    source_doc_hash=self.sha256
                )
                transactions.append(tx)

            if cr_minor > 0:
                total_credits += cr_minor
                src_counterparty_id = f"cp_{uuid.uuid5(uuid.NAMESPACE_DNS, desc_raw).hex[:8]}"
                tx = CanonicalTransaction(
                    id=f"tx_{uuid.uuid4().hex[:12]}",
                    case_id=self.case_id,
                    rail=rail,
                    src_id=src_counterparty_id,
                    dst_id=self.account_owner_id,
                    asset="INR",
                    amount_minor=cr_minor,
                    decimals=2,
                    ts_utc=dt_utc,
                    ts_precision=precision,
                    ref=rrn or ref_raw or None,
                    ref_kind="rrn" if rrn else "other",
                    raw_unmapped_data=unmapped,
                    source_doc_hash=self.sha256
                )
                transactions.append(tx)

        # Mathematical Reconciliation Check
        reconciled = False
        discrepancy = 0
        if opening_balance is not None and closing_balance is not None:
            expected_closing = opening_balance + total_credits - total_debits
            discrepancy = abs(expected_closing - closing_balance)
            reconciled = (discrepancy == 0)

        summary = {
            "document_hash": self.sha256,
            "filename": self.filename,
            "opening_balance_minor": opening_balance or 0,
            "closing_balance_minor": closing_balance or 0,
            "total_credits_minor": total_credits,
            "total_debits_minor": total_debits,
            "transaction_count": len(transactions),
            "reconciled": reconciled,
            "discrepancy_minor": discrepancy
        }

        return transactions, summary

    @staticmethod
    def _find_best_match(headers: List[str], aliases: List[str]) -> Optional[int]:
        for alias in aliases:
            for idx, h in enumerate(headers):
                if alias == h or alias in h:
                    return idx
        return None
