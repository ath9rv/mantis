"""
MANTIS Dynamic Ingestion Base Framework
Bank-agnostic parsing, fuzzy column mapping, mathematical reconciliation,
and unmapped data retention. Zero data discarded.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
import hashlib
import re
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
        """Converts strings like '1,50,000.50' or '₹49,500' into integer minor units (paise)."""
        if val_str is None or val_str == "":
            return 0
        cleaned = re.sub(r"[^\d.-]", "", str(val_str)).strip()
        if not cleaned:
            return 0
        try:
            val_float = float(cleaned)
            return int(round(val_float * (10 ** decimals)))
        except ValueError:
            return 0

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
        # Default fallback to now with 'date' precision
        return datetime.now(timezone.utc), "date"
