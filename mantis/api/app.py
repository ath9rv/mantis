"""
MANTIS prototype FastAPI application
Provides RESTful APIs for case management, statement ingestion, multi-strategy tracing,
bipartite seam matching, typology detection, custody gap planning, and grounded AI copilot.
"""

import os
import csv
import json
import re
import uuid
import hashlib
import hmac
import math
from dataclasses import asdict
from urllib.parse import quote
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, model_validator

from mantis.config import MantisConfig
from mantis.db.session import get_db, init_db
from mantis.db.models import (
    CaseDB, DocumentDB, StatementReconciliationDB, EntityDB, TransferDB,
    SeamMatchDB, EpisodeDB, InvestigationDataRequestDB, TraceRunDB, AuditLogDB
)
from mantis.core.models import (
    CanonicalTransaction, CanonicalEntity, Rail, EntityKind, LinkLabel,
    FlowEdge, SeamEdge, Episode, InvestigationDataRequest,
)
from mantis.ingest.bank_statement import DynamicBankStatementAdapter
from mantis.ingest.evidence_store import store_evidence, read_evidence
from mantis.correlation.seam_solver import MultiRailSeamSolver
from mantis.graph.tracer import MultiStrategyTracer
from mantis.intelligence.typologies import RapidPassThroughDetector, StructuringDetector, PeelChainDetector
from mantis.copilot.grounded_querier import GroundedCopilotQuerier

# Initialize Database Schema
init_db()

app = FastAPI(
    title="MANTIS API",
    description="Development prototype for statement ingestion, seam matching, typology analysis, and case queries",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "MANTIS_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = MantisConfig()
API_KEY = os.getenv("MANTIS_API_KEY")
AUDIT_ACTOR = os.getenv("MANTIS_AUDIT_ACTOR", "local_operator")

def append_audit(db: Session, case_id: str, action: str, payload: Dict[str, Any]) -> None:
    """Append a SHA-256 linked audit event in the same DB transaction as its action."""
    previous = db.query(AuditLogDB).filter(AuditLogDB.case_id == case_id).order_by(AuditLogDB.seq.desc()).first()
    prev_hash = previous.this_hash if previous else "0" * 64
    at = datetime.now(timezone.utc)
    event = {
        "case_id": case_id, "actor": AUDIT_ACTOR, "action": action,
        "payload": payload, "prev_hash": prev_hash, "at": at.isoformat(),
    }
    this_hash = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    db.add(AuditLogDB(case_id=case_id, actor=AUDIT_ACTOR, action=action,
                      payload_json=json.dumps(payload, sort_keys=True, ensure_ascii=False),
                      prev_hash=prev_hash, this_hash=this_hash, at=at))

@app.middleware("http")
async def protect_api_when_configured(request: Request, call_next):
    if API_KEY and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {API_KEY}"):
            return JSONResponse(status_code=401, content={"detail": "Valid bearer token required"})
    return await call_next(request)

# Pydantic Schemas
class CaseCreateRequest(BaseModel):
    title: str
    complaint_ref: Optional[str] = None
    jurisdiction: Optional[str] = "State Cyber Crime Police Station"
    investigating_officer: Optional[str] = "Inspector Cyber Forensics"

class CopilotQueryRequest(BaseModel):
    question: str

class TraceRequest(BaseModel):
    seed_transfer_id: str = Field(min_length=1, max_length=64)
    market_fx_rate: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    market_fx_source: Optional[str] = Field(default=None, max_length=512)
    market_fx_observed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_fx_provenance(self):
        source = (self.market_fx_source or "").strip()
        if self.market_fx_rate is None:
            if source or self.market_fx_observed_at is not None:
                raise ValueError("FX source and observation time require a market_fx_rate")
            return self
        if not source:
            raise ValueError("market_fx_source is required when a market_fx_rate is supplied")
        if self.market_fx_observed_at is None or self.market_fx_observed_at.tzinfo is None or self.market_fx_observed_at.utcoffset() is None:
            raise ValueError("market_fx_observed_at must be a timezone-aware timestamp")
        self.market_fx_source = source
        return self

class EntityUpdateRequest(BaseModel):
    display: Optional[str] = None
    kind: Optional[str] = None
    is_custody_boundary: Optional[bool] = None

def safe_filename(filename: Optional[str], fallback: str) -> str:
    name = os.path.basename((filename or fallback).replace("\\", "/")).strip()
    return name[:255] or fallback

async def read_upload(file: UploadFile) -> bytes:
    max_upload_bytes = int(os.getenv("MANTIS_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
    content = await file.read(max_upload_bytes + 1)
    if len(content) > max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"Upload exceeds {max_upload_bytes} byte limit")
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    return content

def format_minor(amount_minor: int, decimals: int, asset: str) -> str:
    from decimal import Decimal
    value = Decimal(amount_minor) / (Decimal(10) ** decimals)
    return f"₹{value:,.2f}" if asset.upper() == "INR" else f"{value:,.{min(decimals, 8)}f} {asset.upper()}"

def stable_sha256(payload: Any) -> str:
    """Hash a JSON-compatible value using a stable UTF-8 representation."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

# ---------------------------------------------------------------------------
# CASE MANAGEMENT ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "2.0.0", "time_utc": datetime.now(timezone.utc).isoformat()}

@app.get("/api/cases")
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(CaseDB).order_by(CaseDB.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "case_number": c.case_number,
            "title": c.title,
            "complaint_ref": c.complaint_ref,
            "jurisdiction": c.jurisdiction,
            "investigating_officer": c.investigating_officer,
            "created_at": c.created_at.isoformat()
        }
        for c in cases
    ]

@app.post("/api/cases")
def create_case(req: CaseCreateRequest, db: Session = Depends(get_db)):
    if not req.title.strip():
        raise HTTPException(status_code=422, detail="Case title must not be empty")
    case_num = f"NCRP-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}"
    new_case = CaseDB(
        case_number=case_num,
        title=req.title,
        complaint_ref=req.complaint_ref or case_num,
        jurisdiction=req.jurisdiction or "State Cyber Crime Police Station",
        investigating_officer=req.investigating_officer or "Inspector Cyber Forensics",
        params_json=json.dumps(config.__dict__, default=str)
    )
    db.add(new_case)
    db.flush()
    append_audit(db, new_case.id, "case.created", {"case_number": case_num, "title": req.title.strip()})
    db.commit()
    db.refresh(new_case)
    return {"id": new_case.id, "case_number": new_case.case_number, "title": new_case.title}

@app.get("/api/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(CaseDB).filter(CaseDB.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    tx_count = db.query(TransferDB).filter(TransferDB.case_id == case_id).count()
    doc_count = db.query(DocumentDB).filter(DocumentDB.case_id == case_id).count()
    ep_count = db.query(EpisodeDB).filter(EpisodeDB.case_id == case_id).count()
    gap_count = db.query(InvestigationDataRequestDB).filter(InvestigationDataRequestDB.case_id == case_id).count()

    return {
        "id": case.id,
        "case_number": case.case_number,
        "title": case.title,
        "complaint_ref": case.complaint_ref,
        "jurisdiction": case.jurisdiction,
        "investigating_officer": case.investigating_officer,
        "stats": {
            "transactions": tx_count,
            "documents": doc_count,
            "typologies": ep_count,
            "gap_requests": gap_count
        }
    }

# ---------------------------------------------------------------------------
# DOCUMENT INGESTION & RECONCILIATION ENDPOINTS
# ---------------------------------------------------------------------------
@app.post("/api/cases/{case_id}/ingest/csv")
async def ingest_csv(case_id: str, file: UploadFile = File(...),
                     account_owner_name: Optional[str] = Form(None),
                     db: Session = Depends(get_db)):
    case = db.query(CaseDB).filter(CaseDB.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    content = await read_upload(file)
    sha256, _ = store_evidence(content)
    existing = db.query(DocumentDB).filter(
        DocumentDB.case_id == case_id, DocumentDB.sha256 == sha256
    ).first()
    if existing:
        append_audit(db, case_id, "evidence.duplicate_upload", {"document_id": existing.id, "sha256": sha256, "filename": safe_filename(file.filename, "statement.csv")})
        db.commit()
        return {"document_id": existing.id, "sha256": sha256, "already_ingested": True, "parse_status": existing.parse_status}

    owner_id = f"entity_{uuid.uuid4().hex[:12]}"
    filename = safe_filename(file.filename, "statement.csv")
    adapter = DynamicBankStatementAdapter(
        document_id=f"doc_{uuid.uuid4().hex[:12]}", case_id=case_id,
        raw_bytes=content, filename=filename, account_owner_id=owner_id
    )
    try:
        txs, summary = adapter.parse()
    except (UnicodeDecodeError, ValueError, csv.Error) as exc:
        doc = DocumentDB(id=adapter.document_id, case_id=case_id, sha256=sha256,
                         filename=filename, mime="text/csv", parse_status="rejected")
        db.add(doc)
        append_audit(db, case_id, "evidence.import_rejected", {"document_id": doc.id, "sha256": sha256, "filename": filename, "reason": str(exc)[:500]})
        db.commit()
        raise HTTPException(status_code=422, detail={"message": str(exc), "document_id": doc.id, "sha256": sha256}) from exc

    doc = DocumentDB(
        id=adapter.document_id, case_id=case_id, sha256=sha256, filename=filename,
        mime="text/csv", parse_status="ok" if summary["reconciled"] else "review"
    )
    db.add(doc)
    db.add(EntityDB(
        id=owner_id, case_id=case_id, kind="bank_account",
        display=(account_owner_name or filename.rsplit(".", 1)[0]).strip(), observed=True
    ))
    db.add(StatementReconciliationDB(
        document_id=doc.id, account_identifier=owner_id,
        opening_balance_minor=summary["opening_balance_minor"],
        closing_balance_minor=summary["closing_balance_minor"],
        calculated_balance_minor=summary["opening_balance_minor"] + summary["total_credits_minor"] - summary["total_debits_minor"],
        total_credits_minor=summary["total_credits_minor"], total_debits_minor=summary["total_debits_minor"],
        reconciled=summary["reconciled"], error_margin_minor=summary["discrepancy_minor"]
    ))

    entity_ids = {owner_id}
    for tx in txs:
        entity_ids.update((tx.src_id, tx.dst_id))
        db.add(TransferDB(
            id=tx.id, case_id=case_id, rail=tx.rail.value, src_id=tx.src_id, dst_id=tx.dst_id,
            asset=tx.asset, amount_minor=tx.amount_minor, decimals=tx.decimals, ts_utc=tx.ts_utc,
            ts_precision=tx.ts_precision, ref=tx.ref, ref_kind=tx.ref_kind,
            corroboration=tx.corroboration, raw_unmapped_json=json.dumps(tx.raw_unmapped_data, ensure_ascii=False),
            source_doc_hash=sha256
        ))
    existing_ids = {row[0] for row in db.query(EntityDB.id).filter(
        EntityDB.case_id == case_id, EntityDB.id.in_(entity_ids)
    ).all()}
    for entity_id in entity_ids - existing_ids:
        if entity_id != owner_id:
            is_reference = entity_id.startswith("cp_")
            db.add(EntityDB(
                id=entity_id, case_id=case_id, kind="unknown",
                display="Unresolved transfer reference" if is_reference else entity_id,
                observed=True, metadata_json=json.dumps({"reference_node": is_reference})
            ))

    append_audit(db, case_id, "evidence.csv_imported", {
        "document_id": doc.id, "sha256": sha256, "filename": filename,
        "transaction_count": len(txs), "reconciled": summary["reconciled"],
    })
    db.commit()
    return {
        "document_id": doc.id,
        "sha256": sha256,
        "already_ingested": False,
        "transactions_imported": len(txs),
        "reconciliation": summary
    }

@app.post("/api/cases/{case_id}/ingest/tron-json")
async def ingest_tron_json(case_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import a frozen TRON transfer export as evidence; no external chain API is queried."""
    if not db.query(CaseDB).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    content = await read_upload(file)
    sha256, _ = store_evidence(content)
    existing_doc = db.query(DocumentDB).filter(
        DocumentDB.case_id == case_id, DocumentDB.sha256 == sha256
    ).first()
    if existing_doc:
        append_audit(db, case_id, "evidence.duplicate_upload", {"document_id": existing_doc.id, "sha256": sha256, "filename": safe_filename(file.filename, "tron-transfer-export.json")})
        db.commit()
        return {"document_id": existing_doc.id, "sha256": sha256, "already_ingested": True, "parse_status": existing_doc.parse_status}
    filename = safe_filename(file.filename, "tron-transfer-export.json")

    def reject_import(reason: str):
        doc = DocumentDB(id=f"doc_{uuid.uuid4().hex[:12]}", case_id=case_id, sha256=sha256,
                         filename=filename, mime="application/json", parser="tron_json_adapter", parse_status="rejected")
        db.add(doc)
        append_audit(db, case_id, "evidence.import_rejected", {
            "document_id": doc.id, "sha256": sha256, "filename": filename, "reason": reason[:500],
        })
        db.commit()
        raise HTTPException(status_code=422, detail={"message": reason, "document_id": doc.id, "sha256": sha256})

    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        reject_import(f"Invalid UTF-8 JSON: {exc}")
    events = payload.get("transfers") if isinstance(payload, dict) else payload
    if not isinstance(events, list) or not events:
        reject_import("Expected a non-empty JSON array or an object with a transfers array")

    normalized = []
    seen_event_keys = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            reject_import(f"Transfer at index {index} must be an object")
        tx_hash = str(event.get("tx_hash") or event.get("transaction_id") or "").strip()
        if tx_hash.lower().startswith("0x"):
            tx_hash = tx_hash[2:]
        if not re.fullmatch(r"[0-9a-fA-F]{64}", tx_hash):
            reject_import(f"Transfer at index {index} requires a 32-byte hexadecimal transaction hash")
        tx_hash = tx_hash.lower()
        src = str(event.get("from_address") or event.get("from") or "").strip()
        dst = str(event.get("to_address") or event.get("to") or "").strip()
        try:
            raw_amount = event["amount_minor"]
            raw_timestamp = event["block_timestamp"]
            raw_decimals = event.get("decimals", 6)
            raw_event_index = event.get("event_index", event.get("log_index", 0))
            if any(isinstance(value, bool) for value in (raw_amount, raw_timestamp, raw_decimals, raw_event_index)):
                raise ValueError("boolean values are not valid numeric fields")
            if any(isinstance(value, float) and not value.is_integer() for value in (raw_amount, raw_timestamp, raw_decimals, raw_event_index)):
                raise ValueError("fractional values are not valid for integer fields")
            amount_minor = int(raw_amount)
            timestamp_ms = int(raw_timestamp)
            decimals = int(raw_decimals)
            event_index = int(raw_event_index)
        except (KeyError, TypeError, ValueError) as exc:
            reject_import(f"Transfer at index {index} requires integer amount_minor and block_timestamp: {exc}")
        if not tx_hash or not src or not dst or amount_minor <= 0 or not 0 < timestamp_ms < 253402300800000 or not 0 <= decimals <= 18 or event_index < 0:
            reject_import(f"Transfer at index {index} has invalid hash, address, amount, timestamp, or decimals")
        event_key = f"{tx_hash}:{event_index}"
        if event_key in seen_event_keys:
            reject_import(f"Duplicate transfer event in upload: {event_key}")
        seen_event_keys.add(event_key)
        normalized.append((event, tx_hash, event_index, event_key, src, dst, amount_minor, timestamp_ms, decimals))

    doc = DocumentDB(
        id=f"doc_{uuid.uuid4().hex[:12]}", case_id=case_id, sha256=sha256,
        filename=filename, mime="application/json", parser="tron_json_adapter", parse_status="ok"
    )
    db.add(doc)
    event_transfer_ids = {
        f"chain_{hashlib.sha256((case_id + ':' + event_key).encode()).hexdigest()[:24]}"
        for event_key in seen_event_keys
    }
    existing_transfer_ids = {row[0] for row in db.query(TransferDB.id).filter(
        TransferDB.case_id == case_id, TransferDB.id.in_(event_transfer_ids)
    ).all()} if event_transfer_ids else set()
    new_count = 0
    entity_records = {}
    for event, tx_hash, event_index, event_key, src, dst, amount_minor, timestamp_ms, decimals in normalized:
        transfer_id = f"chain_{hashlib.sha256((case_id + ':' + event_key).encode()).hexdigest()[:24]}"
        if transfer_id in existing_transfer_ids:
            continue
        def wallet_id(address: str) -> str:
            return f"wallet_{hashlib.sha256((case_id + ':' + address).encode()).hexdigest()[:24]}"
        src_id, dst_id = wallet_id(src), wallet_id(dst)
        entity_records[src_id] = src
        entity_records[dst_id] = dst
        db.add(TransferDB(
            id=transfer_id, case_id=case_id,
            rail=Rail.TRON.value, src_id=src_id, dst_id=dst_id, asset=str(event.get("asset") or event.get("token_symbol") or "USDT").upper(),
            amount_minor=amount_minor, decimals=decimals,
            ts_utc=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc), ts_precision="exact",
            ref=tx_hash, ref_kind="tx_hash", corroboration=1,
            raw_unmapped_json=json.dumps(event, ensure_ascii=False), source_doc_hash=sha256
        ))
        new_count += 1
    present = {row[0] for row in db.query(EntityDB.id).filter(
        EntityDB.case_id == case_id, EntityDB.id.in_(entity_records.keys())
    ).all()} if entity_records else set()
    for entity_id, address in entity_records.items():
        if entity_id not in present:
            db.add(EntityDB(id=entity_id, case_id=case_id, kind=EntityKind.WALLET.value, display=address, observed=True))
    append_audit(db, case_id, "evidence.tron_json_imported", {
        "document_id": doc.id, "sha256": sha256, "filename": filename,
        "transaction_count": new_count,
    })
    db.commit()
    return {"document_id": doc.id, "sha256": sha256, "already_ingested": False, "transactions_imported": new_count, "duplicates_skipped": len(existing_transfer_ids)}

# ---------------------------------------------------------------------------
# GRAPH & INVESTIGATION TRACE ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/api/cases/{case_id}/transactions")
def list_case_transactions(case_id: str, limit: int = Query(100, ge=1, le=1000),
                           offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    if not db.query(CaseDB.id).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    query = db.query(TransferDB).filter(TransferDB.case_id == case_id)
    total = query.count()
    rows = query.order_by(TransferDB.ts_utc.asc(), TransferDB.id.asc()).offset(offset).limit(limit).all()
    doc_hashes = {row.source_doc_hash for row in rows if row.source_doc_hash}
    docs = {doc.sha256: doc.filename for doc in db.query(DocumentDB).filter(
        DocumentDB.case_id == case_id, DocumentDB.sha256.in_(doc_hashes)
    ).all()} if doc_hashes else {}
    return {
        "items": [{
            "id": tx.id, "rail": tx.rail, "src_id": tx.src_id, "dst_id": tx.dst_id,
            "asset": tx.asset, "amount_minor": tx.amount_minor, "decimals": tx.decimals,
            "amount": format_minor(tx.amount_minor, tx.decimals, tx.asset),
            "ts_utc": tx.ts_utc.replace(tzinfo=timezone.utc).isoformat(),
            "ts_precision": tx.ts_precision, "ref": tx.ref, "ref_kind": tx.ref_kind,
            "source_doc_hash": tx.source_doc_hash,
            "source_filename": docs.get(tx.source_doc_hash, "Unknown source document"),
        } for tx in rows],
        "total": total, "limit": limit, "offset": offset,
    }

@app.get("/api/cases/{case_id}/documents")
def list_case_documents(case_id: str, db: Session = Depends(get_db)):
    if not db.query(CaseDB.id).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    docs = db.query(DocumentDB).filter(DocumentDB.case_id == case_id).order_by(DocumentDB.uploaded_at.desc()).all()
    return [{"id": d.id, "filename": d.filename, "sha256": d.sha256, "mime": d.mime,
             "parser": d.parser, "parse_status": d.parse_status,
             "uploaded_at": d.uploaded_at.replace(tzinfo=timezone.utc).isoformat()} for d in docs]

@app.get("/api/cases/{case_id}/documents/{document_id}/content")
def download_case_document(case_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.query(DocumentDB).filter(DocumentDB.case_id == case_id, DocumentDB.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in case")
    try:
        content = read_evidence(doc.sha256)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="Original evidence file is missing from local evidence storage") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    encoded_name = quote(safe_filename(doc.filename, "evidence.bin"), safe="")
    return Response(content=content, media_type=doc.mime,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
                             "X-Content-SHA256": doc.sha256})

@app.get("/api/cases/{case_id}/entities")
def list_case_entities(case_id: str, db: Session = Depends(get_db)):
    if not db.query(CaseDB.id).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    entities = db.query(EntityDB).filter(EntityDB.case_id == case_id).order_by(EntityDB.display.asc()).all()
    return [{"id": e.id, "kind": e.kind, "display": e.display, "observed": e.observed,
             "is_custody_boundary": e.is_custody_boundary,
             "metadata": json.loads(e.metadata_json or "{}"),
             "risk_tags": json.loads(e.risk_tags_json or "[]")} for e in entities]

@app.patch("/api/cases/{case_id}/entities/{entity_id}")
def update_case_entity(case_id: str, entity_id: str, req: EntityUpdateRequest, db: Session = Depends(get_db)):
    entity = db.query(EntityDB).filter(EntityDB.case_id == case_id, EntityDB.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found in case")
    allowed_kinds = {kind.value for kind in EntityKind}
    if req.kind is not None:
        if req.kind not in allowed_kinds:
            raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(allowed_kinds)}")
        entity.kind = req.kind
    if req.display is not None:
        if not req.display.strip():
            raise HTTPException(status_code=422, detail="display must not be empty")
        entity.display = req.display.strip()[:255]
    if req.is_custody_boundary is not None:
        entity.is_custody_boundary = req.is_custody_boundary
    append_audit(db, case_id, "entity.reviewed", {
        "entity_id": entity.id, "kind": entity.kind, "display": entity.display,
        "is_custody_boundary": entity.is_custody_boundary,
    })
    db.commit()
    return {"id": entity.id, "kind": entity.kind, "display": entity.display,
            "is_custody_boundary": entity.is_custody_boundary}

@app.get("/api/cases/{case_id}/graph")
def get_case_graph(case_id: str, db: Session = Depends(get_db)):
    """Return observed transfers and persisted candidate seams for this case."""
    if not db.query(CaseDB.id).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    transfers = db.query(TransferDB).filter(TransferDB.case_id == case_id).all()
    entities = db.query(EntityDB).filter(EntityDB.case_id == case_id).all()
    seams = db.query(SeamMatchDB).filter(SeamMatchDB.case_id == case_id).all()
    nodes = [{"data": {"id": ent.id, "label": ent.display, "kind": ent.kind,
                        "risk_tags": json.loads(ent.risk_tags_json or "[]"),
                        "is_custody_boundary": ent.is_custody_boundary}}
             for ent in entities]
    edges = []
    transfer_by_id = {tx.id: tx for tx in transfers}
    for tx in transfers:
        edges.append({
            "data": {
                "id": f"flow_{tx.id}",
                "source": tx.src_id,
                "target": tx.dst_id,
                "edge_class": "flow",
                "label": "observed",
                "amount": format_minor(tx.amount_minor, tx.decimals, tx.asset),
                "rail": tx.rail,
                "ref": tx.ref,
                "reason": f"Source: {tx.source_doc_hash or 'unknown'}"
            }
        })

    for sm in seams:
        fiat = transfer_by_id.get(sm.fiat_transfer_id)
        chain = transfer_by_id.get(sm.chain_transfer_id)
        if not fiat or not chain:
            continue
        edges.append({
            "data": {
                "id": f"seam_{sm.id}",
                "source": fiat.src_id,
                "target": chain.dst_id,
                "edge_class": "seam",
                "label": "candidate",
                "amount": f"{format_minor(sm.inr_amount_minor, 2, 'INR')} ↔ {format_minor(sm.usdt_amount_minor, 6, 'USDT')}",
                "score": sm.confidence_score,
                "reason": sm.reason
            }
        })

    return {"elements": {"nodes": nodes, "edges": edges}}

@app.post("/api/cases/{case_id}/trace")
def execute_trace(case_id: str, req: TraceRequest, db: Session = Depends(get_db)):
    """Run an explicit seeded trace and persist its input parameters and result references."""
    if not db.query(CaseDB.id).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    tx_records = db.query(TransferDB).filter(TransferDB.case_id == case_id).all()
    if not tx_records:
        raise HTTPException(status_code=400, detail="No transactions available in this case to trace.")
    seed_record = next((tx for tx in tx_records if tx.id == req.seed_transfer_id), None)
    if not seed_record:
        raise HTTPException(status_code=404, detail="Seed transfer not found in this case")
    if req.market_fx_rate is not None and (not math.isfinite(req.market_fx_rate) or req.market_fx_rate <= 0):
        raise HTTPException(status_code=422, detail="market_fx_rate must be a finite positive number")

    canonical_txs = [CanonicalTransaction(
        id=t.id, case_id=t.case_id, rail=Rail(t.rail), src_id=t.src_id, dst_id=t.dst_id,
        asset=t.asset, amount_minor=t.amount_minor, decimals=t.decimals,
        ts_utc=t.ts_utc.replace(tzinfo=timezone.utc), ts_precision=t.ts_precision,
        ref=t.ref, ref_kind=t.ref_kind, corroboration=t.corroboration,
        raw_unmapped_data=json.loads(t.raw_unmapped_json or "{}"), source_doc_hash=t.source_doc_hash,
    ) for t in tx_records]
    canonical_by_id = {tx.id: tx for tx in canonical_txs}
    seed = canonical_by_id[req.seed_transfer_id]
    input_snapshot = [{
        "id": tx.id, "rail": tx.rail.value, "source": tx.src_id, "target": tx.dst_id,
        "asset": tx.asset, "amount_minor": tx.amount_minor, "decimals": tx.decimals,
        "ts_utc": tx.ts_utc.isoformat(), "ts_precision": tx.ts_precision,
        "ref": tx.ref, "ref_kind": tx.ref_kind, "corroboration": tx.corroboration,
        "raw_unmapped_data": tx.raw_unmapped_data, "source_doc_hash": tx.source_doc_hash,
    } for tx in sorted(canonical_txs, key=lambda item: (item.id, item.ts_utc))]
    config_snapshot = asdict(config)
    analysis_manifest = {
        "schema": "mantis.analysis-manifest.v1",
        "algorithm_bundle": "mantis-default-analysis-v1",
        "trace_strategy": "time_respecting_breadth_first_v1",
        "seam_solver": "time_value_constrained_matching_v1",
        "typology_rules": ["rapid_pass_through_v1", "structuring_v1", "peel_chain_v1"],
        "input_transfer_count": len(input_snapshot),
        "input_snapshot_sha256": stable_sha256(input_snapshot),
        "source_document_sha256": sorted({
            tx.source_doc_hash for tx in canonical_txs if tx.source_doc_hash
        }),
        "configuration_sha256": stable_sha256(config_snapshot),
    }
    analysis_manifest["manifest_sha256"] = stable_sha256(analysis_manifest)
    trace_result = MultiStrategyTracer(config.tracer).trace_forward(seed, canonical_txs)

    entity_kinds = {e.id: e.kind for e in db.query(EntityDB).filter(EntityDB.case_id == case_id).all()}
    fiat_debits = [t for t in canonical_txs if t.asset.upper() == "INR" and entity_kinds.get(t.src_id) == EntityKind.BANK_ACCOUNT.value]
    crypto_credits = [t for t in canonical_txs if t.asset.upper() == "USDT" and entity_kinds.get(t.dst_id) == EntityKind.WALLET.value]
    seam_matches = MultiRailSeamSolver(config.seam).solve_matches(
        fiat_debits, crypto_credits, market_fx_rate=req.market_fx_rate
    )
    # A seeded analysis only presents cross-rail candidates incident to that
    # exact transfer. Other candidates remain available through separate runs.
    seam_matches = [sm for sm in seam_matches if seed.id in {sm.fiat_transfer_id, sm.chain_transfer_id}]

    # The case-level seam table represents the latest analysis state. Historical
    # runs retain their own full results in TraceRunDB.result_json.
    db.query(SeamMatchDB).filter(SeamMatchDB.case_id == case_id).delete(synchronize_session=False)

    for sm in seam_matches:
        existing = db.query(SeamMatchDB).filter(SeamMatchDB.case_id == case_id, SeamMatchDB.id == sm.id).first()
        if not existing:
            db.add(SeamMatchDB(
                id=sm.id,
                case_id=case_id,
                fiat_transfer_id=sm.fiat_transfer_id,
                chain_transfer_id=sm.chain_transfer_id,
                label=sm.label.value,
                confidence_score=sm.score,
                delta_t_seconds=sm.delta_t_seconds,
                inr_amount_minor=sm.inr_amount_minor,
                usdt_amount_minor=sm.usdt_amount_minor,
                implied_rate=sm.implied_rate,
                deviation_pct=sm.deviation_pct,
                reason=sm.reason
            ))

    # Indicators remain associated with their supporting transaction IDs for review.
    detectors = [
        RapidPassThroughDetector(config.typology),
        StructuringDetector(config.typology),
        PeelChainDetector(config.typology)
    ]
    detected_episodes = []
    for d in detectors:
        for ep in d.analyze(canonical_txs):
            detected_episodes.append(ep)

    episode_ids = []
    persisted_episodes = db.query(EpisodeDB).filter(EpisodeDB.case_id == case_id).all()
    existing_episode_keys = {(ep.pattern, ep.entity_id, ep.evidence_tx_ids_json or "[]"): ep.id for ep in persisted_episodes}
    for ep in detected_episodes:
        evidence_json = json.dumps(ep.evidence_tx_ids, separators=(",", ":"))
        key = (ep.pattern, ep.entity_id, evidence_json)
        existing_id = existing_episode_keys.get(key)
        if existing_id:
            episode_ids.append(existing_id)
            continue
        stored = EpisodeDB(
            case_id=case_id, pattern=ep.pattern, entity_id=ep.entity_id, confidence=ep.confidence,
            evidence_tx_ids_json=evidence_json, metrics_json=json.dumps(ep.metrics),
            benign_hypotheses_json=json.dumps(ep.benign_hypotheses)
        )
        db.add(stored)
        db.flush()
        existing_episode_keys[key] = stored.id
        episode_ids.append(stored.id)

    run_id = f"trace_{uuid.uuid4().hex[:16]}"
    serialized_edges = [{
        "id": edge.transfer.id, "source": edge.transfer.src_id, "target": edge.transfer.dst_id,
        "amount": format_minor(edge.transfer.amount_minor, edge.transfer.decimals, edge.transfer.asset),
        "asset": edge.transfer.asset, "rail": edge.transfer.rail.value,
        "ts_utc": edge.transfer.ts_utc.isoformat(), "ref": edge.transfer.ref,
        "source_doc_hash": edge.transfer.source_doc_hash, "label": edge.label.value,
    } for edge in trace_result["edges"]]
    seam_payload = [{"id": sm.id, "fiat_transfer_id": sm.fiat_transfer_id,
                     "chain_transfer_id": sm.chain_transfer_id, "score": sm.score,
                     "label": sm.label.value, "reason": sm.reason} for sm in seam_matches]
    episode_payload = [{"id": episode_ids[idx], "pattern": ep.pattern, "entity_id": ep.entity_id,
                        "score": ep.confidence, "evidence_tx_ids": ep.evidence_tx_ids,
                        "metrics": ep.metrics} for idx, ep in enumerate(detected_episodes)]
    trace_payload = {
        "seed_transfer_id": seed.id,
        "node_ids": trace_result["nodes"],
        "edges": serialized_edges,
        "hop_depth": trace_result["hop_depth"],
        "seam_matches": seam_payload,
        "episodes": episode_payload,
        "market_fx_rate": req.market_fx_rate,
        "market_fx_source": req.market_fx_source,
        "market_fx_observed_at": req.market_fx_observed_at.astimezone(timezone.utc).isoformat()
        if req.market_fx_observed_at else None,
        "analysis_manifest": analysis_manifest,
    }
    db.add(TraceRunDB(id=run_id, case_id=case_id, seed_transfer_id=seed.id, result_json=json.dumps(trace_payload)))
    append_audit(db, case_id, "analysis.trace_run", {
        "trace_run_id": run_id, "seed_transfer_id": seed.id,
        "analysis_manifest_sha256": analysis_manifest["manifest_sha256"],
        "market_fx_rate": req.market_fx_rate,
        "market_fx_source": req.market_fx_source,
        "market_fx_observed_at": req.market_fx_observed_at.astimezone(timezone.utc).isoformat()
        if req.market_fx_observed_at else None,
        "flow_edge_count": len(serialized_edges), "seam_candidate_count": len(seam_payload),
        "indicator_count": len(episode_payload),
    })
    db.commit()
    return {
        "status": "complete",
        "trace_run_id": run_id,
        "trace": {"seed_transfer_id": seed.id, "node_ids": trace_result["nodes"],
                  "edges": serialized_edges, "hop_depth": trace_result["hop_depth"]},
        "seam_matches": seam_payload,
        "episodes": episode_payload,
        "market_fx_rate": req.market_fx_rate,
        "market_fx_source": req.market_fx_source,
        "market_fx_observed_at": req.market_fx_observed_at.astimezone(timezone.utc).isoformat()
        if req.market_fx_observed_at else None,
        "analysis_manifest": analysis_manifest,
        "market_fx_rate_status": "investigator_supplied" if req.market_fx_rate is not None else "not_supplied; no FX seam candidates generated",
        "seam_matches_count": len(seam_matches),
        "episodes_detected_count": len(detected_episodes)
    }

@app.get("/api/cases/{case_id}/trace-runs")
def list_trace_runs(case_id: str, db: Session = Depends(get_db)):
    if not db.query(CaseDB.id).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    runs = db.query(TraceRunDB).filter(TraceRunDB.case_id == case_id).order_by(TraceRunDB.created_at.desc()).limit(50).all()
    return [{"id": run.id, "seed_transfer_id": run.seed_transfer_id,
             "created_at": run.created_at.replace(tzinfo=timezone.utc).isoformat(),
             "hop_depth": json.loads(run.result_json).get("hop_depth", 0),
             "transfer_count": len(json.loads(run.result_json).get("edges", []))} for run in runs]

@app.get("/api/cases/{case_id}/trace-runs/{trace_run_id}")
def get_trace_run(case_id: str, trace_run_id: str, db: Session = Depends(get_db)):
    run = db.query(TraceRunDB).filter(TraceRunDB.case_id == case_id, TraceRunDB.id == trace_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Trace run not found in case")
    return {"id": run.id, "seed_transfer_id": run.seed_transfer_id,
            "created_at": run.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "result": json.loads(run.result_json)}

@app.get("/api/cases/{case_id}/audit")
def get_case_audit(case_id: str, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    if not db.query(CaseDB.id).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    rows = db.query(AuditLogDB).filter(AuditLogDB.case_id == case_id).order_by(AuditLogDB.seq.asc()).all()
    previous_hash = "0" * 64
    valid = True
    results = []
    for row in rows:
        payload = json.loads(row.payload_json or "{}")
        event = {"case_id": row.case_id, "actor": row.actor, "action": row.action,
                 "payload": payload, "prev_hash": row.prev_hash,
                 "at": row.at.replace(tzinfo=timezone.utc).isoformat()}
        expected = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        valid = valid and row.prev_hash == previous_hash and hmac.compare_digest(row.this_hash, expected)
        previous_hash = row.this_hash
        results.append({"sequence": row.seq, "at": row.at.replace(tzinfo=timezone.utc).isoformat(),
                        "actor": row.actor, "action": row.action, "payload": payload,
                        "previous_hash": row.prev_hash, "event_hash": row.this_hash})
    return {"events": results[-limit:], "integrity": "valid" if valid else "broken", "checked_events": len(results)}

# ---------------------------------------------------------------------------
# INVESTIGATION GAP PLANNER & RECOVERY ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/api/cases/{case_id}/gaps")
def get_case_gaps(case_id: str, db: Session = Depends(get_db)):
    """Returns all Investigation Gap Planner requests and Section 94 BNSS notice drafts."""
    reqs = db.query(InvestigationDataRequestDB).filter(InvestigationDataRequestDB.case_id == case_id).all()
    return [
        {
            "id": r.id,
            "target_institution": r.target_institution,
            "custody_account_or_wallet": r.custody_account_or_wallet,
            "unresolved_amount": r.unresolved_amount_formatted,
            "asks": json.loads(r.asks_json or "[]"),
            "statutory_basis": r.statutory_basis,
            "legal_draft": r.legal_draft_text,
            "urgency": r.urgency
        }
        for r in reqs
    ]

@app.get("/api/cases/{case_id}/recovery")
def get_case_recovery(case_id: str, db: Session = Depends(get_db)):
    """Recovery is unavailable until verified balances and residual taint are persisted."""
    if not db.query(CaseDB).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "status": "unavailable",
        "targets": [],
        "reason": "The case schema does not store verified current balances or computed taint residuals; no lien amount can be calculated from the available evidence.",
    }

# ---------------------------------------------------------------------------
# GROUNDED AI COPILOT ENDPOINT
# ---------------------------------------------------------------------------
@app.post("/api/cases/{case_id}/copilot")
def query_copilot(case_id: str, req: CopilotQueryRequest, db: Session = Depends(get_db)):
    """Grounded AI Copilot that queries verified database records."""
    transfers = db.query(TransferDB).filter(TransferDB.case_id == case_id).all()
    if not db.query(CaseDB).filter(CaseDB.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    entities = db.query(EntityDB).filter(EntityDB.case_id == case_id).all()
    episodes = db.query(EpisodeDB).filter(EpisodeDB.case_id == case_id).all()
    seams = db.query(SeamMatchDB).filter(SeamMatchDB.case_id == case_id).all()
    gaps = db.query(InvestigationDataRequestDB).filter(InvestigationDataRequestDB.case_id == case_id).all()

    canonical_txs = [
        CanonicalTransaction(
            id=t.id, case_id=t.case_id, rail=Rail(t.rail), src_id=t.src_id, dst_id=t.dst_id,
            asset=t.asset, amount_minor=t.amount_minor, decimals=t.decimals,
            ts_utc=t.ts_utc.replace(tzinfo=timezone.utc), ref=t.ref, corroboration=t.corroboration
        ) for t in transfers
    ]

    flow_edges = [
        FlowEdge(
            id=f"flow_{t.id}", source=t.src_id, target=t.dst_id, transfer=tx,
            label=LinkLabel.CONFIRMED if t.corroboration > 1 else LinkLabel.INFERRED,
            evidence_reason=f"Recorded transfer {t.ref or t.id}",
        )
        for t, tx in zip(transfers, canonical_txs)
    ]
    seam_edges = [
        SeamEdge(
            id=s.id, fiat_transfer_id=s.fiat_transfer_id, chain_transfer_id=s.chain_transfer_id,
            source_entity="", target_entity="", score=s.confidence_score,
            label=LinkLabel(s.label), delta_t_seconds=s.delta_t_seconds,
            inr_amount_minor=s.inr_amount_minor, usdt_amount_minor=s.usdt_amount_minor,
            implied_rate=s.implied_rate, deviation_pct=s.deviation_pct,
            assigned_vasp=s.assigned_vasp, reason=s.reason,
        ) for s in seams
    ]
    grounded_episodes = [
        Episode(
            pattern=e.pattern, entity_id=e.entity_id, confidence=e.confidence,
            evidence_tx_ids=json.loads(e.evidence_tx_ids_json or "[]"),
            metrics=json.loads(e.metrics_json or "{}"),
            benign_hypotheses=json.loads(e.benign_hypotheses_json or "[]"),
        ) for e in episodes
    ]
    grounded_gaps = [
        InvestigationDataRequest(
            id=g.id, case_id=g.case_id, entity_id=g.entity_id,
            target_institution=g.target_institution,
            custody_account_or_wallet=g.custody_account_or_wallet,
            unresolved_amount_formatted=g.unresolved_amount_formatted,
            asks=json.loads(g.asks_json or "[]"), statutory_basis=g.statutory_basis,
            legal_draft_text=g.legal_draft_text, urgency=g.urgency, status=g.status,
        ) for g in gaps
    ]

    copilot = GroundedCopilotQuerier(
        transactions=canonical_txs,
        flow_edges=flow_edges,
        seam_edges=seam_edges,
        episodes=grounded_episodes,
        gap_requests=grounded_gaps,
        entity_directory={e.id: {"display": e.display} for e in entities}
    )

    return copilot.query(req.question)

# ---------------------------------------------------------------------------
# WEB UI DASHBOARD (Served at root '/')
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    dashboard_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "index.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>MANTIS API Running</h1><p>Visit <a href='/docs'>/docs</a> for Swagger UI.</p>"
