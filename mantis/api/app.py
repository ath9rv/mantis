"""
MANTIS Production FastAPI Application
Provides RESTful APIs for case management, statement ingestion, multi-strategy tracing,
bipartite seam matching, typology detection, custody gap planning, and grounded AI copilot.
"""

import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from mantis.config import MantisConfig
from mantis.db.session import get_db, init_db, engine
from mantis.db.models import (
    CaseDB, DocumentDB, StatementReconciliationDB, EntityDB, TransferDB,
    SeamMatchDB, EpisodeDB, InvestigationDataRequestDB, AuditLogDB
)
from mantis.core.models import CanonicalTransaction, CanonicalEntity, Rail, EntityKind, LinkLabel
from mantis.ingest.bank_statement import DynamicBankStatementAdapter
from mantis.correlation.seam_solver import MultiRailSeamSolver
from mantis.graph.tracer import MultiStrategyTracer
from mantis.graph.gap_planner import InvestigationGapPlanner
from mantis.intelligence.typologies import RapidPassThroughDetector, StructuringDetector, PeelChainDetector
from mantis.recovery.manager import RecoveryManager
from mantis.copilot.grounded_querier import GroundedCopilotQuerier

# Initialize Database Schema
init_db()

app = FastAPI(
    title="MANTIS API",
    description="Multi-Rail Financial Crime Trail Reconstruction Platform",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = MantisConfig()

# Pydantic Schemas
class CaseCreateRequest(BaseModel):
    title: str
    complaint_ref: Optional[str] = None
    jurisdiction: Optional[str] = "State Cyber Crime Police Station"
    investigating_officer: Optional[str] = "Inspector Cyber Forensics"

class CopilotQueryRequest(BaseModel):
    question: str

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
    case_num = f"NCRP-{datetime.now().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
    new_case = CaseDB(
        case_number=case_num,
        title=req.title,
        complaint_ref=req.complaint_ref or case_num,
        jurisdiction=req.jurisdiction,
        investigating_officer=req.investigating_officer,
        params_json=json.dumps(config.__dict__, default=str)
    )
    db.add(new_case)
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

    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()

    # Create account entity for this statement
    owner_id = f"entity_{uuid.uuid4().hex[:8]}"
    owner_entity = EntityDB(
        id=owner_id,
        case_id=case_id,
        kind="bank_account",
        display=account_owner_name or file.filename.replace(".csv", ""),
        observed=True
    )
    db.add(owner_entity)

    # Ingest using DynamicBankStatementAdapter
    adapter = DynamicBankStatementAdapter(
        document_id=f"doc_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        raw_bytes=content,
        filename=file.filename,
        account_owner_id=owner_id
    )
    txs, summary = adapter.parse()

    # Save document record
    doc = DocumentDB(
        id=adapter.document_id,
        case_id=case_id,
        sha256=sha256,
        filename=file.filename,
        mime="text/csv",
        parse_status="ok" if summary["reconciled"] else "review"
    )
    db.add(doc)

    # Save reconciliation
    rec = StatementReconciliationDB(
        document_id=doc.id,
        account_identifier=owner_id,
        opening_balance_minor=summary["opening_balance_minor"],
        closing_balance_minor=summary["closing_balance_minor"],
        calculated_balance_minor=summary["opening_balance_minor"] + summary["total_credits_minor"] - summary["total_debits_minor"],
        total_credits_minor=summary["total_credits_minor"],
        total_debits_minor=summary["total_debits_minor"],
        reconciled=summary["reconciled"],
        error_margin_minor=summary["discrepancy_minor"]
    )
    db.add(rec)

    # Save transactions
    for tx in txs:
        # Ensure counterparty entity exists
        cp = db.query(EntityDB).filter(EntityDB.id == tx.dst_id).first()
        if not cp and tx.dst_id != owner_id:
            db.add(EntityDB(id=tx.dst_id, case_id=case_id, kind="bank_account", display=tx.dst_id, observed=True))
        cp_src = db.query(EntityDB).filter(EntityDB.id == tx.src_id).first()
        if not cp_src and tx.src_id != owner_id:
            db.add(EntityDB(id=tx.src_id, case_id=case_id, kind="bank_account", display=tx.src_id, observed=True))

        db_tx = TransferDB(
            id=tx.id,
            case_id=case_id,
            rail=tx.rail.value,
            src_id=tx.src_id,
            dst_id=tx.dst_id,
            asset=tx.asset,
            amount_minor=tx.amount_minor,
            decimals=tx.decimals,
            ts_utc=tx.ts_utc,
            ts_precision=tx.ts_precision,
            ref=tx.ref,
            ref_kind=tx.ref_kind,
            corroboration=tx.corroboration,
            raw_unmapped_json=json.dumps(tx.raw_unmapped_data),
            source_doc_hash=sha256
        )
        db.add(db_tx)

    db.commit()
    return {
        "document_id": doc.id,
        "sha256": sha256,
        "transactions_imported": len(txs),
        "reconciliation": summary
    }

# ---------------------------------------------------------------------------
# GRAPH & INVESTIGATION TRACE ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/api/cases/{case_id}/graph")
def get_case_graph(case_id: str, db: Session = Depends(get_db)):
    """Returns the Cytoscape.js compatible graph payload with flow, assoc, and seam edges."""
    transfers = db.query(TransferDB).filter(TransferDB.case_id == case_id).all()
    entities = db.query(EntityDB).filter(EntityDB.case_id == case_id).all()
    seams = db.query(SeamMatchDB).filter(SeamMatchDB.case_id == case_id).all()

    nodes = []
    for ent in entities:
        nodes.append({
            "data": {
                "id": ent.id,
                "label": ent.display,
                "kind": ent.kind,
                "risk_tags": json.loads(ent.risk_tags_json or "[]"),
                "is_custody_boundary": ent.is_custody_boundary
            }
        })

    edges = []
    for tx in transfers:
        factor = 10 ** tx.decimals
        amt_fmt = f"₹{tx.amount_minor / factor:,.2f}" if tx.asset == "INR" else f"{tx.amount_minor / factor:.2f} {tx.asset}"
        edges.append({
            "data": {
                "id": f"flow_{tx.id}",
                "source": tx.src_id,
                "target": tx.dst_id,
                "edge_class": "flow",
                "label": "confirmed" if tx.corroboration > 1 else "inferred",
                "amount": amt_fmt,
                "rail": tx.rail,
                "ref": tx.ref,
                "reason": f"Corroborated by {tx.corroboration} source(s)"
            }
        })

    for sm in seams:
        edges.append({
            "data": {
                "id": f"seam_{sm.id}",
                "source": sm.fiat_transfer_id,
                "target": sm.chain_transfer_id,
                "edge_class": "seam",
                "label": sm.label,
                "amount": f"₹{sm.inr_amount_minor / 100:,.0f} ↔ {sm.usdt_amount_minor / 1e6:.1f} USDT",
                "score": sm.confidence_score,
                "reason": sm.reason
            }
        })

    return {"elements": {"nodes": nodes, "edges": edges}}

@app.post("/api/cases/{case_id}/trace")
def execute_trace(case_id: str, db: Session = Depends(get_db)):
    """Executes time-monotonic trace, seam solver, and typology detectors across all case data."""
    tx_records = db.query(TransferDB).filter(TransferDB.case_id == case_id).all()
    if not tx_records:
        raise HTTPException(status_code=400, detail="No transactions available in this case to trace.")

    # Convert to canonical objects
    canonical_txs = [
        CanonicalTransaction(
            id=t.id,
            case_id=t.case_id,
            rail=Rail(t.rail),
            src_id=t.src_id,
            dst_id=t.dst_id,
            asset=t.asset,
            amount_minor=t.amount_minor,
            decimals=t.decimals,
            ts_utc=t.ts_utc.replace(tzinfo=timezone.utc),
            ref=t.ref,
            corroboration=t.corroboration
        )
        for t in tx_records
    ]

    # 1. Run Seam Solver (Fiat debits <-> Crypto credits)
    fiat_debits = [t for t in canonical_txs if t.asset == "INR"]
    crypto_credits = [t for t in canonical_txs if t.asset == "USDT"]
    seam_solver = MultiRailSeamSolver(config.seam)
    seam_matches = seam_solver.solve_matches(fiat_debits, crypto_credits)

    for sm in seam_matches:
        existing = db.query(SeamMatchDB).filter(SeamMatchDB.id == sm.id).first()
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

    # 2. Run Typology Detectors
    detectors = [
        RapidPassThroughDetector(config.typology),
        StructuringDetector(config.typology),
        PeelChainDetector(config.typology)
    ]
    detected_episodes = []
    for d in detectors:
        for ep in d.analyze(canonical_txs):
            detected_episodes.append(ep)
            db.add(EpisodeDB(
                case_id=case_id,
                pattern=ep.pattern,
                entity_id=ep.entity_id,
                confidence=ep.confidence,
                evidence_tx_ids_json=json.dumps(ep.evidence_tx_ids),
                metrics_json=json.dumps(ep.metrics),
                benign_hypotheses_json=json.dumps(ep.benign_hypotheses)
            ))

    db.commit()
    return {
        "status": "success",
        "seam_matches_count": len(seam_matches),
        "episodes_detected_count": len(detected_episodes)
    }

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
    """Calculates Section 106 BNSS compliant disputed liens and ranked recovery targets."""
    transfers = db.query(TransferDB).filter(TransferDB.case_id == case_id).all()
    entities = db.query(EntityDB).filter(EntityDB.case_id == case_id).all()

    # Mock balances for demo
    entity_dir = {e.id: {"name": e.display, "kind": e.kind} for e in entities}
    balances = {e.id: 4000000 if "pooja" in e.display.lower() else 100000 for e in entities}
    residuals = {e.id: 4000000 if "pooja" in e.display.lower() else 0 for e in entities}

    rec_mgr = RecoveryManager()
    targets = rec_mgr.evaluate_targets(
        case_id=case_id,
        tainted_residuals=residuals,
        account_balances=balances,
        entity_directory=entity_dir,
        last_seen_times={e.id: datetime.now(timezone.utc) for e in entities}
    )

    return [
        {
            "target_id": t.target_id,
            "entity_display": t.entity_display,
            "institution": t.institution,
            "account_or_address": t.account_or_address,
            "disputed_lien": f"₹{t.disputed_lien_minor / (10 ** t.decimals):,.2f}",
            "priority_score": t.priority_score,
            "urgency": t.urgency,
            "statutory_action": t.statutory_action,
            "notice_draft": t.notice_draft
        }
        for t in targets
    ]

# ---------------------------------------------------------------------------
# GROUNDED AI COPILOT ENDPOINT
# ---------------------------------------------------------------------------
@app.post("/api/cases/{case_id}/copilot")
def query_copilot(case_id: str, req: CopilotQueryRequest, db: Session = Depends(get_db)):
    """Grounded AI Copilot that queries verified database records."""
    transfers = db.query(TransferDB).filter(TransferDB.case_id == case_id).all()
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

    copilot = GroundedCopilotQuerier(
        transactions=canonical_txs,
        flow_edges=[],
        seam_edges=[],
        episodes=[],
        gap_requests=[],
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
