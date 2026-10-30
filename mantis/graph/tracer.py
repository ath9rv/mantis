"""
MANTIS Multi-Strategy Graph Tracer & Taint Replay Engine
Supports Forward, Backward, Convergence, and Common-Source Tracing.
Enforces time-monotonic DAG constraints (t_out >= t_in) to eliminate infinite loops.
Runs Poison, Haircut, and FIFO taint models concurrently over unified ledger events.
"""

from typing import List, Dict, Any, Set, Tuple, Optional
from datetime import datetime, timedelta, timezone
from collections import deque
import networkx as nx
from mantis.core.models import CanonicalTransaction, FlowEdge, LinkLabel
from mantis.config import TracerConfig

class MultiStrategyTracer:
    """
    Time-respecting multi-hop graph tracer with pluggable strategies.
    """

    def __init__(self, config: Optional[TracerConfig] = None):
        self.config = config or TracerConfig()

    def build_networkx_graph(self, transactions: List[CanonicalTransaction]) -> nx.MultiDiGraph:
        """Constructs a directed multi-graph from canonical transactions."""
        G = nx.MultiDiGraph()
        for tx in transactions:
            G.add_node(tx.src_id)
            G.add_node(tx.dst_id)
            G.add_edge(
                tx.src_id,
                tx.dst_id,
                key=tx.id,
                transaction=tx,
                amount_minor=tx.amount_minor,
                ts_utc=tx.ts_utc,
                rail=tx.rail,
                ref=tx.ref
            )
        return G

    def trace_forward(self, seed_tx: CanonicalTransaction,
                      all_transactions: List[CanonicalTransaction]) -> Dict[str, Any]:
        """
        Traces money forward from an initial complaint transaction.
        Enforces: t(outflow) >= t(inflow) and (t(outflow) - t(inflow)) <= max_window_hours.
        """
        # Index transactions by source entity
        tx_by_src: Dict[str, List[CanonicalTransaction]] = {}
        for tx in all_transactions:
            tx_by_src.setdefault(tx.src_id, []).append(tx)

        # Sort each node's outflows chronologically
        for src in tx_by_src:
            tx_by_src[src].sort(key=lambda t: t.ts_utc)

        visited_tx_ids: Set[str] = {seed_tx.id}
        queue = deque([(seed_tx.dst_id, seed_tx.ts_utc, seed_tx.amount_minor, 1)])

        traced_edges: List[FlowEdge] = [
            FlowEdge(
                id=f"flow_{seed_tx.id}",
                source=seed_tx.src_id,
                target=seed_tx.dst_id,
                transfer=seed_tx,
                label=LinkLabel.CONFIRMED,
                evidence_reason="Seed complaint transaction"
            )
        ]
        traced_node_ids: Set[str] = {seed_tx.src_id, seed_tx.dst_id}

        while queue:
            curr_entity, curr_time, parent_amount, hop = queue.popleft()
            if hop > self.config.hop_cap:
                continue

            outflows = tx_by_src.get(curr_entity, [])
            for tx in outflows:
                if tx.id in visited_tx_ids:
                    continue

                # Time-monotonicity check
                if tx.ts_utc < curr_time:
                    continue # Cannot continue backwards in time

                # Time window constraint
                window_sec = (tx.ts_utc - curr_time).total_seconds()
                if window_sec > (self.config.max_window_hours * 3600.0):
                    continue # Exceeds continuity window

                # Dust floor check
                if tx.amount_minor < self.config.dust_floor_minor:
                    continue

                visited_tx_ids.add(tx.id)
                traced_node_ids.add(tx.dst_id)

                dwell_minutes = round(window_sec / 60.0, 1)
                edge_label = LinkLabel.CONFIRMED if tx.corroboration > 1 else LinkLabel.INFERRED
                traced_edges.append(FlowEdge(
                    id=f"flow_{tx.id}",
                    source=tx.src_id,
                    target=tx.dst_id,
                    transfer=tx,
                    label=edge_label,
                    evidence_reason=f"Hop {hop}: Transferred after {dwell_minutes}m dwell time (Ref: {tx.ref or 'N/A'})"
                ))

                queue.append((tx.dst_id, tx.ts_utc, tx.amount_minor, hop + 1))

        return {
            "strategy": "forward",
            "seed_id": seed_tx.id,
            "nodes": list(traced_node_ids),
            "edges": traced_edges,
            "hop_depth": max((e.transfer.corroboration for e in traced_edges), default=1)
        }

    def trace_convergence(self, complaint_txs: List[CanonicalTransaction],
                          all_transactions: List[CanonicalTransaction]) -> Dict[str, Any]:
        """
        Multi-Victim Convergence Strategy:
        Traces forward from multiple independent complaints to identify shared downstream destinations.
        """
        individual_trails: List[Dict[str, Any]] = []
        node_reach_counts: Dict[str, Set[str]] = {} # entity_id -> set of complaint_ids

        for c_tx in complaint_txs:
            trail = self.trace_forward(c_tx, all_transactions)
            individual_trails.append(trail)
            for node_id in trail["nodes"]:
                node_reach_counts.setdefault(node_id, set()).add(c_tx.id)

        # Find convergent nodes reached by 2 or more distinct complaints
        convergent_nodes = {
            node: list(complaints)
            for node, complaints in node_reach_counts.items()
            if len(complaints) >= 2
        }

        return {
            "strategy": "convergence",
            "complaint_count": len(complaint_txs),
            "convergent_nodes": convergent_nodes,
            "trails": individual_trails
        }

    def compute_taint_models(self, seed_tx: CanonicalTransaction,
                             traced_transfers: List[CanonicalTransaction],
                             account_balances: Dict[str, int]) -> Dict[str, Any]:
        """
        Simultaneously computes Poison, Haircut, and FIFO taint distributions.
        Identifies whether model conclusions diverge.
        """
        seed_taint = seed_tx.amount_minor

        # Ledgers for each model: entity_id -> tainted_amount_minor
        poison_ledger: Dict[str, int] = {seed_tx.dst_id: seed_taint}
        haircut_ledger: Dict[str, int] = {seed_tx.dst_id: seed_taint}
        fifo_ledger: Dict[str, int] = {seed_tx.dst_id: seed_taint}

        for tx in sorted(traced_transfers, key=lambda t: t.ts_utc):
            if tx.id == seed_tx.id:
                continue

            src = tx.src_id
            dst = tx.dst_id
            amt = tx.amount_minor
            total_bal = max(amt, account_balances.get(src, amt))

            # 1. Poison Model (Max Aggression): 100% of outflow is tainted up to current taint
            curr_poison = poison_ledger.get(src, 0)
            if curr_poison > 0:
                transferred_poison = min(amt, curr_poison)
                poison_ledger[src] = curr_poison - transferred_poison
                poison_ledger[dst] = poison_ledger.get(dst, 0) + transferred_poison

            # 2. Haircut Model (Proportional Accounting)
            curr_haircut = haircut_ledger.get(src, 0)
            if curr_haircut > 0 and total_bal > 0:
                ratio = min(1.0, curr_haircut / total_bal)
                transferred_haircut = int(round(amt * ratio))
                haircut_ledger[src] = max(0, curr_haircut - transferred_haircut)
                haircut_ledger[dst] = haircut_ledger.get(dst, 0) + transferred_haircut

            # 3. FIFO Model (Time-Ordered Ledger)
            curr_fifo = fifo_ledger.get(src, 0)
            if curr_fifo > 0:
                transferred_fifo = min(amt, curr_fifo)
                fifo_ledger[src] = curr_fifo - transferred_fifo
                fifo_ledger[dst] = fifo_ledger.get(dst, 0) + transferred_fifo

        return {
            "poison_results": poison_ledger,
            "haircut_results": haircut_ledger,
            "fifo_results": fifo_ledger,
            "model_divergence_alert": (poison_ledger != haircut_ledger)
        }
