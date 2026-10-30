"""
MANTIS Multi-Rail Financial Flow Reconciliation Solver
Solves a sparse one-to-one fiat-to-USDT candidate assignment across banking and blockchains.
Candidates are compared jointly within time and FX windows; split/merge flows are not modeled.
"""

from typing import List, Dict, Any, Optional
from datetime import timedelta
from bisect import bisect_left, bisect_right
from decimal import Decimal
import math
import networkx as nx
from mantis.core.models import CanonicalTransaction, SeamEdge, LinkLabel
from mantis.config import SeamConfig

class MultiRailSeamSolver:
    """
    Global reconciliation solver matching fiat debits to crypto deposits/orders.
    """

    def __init__(self, config: Optional[SeamConfig] = None):
        self.config = config or SeamConfig()
        weights = (self.config.weight_time, self.config.weight_value, self.config.weight_reference_match)
        if any(not math.isfinite(weight) or weight < 0 for weight in weights):
            raise ValueError("seam weights must be finite and non-negative")
        if not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("seam weights must sum to 1")
        if not math.isfinite(self.config.p2p_window_hours) or self.config.p2p_window_hours <= 0:
            raise ValueError("p2p_window_hours must be finite and positive")
        if not math.isfinite(self.config.fx_tolerance_pct) or self.config.fx_tolerance_pct <= 0:
            raise ValueError("fx_tolerance_pct must be finite and positive")

    def solve_matches(self, fiat_debits: List[CanonicalTransaction],
                      crypto_credits: List[CanonicalTransaction],
                      market_fx_rate: Optional[float] = None) -> List[SeamEdge]:
        """
        Computes global optimal bipartite matching between fiat debits and crypto credits.
        Considers temporal order, FX rate tolerance, and platform fees.
        """
        fx_rate = self.config.default_inr_usdt_rate if market_fx_rate is None else market_fx_rate
        if fx_rate is None:
            return []
        if not math.isfinite(fx_rate) or fx_rate <= 0:
            raise ValueError("market_fx_rate must be finite and positive")
        if self.config.fx_tolerance_pct <= 0:
            raise ValueError("fx_tolerance_pct must be positive")
        matches: List[SeamEdge] = []

        if not fiat_debits or not crypto_credits:
            return matches

        # Narrow the pair search to the configured time window before comparing
        # value. This changes work from every possible pair to only local pairs.
        candidates: List[Dict[str, Any]] = []
        crypto_sorted = sorted(crypto_credits, key=lambda tx: tx.ts_utc)
        crypto_times = [tx.ts_utc for tx in crypto_sorted]
        max_window = timedelta(hours=self.config.p2p_window_hours)
        fx_decimal = Decimal(str(fx_rate))
        for fd in fiat_debits:
            start = bisect_left(crypto_times, fd.ts_utc)
            end = bisect_right(crypto_times, fd.ts_utc + max_window)
            fiat_inr = Decimal(fd.amount_minor) / (Decimal(10) ** fd.decimals)

            for cc in crypto_sorted[start:end]:
                if fd.asset.upper() != "INR" or cc.asset.upper() != "USDT":
                    continue
                # Time Constraint: Crypto credit must occur AFTER or simultaneously with fiat debit
                delta_t_sec = (cc.ts_utc - fd.ts_utc).total_seconds()
                crypto_val = Decimal(cc.amount_minor) / (Decimal(10) ** cc.decimals)
                if crypto_val <= 0:
                    continue

                # Valuation Calculation
                implied_rate = fiat_inr / crypto_val
                deviation_pct = abs(implied_rate - fx_decimal) / fx_decimal * Decimal(100)

                if deviation_pct > Decimal(str(self.config.fx_tolerance_pct)):
                    continue # Exceeds acceptable FX band

                # Compute Component Scores
                # Time score: Exponential decay over time delta
                time_score = math.exp(-0.5 * ((delta_t_sec / 1800.0) ** 2)) # Decay half-life ~30 mins

                # Value score: Linear decay over FX deviation
                val_score = max(0.0, 1.0 - (float(deviation_pct) / self.config.fx_tolerance_pct))

                # A reference match counts only when both sources carry the same
                # explicit external order reference. Missing evidence adds no score.
                fiat_reference = str(fd.raw_unmapped_data.get("cross_rail_reference", "")).strip().casefold()
                chain_reference = str(cc.raw_unmapped_data.get("cross_rail_reference", "")).strip().casefold()
                reference_score = 1.0 if fiat_reference and fiat_reference == chain_reference else 0.0

                # Weighted Composite Affiliation Score
                composite_score = (
                    self.config.weight_time * time_score +
                    self.config.weight_value * val_score +
                    self.config.weight_reference_match * reference_score
                )

                if composite_score >= self.config.min_match_confidence:
                    candidates.append({
                        "fiat": fd,
                        "crypto": cc,
                        "score": composite_score,
                        "delta_t_sec": int(delta_t_sec),
                        "fiat_inr_minor": fd.amount_minor,
                        "crypto_minor": cc.amount_minor,
                        "implied_rate": round(float(implied_rate), 2),
                        "deviation_pct": round(float(deviation_pct), 2)
                    })

        # Find a maximum-weight one-to-one assignment, rather than greedily
        # consuming the locally best pair and potentially blocking a better total.
        candidates.sort(key=lambda x: (x["fiat"].id, x["crypto"].id))
        graph = nx.Graph()
        tie_scale = len(candidates) + 1
        candidate_by_pair = {}
        for rank, cand in enumerate(candidates):
            fid = cand["fiat"].id
            cid = cand["crypto"].id
            pair = (fid, cid)
            candidate_by_pair[pair] = cand
            graph.add_edge(
                ("fiat", fid),
                ("crypto", cid),
                weight=int(round(cand["score"] * 1_000_000)) * tie_scale + (len(candidates) - rank),
            )

        assignment = nx.algorithms.matching.max_weight_matching(graph, maxcardinality=False)
        selected_pairs = sorted(
            ((left[1], right[1]) if left[0] == "fiat" else (right[1], left[1]))
            for left, right in assignment
        )

        for fid, cid in selected_pairs:
            cand = candidate_by_pair[(fid, cid)]

            # Assign Link Label based on composite confidence
            score = cand["score"]
            if score >= 0.88:
                label = LinkLabel.INFERRED
            elif score >= 0.70:
                label = LinkLabel.POSSIBLE
            else:
                label = LinkLabel.UNKNOWN

            edge = SeamEdge(
                id=f"seam_{fid}_{cid}",
                fiat_transfer_id=fid,
                chain_transfer_id=cid,
                source_entity=cand["fiat"].src_id,
                target_entity=cand["crypto"].dst_id,
                score=round(score, 3),
                label=label,
                delta_t_seconds=cand["delta_t_sec"],
                inr_amount_minor=cand["fiat_inr_minor"],
                usdt_amount_minor=cand["crypto_minor"],
                implied_rate=cand["implied_rate"],
                deviation_pct=cand["deviation_pct"],
                reason=(
                    f"Multi-rail correlation: Fiat debit of {cand['fiat'].amount_formatted} "
                    f"matches crypto credit of {cand['crypto'].amount_formatted} "
                    f"within {cand['delta_t_sec'] // 60}m @ implied rate {cand['implied_rate']}/USDT "
                    f"({cand['deviation_pct']}% market deviation)"
                )
            )
            matches.append(edge)

        return matches
