"""
MANTIS SQLAlchemy ORM Models
Corresponds to the extended canonical database schema.
Supports JSON serialization for both SQLite and PostgreSQL.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    Text, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from mantis.db.session import Base

class CaseDB(Base):
    __tablename__ = "cases"

    id = Column(String(64), primary_key=True, default=lambda: f"case_{uuid.uuid4().hex[:12]}")
    case_number = Column(String(64), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    complaint_ref = Column(String(128), nullable=True) # NCRP / FIR
    jurisdiction = Column(String(255), nullable=False, default="State Cyber Crime Police Station")
    investigating_officer = Column(String(255), nullable=False, default="Inspector Cyber Forensics")
    params_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    documents = relationship("DocumentDB", back_populates="case", cascade="all, delete-orphan")
    entities = relationship("EntityDB", back_populates="case", cascade="all, delete-orphan")
    transfers = relationship("TransferDB", back_populates="case", cascade="all, delete-orphan")

class DocumentDB(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True, default=lambda: f"doc_{uuid.uuid4().hex[:12]}")
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    sha256 = Column(String(64), nullable=False)
    filename = Column(String(255), nullable=False)
    mime = Column(String(64), nullable=False, default="text/csv")
    parser = Column(String(64), nullable=False, default="dynamic_adapter")
    parse_status = Column(String(32), nullable=False, default="ok")
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case = relationship("CaseDB", back_populates="documents")

class StatementReconciliationDB(Base):
    __tablename__ = "statement_reconciliations"

    id = Column(String(64), primary_key=True, default=lambda: f"rec_{uuid.uuid4().hex[:12]}")
    document_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    account_identifier = Column(String(128), nullable=False)
    opening_balance_minor = Column(Integer, nullable=False)
    closing_balance_minor = Column(Integer, nullable=False)
    calculated_balance_minor = Column(Integer, nullable=False)
    total_credits_minor = Column(Integer, nullable=False)
    total_debits_minor = Column(Integer, nullable=False)
    reconciled = Column(Boolean, nullable=False, default=False)
    error_margin_minor = Column(Integer, nullable=False, default=0)

class EntityDB(Base):
    __tablename__ = "entities"

    id = Column(String(64), primary_key=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(64), nullable=False)
    display = Column(String(255), nullable=False)
    observed = Column(Boolean, nullable=False, default=True)
    risk_tags_json = Column(Text, nullable=False, default="[]")
    is_custody_boundary = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(Text, nullable=False, default="{}")

    case = relationship("CaseDB", back_populates="entities")

class TransferDB(Base):
    __tablename__ = "transfers"

    id = Column(String(64), primary_key=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    rail = Column(String(32), nullable=False)
    src_id = Column(String(64), nullable=False)
    dst_id = Column(String(64), nullable=False)
    asset = Column(String(32), nullable=False, default="INR")
    amount_minor = Column(Integer, nullable=False)
    decimals = Column(Integer, nullable=False, default=2)
    ts_utc = Column(DateTime, nullable=False)
    ts_precision = Column(String(16), nullable=False, default="minute")
    ref = Column(String(128), nullable=True)
    ref_kind = Column(String(32), nullable=True)
    corroboration = Column(Integer, nullable=False, default=1)
    raw_unmapped_json = Column(Text, nullable=False, default="{}")
    source_doc_hash = Column(String(64), nullable=True)

    case = relationship("CaseDB", back_populates="transfers")

class SeamMatchDB(Base):
    __tablename__ = "seam_matches"

    id = Column(String(64), primary_key=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    fiat_transfer_id = Column(String(64), nullable=False)
    chain_transfer_id = Column(String(64), nullable=False)
    label = Column(String(32), nullable=False, default="inferred")
    confidence_score = Column(Float, nullable=False)
    delta_t_seconds = Column(Integer, nullable=False)
    inr_amount_minor = Column(Integer, nullable=False)
    usdt_amount_minor = Column(Integer, nullable=False)
    implied_rate = Column(Float, nullable=False)
    deviation_pct = Column(Float, nullable=False)
    assigned_vasp = Column(String(128), nullable=True)
    review_status = Column(String(32), nullable=False, default="pending")
    reason = Column(Text, nullable=False, default="")

class EpisodeDB(Base):
    __tablename__ = "episodes"

    id = Column(String(64), primary_key=True, default=lambda: f"ep_{uuid.uuid4().hex[:12]}")
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    pattern = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    confidence = Column(Float, nullable=False)
    evidence_tx_ids_json = Column(Text, nullable=False, default="[]")
    metrics_json = Column(Text, nullable=False, default="{}")
    benign_hypotheses_json = Column(Text, nullable=False, default="[]")

class InvestigationDataRequestDB(Base):
    __tablename__ = "investigation_data_requests"

    id = Column(String(64), primary_key=True)
    case_id = Column(String(64), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(String(64), nullable=False)
    target_institution = Column(String(128), nullable=False)
    custody_account_or_wallet = Column(String(255), nullable=False)
    unresolved_amount_formatted = Column(String(64), nullable=False)
    asks_json = Column(Text, nullable=False, default="[]")
    statutory_basis = Column(String(128), nullable=False)
    legal_draft_text = Column(Text, nullable=False)
    urgency = Column(String(32), nullable=False, default="High")
    status = Column(String(32), nullable=False, default="open")

class AuditLogDB(Base):
    __tablename__ = "audit_log"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), nullable=False)
    actor = Column(String(128), nullable=False)
    action = Column(String(128), nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    prev_hash = Column(String(64), nullable=False)
    this_hash = Column(String(64), nullable=False)
    at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
