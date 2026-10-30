"""
MANTIS End-to-End Dynamic Intelligence Pipeline Test
Tests:
1. Dynamic Ingestion & Invariant Reconciliation across multiple bank CSVs
2. Uncalibrated Record-Pair Review Ranking
3. Multi-Rail Constrained Seam Matching (Fiat Debit <-> Crypto Credit)
4. Time-Monotonic Graph Tracing & 3 Taint Models (Poison, Haircut, FIFO)
5. Custody Boundary Detection & Investigation Gap Planning (Sec 94 BNSS)
6. Typology Detection with Benign Alternative Explanations
7. Recovery Management & Section 106 BNSS Disputed Lien Calculation
8. AI Copilot Grounded Query Execution
"""

import os
import json
import sys
import io

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from datetime import datetime, timezone
from mantis.config import MantisConfig
from mantis.core.models import CanonicalTransaction, CanonicalEntity, Rail, EntityKind, LinkLabel
from mantis.ingest.bank_statement import DynamicBankStatementAdapter
from mantis.correlation.record_linkage import FellegiSunterLinker
from mantis.correlation.seam_solver import MultiRailSeamSolver
from mantis.graph.tracer import MultiStrategyTracer
from mantis.graph.gap_planner import InvestigationGapPlanner
from mantis.intelligence.typologies import RapidPassThroughDetector, StructuringDetector, PeelChainDetector
from mantis.recovery.manager import RecoveryManager
from mantis.copilot.grounded_querier import GroundedCopilotQuerier

def run_e2e_pipeline():
    print("=" * 80)
    print("MANTIS 2.0: MULTI-RAIL FINANCIAL INTELLIGENCE PIPELINE TEST")
    print("=" * 80)

    config = MantisConfig()
    scenario_dir = os.path.join(os.path.dirname(__file__), "data", "scenario_1")

    # -----------------------------------------------------------------------
    # STEP 1: DYNAMIC INGESTION & MATHEMATICAL RECONCILIATION
    # -----------------------------------------------------------------------
    print("\n[STEP 1] Ingesting Bank Statements Dynamically...")
    all_transactions = []
    reconciliations = []

    files_and_owners = [
        ("victim_hdfc_statement.csv", "entity_victim", "Dr. Rajesh Sharma"),
        ("layer1_mule_sbi_statement.csv", "entity_mule1", "Ramesh Kumar"),
        ("layer2_mule_axis_statement.csv", "entity_mule2", "Aman Verma"),
    ]

    for fname, owner_id, owner_name in files_and_owners:
        fpath = os.path.join(scenario_dir, fname)
        with open(fpath, "rb") as f:
            raw_bytes = f.read()

        adapter = DynamicBankStatementAdapter(
            document_id=f"doc_{fname}",
            case_id="CASE_2026_NCRP_8819",
            raw_bytes=raw_bytes,
            filename=fname,
            account_owner_id=owner_id
        )
        txs, summary = adapter.parse()
        all_transactions.extend(txs)
        reconciliations.append(summary)
        assert summary["reconciled"], f"{fname} did not reconcile: {summary['discrepancy_minor']} minor units"

        print(f"  -> {fname}: Ingested {len(txs)} txs | "
              f"Credits: ₹{summary['total_credits_minor']/100:,.2f} | "
              f"Debits: ₹{summary['total_debits_minor']/100:,.2f} | "
              f"Reconciled: {'PASS' if summary['reconciled'] else 'FAIL (Margin: ' + str(summary['discrepancy_minor']) + ')'}")

    # Also ingest on-chain TRON USDT transfers
    tron_path = os.path.join(scenario_dir, "tron_usdt_chain_feed.json")
    with open(tron_path, "r", encoding="utf-8") as f:
        tron_data = json.load(f)

    for c_event in tron_data:
        dt = datetime.fromtimestamp(c_event["block_timestamp"] / 1000.0, tz=timezone.utc)
        all_transactions.append(CanonicalTransaction(
            id=c_event["tx_hash"][:16],
            case_id="CASE_2026_NCRP_8819",
            rail=Rail.TRON,
            src_id=c_event["from_address"],
            dst_id=c_event["to_address"],
            asset="USDT",
            amount_minor=c_event["amount_minor"],
            decimals=6,
            ts_utc=dt,
            ref=c_event["tx_hash"],
            ref_kind="tx_hash",
            corroboration=2
        ))
    print(f"  -> TRON Chain Feed: Ingested {len(tron_data)} on-chain events.")

    # -----------------------------------------------------------------------
    # STEP 2: PROBABILISTIC RECORD LINKAGE (Fellegi-Sunter)
    # -----------------------------------------------------------------------
    print("\n[STEP 2] Testing Candidate Record Review Ranking...")
    linker = FellegiSunterLinker()
    rec_complaint = {
        "account_number_suffix": "6789",
        "vpa_handle": "ramesh.k92@oksbi",
        "phone_number": "9711234567",
        "name_token_jaccard": "Ramesh Kumar"
    }
    rec_statement = {
        "account_number_suffix": "6789",
        "vpa_handle": "ramesh.k92@okaxis", # Different PSP handle
        "phone_number": "9711234567",
        "name_token_jaccard": "Ramesh Kumar"
    }
    link_result = linker.compare_records(rec_complaint, rec_statement)
    assert link_result["review_rank_weight"] > 0, "Expected matching complaint and statement records to rank highly for review"
    assert link_result["calibration"] == "uncalibrated_review_rank_only"
    assert link_result["label"] != LinkLabel.CONFIRMED, "Uncalibrated linkage cannot confirm identity"
    print(f"  -> Review Rank Weight: {link_result['review_rank_weight']:.2f} | Label: {link_result['label'].value} (uncalibrated)")
    print(f"     Evidence Factors: {[e['field'] for e in link_result['evidence']]}")

    # -----------------------------------------------------------------------
    # STEP 3: MULTI-RAIL SEAM SOLVER
    # -----------------------------------------------------------------------
    print("\n[STEP 3] Running Multi-Rail Constrained Seam Solver...")
    fiat_debits = [t for t in all_transactions if t.asset == "INR" and t.src_id == "entity_mule2"]
    crypto_credits = [t for t in all_transactions if t.asset == "USDT"]

    seam_solver = MultiRailSeamSolver(config.seam)
    seam_matches = seam_solver.solve_matches(fiat_debits, crypto_credits, market_fx_rate=90.0)
    assert seam_matches, "Expected the scenario's fiat-to-crypto transfer to produce a seam candidate"
    print(f"  -> Solved Seam Matches: {len(seam_matches)} identified.")
    for sm in seam_matches:
        print(f"     * Seam Edge: {sm.reason} | Score: {sm.score} ({sm.label.value})")

    # -----------------------------------------------------------------------
    # STEP 4: TIME-MONOTONIC GRAPH TRACER & TAINT REPLAY
    # -----------------------------------------------------------------------
    print("\n[STEP 4] Executing Time-Monotonic Graph Tracer & Taint Models...")
    # Find seed transaction (Victim -> Mule 1)
    seed_tx = next(t for t in all_transactions if t.src_id == "entity_victim" and t.amount_minor == 10000000)

    tracer = MultiStrategyTracer(config.tracer)
    trace_res = tracer.trace_forward(seed_tx, all_transactions)
    assert len(trace_res["edges"]) > 1, "Expected reference-linked transactions to continue the forward trail"
    assert trace_res["hop_depth"] > 0, "Expected the trace to report at least one downstream hop"
    print(f"  -> Forward Trace complete: {len(trace_res['nodes'])} entities, {len(trace_res['edges'])} flow edges.")

    balances = {
        "entity_victim": 8397050,
        "entity_mule1": 124000,
        "entity_mule2": 95000,
        "entity_mule3": 4000000 # Pooja Singh: ₹40,000 undrained
    }
    traced_txs = [e.transfer for e in trace_res["edges"]]
    taint_res = tracer.compute_taint_models(seed_tx, traced_txs, balances)
    assert taint_res["poison_results"] and taint_res["haircut_results"], "Expected taint models to produce balances"
    print(f"  -> Taint Models Computed:")
    print(f"     Poison:  {taint_res['poison_results']}")
    print(f"     Haircut: {taint_res['haircut_results']}")
    print(f"     Model Divergence Alert: {taint_res['model_divergence_alert']}")

    # -----------------------------------------------------------------------
    # STEP 5: CUSTODY BOUNDARY DETECTOR & GAP PLANNER
    # -----------------------------------------------------------------------
    print("\n[STEP 5] Checking Custody Boundaries & Investigation Gap Planner...")
    gap_planner = InvestigationGapPlanner(config.custody)
    p2p_entity = CanonicalEntity(
        id="entity_krypton_p2p",
        kind=EntityKind.EXCHANGE,
        display="Krypton P2P Escrow Exchange",
        risk_tags=["p2p_onramp", "exchange"]
    )
    p2p_tx = next((t for t in all_transactions if t.dst_id.startswith("cp_")), None)
    gap_req = None
    if p2p_tx:
        gap_req = gap_planner.inspect_boundary("CASE_2026_NCRP_8819", p2p_tx, p2p_entity)
        if gap_req:
            print(f"  -> GAP IDENTIFIED: Reached {gap_req.target_institution} (Unresolved: {gap_req.unresolved_amount_formatted})")
            print(f"     Statutory Basis: {gap_req.statutory_basis}")
            print(f"     Asks: {gap_req.asks[0]}")
    assert gap_req is not None, "Expected the scenario custody boundary to produce a review draft"

    # -----------------------------------------------------------------------
    # STEP 6: TYPOLOGY DETECTORS WITH BENIGN COUNTER-HYPOTHESES
    # -----------------------------------------------------------------------
    print("\n[STEP 6] Running Typology Detectors...")
    detectors = [
        RapidPassThroughDetector(config.typology),
        StructuringDetector(config.typology),
        PeelChainDetector(config.typology)
    ]
    all_episodes = []
    for d in detectors:
        episodes = d.analyze(all_transactions)
        all_episodes.extend(episodes)
        for ep in episodes:
            print(f"  -> [FLAGGED] {ep.pattern.upper()} at '{ep.entity_id}' (Conf: {ep.confidence*100:.1f}%) | "
                  f"Alt Hypothesis: '{ep.benign_hypotheses[0]['explanation']}'")

    # -----------------------------------------------------------------------
    # STEP 7: RECOVERY MANAGEMENT & DISPUTED LIENS
    # -----------------------------------------------------------------------
    print("\n[STEP 7] Generating Recovery Action Targets & Section 106 BNSS Liens...")
    rec_mgr = RecoveryManager()
    entity_dir = {
        "entity_victim": {"name": "Dr. Rajesh Sharma", "kind": "bank_account", "bank": "HDFC Bank"},
        "entity_mule1": {"name": "Ramesh Kumar", "kind": "bank_account", "bank": "State Bank of India", "account_no": "XXXX6789"},
        "entity_mule2": {"name": "Aman Verma", "kind": "bank_account", "bank": "Axis Bank", "account_no": "XXXX7890"},
        "entity_mule3": {"name": "Pooja Singh", "kind": "bank_account", "bank": "ICICI Bank", "account_no": "XXXX7890"}
    }
    targets = rec_mgr.evaluate_targets(
        case_id="CASE_2026_NCRP_8819",
        tainted_residuals=taint_res["haircut_results"],
        account_balances=balances,
        entity_directory=entity_dir,
        last_seen_times={"entity_mule3": datetime.now(timezone.utc)}
    )
    assert targets and all(t.disputed_lien_minor <= t.current_balance_minor for t in targets), "Recovery figures must be non-empty and capped by supplied balances"
    print(f"  -> Ranked Recovery Targets: {len(targets)}")
    for tg in targets:
        print(f"     * Target: {tg.entity_display} ({tg.institution}) | "
              f"Disputed Lien: {tg.statutory_action} | Score: {tg.priority_score} ({tg.urgency})")

    # -----------------------------------------------------------------------
    # STEP 8: AI INVESTIGATION COPILOT GROUNDED QUERY
    # -----------------------------------------------------------------------
    print("\n[STEP 8] Testing AI Investigation Copilot Grounded Queries...")
    copilot = GroundedCopilotQuerier(
        transactions=all_transactions,
        flow_edges=trace_res["edges"],
        seam_edges=seam_matches,
        episodes=all_episodes,
        gap_requests=[gap_req] if gap_req else [],
        entity_directory=entity_dir
    )

    questions = [
        "What are the 3 largest transactions in this case?",
        "What suspicious patterns were detected?",
        "What information is missing or required to complete this trail?",
        "Did any money reach cryptocurrency or USDT?"
    ]

    for q in questions:
        ans = copilot.query(q)
        print(f"\n  Q: '{q}'")
        print(f"  A: {ans['answer']}")
        print(f"     Confidence: {ans['confidence']} | Cited TxIDs: {ans['cited_tx_ids'][:2]}")

    print("\n" + "=" * 80)
    print("[SUCCESS] Scenario pipeline checks passed.")
    print("=" * 80)

if __name__ == "__main__":
    run_e2e_pipeline()
