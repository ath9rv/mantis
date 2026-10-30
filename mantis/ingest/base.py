"""
MANTIS Dynamic Ingestion Base Framework
Bank-agnostic parsing, fuzzy column mapping, mathematical reconciliation,
and unmapped data retention. Zero data discarded.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
import hashlib
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timezone
from mantis.core.models import CanonicalTransaction, Rail

class IngestionReconciliationError(Exception):
    """Raised when opening + credits - debits != closing balance."""
    pass

class BaseStatementAdapter(ABC):
    """Abstract base adapter for parsing any bank statement or financial ledger."""

    def __init__(self, document_id: str, case_id: str, raw_bytes: bytes, filename: str):
        self.document_id = document_id
        self.case_id = case_id
        self.raw_bytes = raw_bytes
        self.filename = filename
        self.sha256 = hashlib.sha256(raw_bytes).hexdigest()

    @abstractmethod
    def parse(self) -> Tuple[List[CanonicalTransaction], Dict[str, Any]]:
        """
        Parses document into canonical transactions and reconciliation metrics.
        Returns: (transactions_list, reconciliation_summary)
        """
        pass

    @staticmethod
    def parse_amount_to_minor(val_str: Any, decimals: int = 2) -> int:
        """Convert a financial amount to integer minor units without float rounding."""
        if val_str is None or str(val_str).strip() == "":
            return 0
        cleaned = re.sub(r"[^\d,().+-]", "", str(val_str)).strip().replace(",", "")
        if not cleaned:
            raise ValueError(f"Invalid amount: {val_str!r}")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            value = Decimal(cleaned)
            if not value.is_finite():
                raise InvalidOperation
            return int((value * (10 ** decimals)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid amount: {val_str!r}") from exc

    @staticmethod
    def extract_upi_rrn(text: str) -> Optional[str]:
        """
        Universal 12-digit UPI RRN / UTR extractor.
        Matches both legacy Julian date (YDDDSSSSSSSS) and continuous STAN formats.
        """
        if not text:
            return None
        match = re.search(r"(?:UPI[/-]|RRN:?\s*|UTR:?\s*|REF:?\s*)(\d{12})\b", text, re.IGNORECASE)
        if match:
            return match.group(1)
        # Fallback to standalone 12-digit string
        match2 = re.search(r"\b(\d{12})\b", text)
        if match2:
            return match2.group(1)
        return None

    @staticmethod
    def parse_datetime_flexible(date_str: str, default_tz_offset_hours: float = 5.5) -> Tuple[datetime, str]:
        """
        Parses date string under multiple Indian and ISO formats.
        Defaults Indian statements to IST (UTC+5:30) and converts to canonical UTC.
        Returns (parsed_utc_datetime, precision: 'exact'|'minute'|'date').
        """
        date_str = str(date_str).strip()
        if not date_str:
            raise ValueError("Transaction date is empty")
        from datetime import timedelta
        ist_tz = timezone(timedelta(hours=default_tz_offset_hours))

        formats = [
            ("%d/%m/%Y %H:%M:%S", "exact"),
            ("%d-%m-%Y %H:%M:%S", "exact"),
            ("%Y-%m-%d %H:%M:%S", "exact"),
            ("%d-%b-%Y %H:%M:%S", "exact"),
            ("%d/%m/%Y %H:%M", "minute"),
            ("%d-%m-%Y %H:%M", "minute"),
            ("%Y-%m-%d %H:%M", "minute"),
            ("%d/%m/%Y", "date"),
            ("%d-%m-%Y", "date"),
            ("%Y-%m-%d", "date"),
            ("%d-%b-%Y", "date"),
        ]
        for fmt, prec in formats:
            try:
                dt_naive = datetime.strptime(date_str, fmt)
                dt_localized = dt_naive.replace(tzinfo=ist_tz)
                return dt_localized.astimezone(timezone.utc), prec
            except ValueError:
                continue
        # ISO timestamps may include an explicit UTC offset or Z suffix.
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ist_tz)
            precision = "exact" if "." in date_str or re.search(r"\d{2}:\d{2}:\d{2}", date_str) else "minute"
            return dt.astimezone(timezone.utc), precision
        except ValueError as exc:
            raise ValueError(f"Unsupported transaction date: {date_str!r}") from exc
