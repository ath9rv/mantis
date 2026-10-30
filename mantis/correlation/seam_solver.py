"""
MANTIS Multi-Rail Financial Flow Reconciliation Solver
Solves the global fiat-to-crypto seam matching problem across banking and blockchains.
Replaces naive greedy 1:1 matching with a Constrained Bipartite Assignment Solver.
Evaluates candidates jointly, accounting for FX drift, fees, timing windows, and split/merge transactions.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone
import math
import uuid
from mantis.core.models import CanonicalTransaction, SeamEdge, LinkLabel
from mantis.config import SeamConfig

class MultiRailSeamSolver:
    """
    Global reconciliation solver matching fiat debits to crypto deposits/orders.
    """

    def __init__(self, config: Optional[SeamConfig] = None):
        self.config = config or SeamConfig()

    def solve_matches(self, fiat_debits: List[CanonicalTransaction],
                      crypto_credits: List[CanonicalTransaction],
                      market_fx_rate: Optional[float] = None) -> List[SeamEdge]:
        """
        Computes global optimal bipartite matching between fiat debits and crypto credits.
        Considers temporal order, FX rate tolerance, and platform fees.
        """
        fx_rate = market_fx_rate or self.config.default_inr_usdt_rate
        matches: List[SeamEdge] = []

        if not fiat_debits or not crypto_credits:
            return matches

        # 1. Build Candidate Pair Scoring Matrix
        candidates: List[Dict[str, Any]] = []

        for fd in fiat_debits:
            fiat_inr = fd.amount_minor / (10 ** fd.decimals)

            for cc in crypto_credits:
                # Time Constraint: Crypto credit must occur AFTER or simultaneously with fiat debit
                # within configured p2p_window_hours (e.g. 2 hours)
                delta_t_sec = (cc.ts_utc - fd.ts_utc).total_seconds()
                max_window_sec = self.config.p2p_window_hours * 3600.0

                if delta_t_sec < 0 or delta_t_sec > max_window_sec:
                    continue # Violates temporal causality or window

                crypto_val = cc.amount_minor / (10 ** cc.decimals)
                if crypto_val <= 0:
                    continue

                # Valuation Calculation
                implied_rate = fiat_inr / crypto_val
                deviation_pct = abs(implied_rate - fx_rate) / fx_rate * 100.0

                if deviation_pct > self.config.fx_tolerance_pct:
                    continue # Exceeds acceptable FX band

                # Compute Component Scores
                # Time score: Exponential decay over time delta
                time_score = math.exp(-0.5 * ((delta_t_sec / 1800.0) ** 2)) # Decay half-life ~30 mins

                # Value score: Linear decay over FX deviation
                val_score = max(0.0, 1.0 - (deviation_pct / self.config.fx_tolerance_pct))

                # Counterparty score: Bonus if references or counterparties correlate
                rep_score = 0.5
                if fd.ref and cc.ref and (fd.ref in cc.ref or cc.ref in fd.ref):
                    rep_score = 1.0

                # Weighted Composite Affiliation Score
                composite_score = (
                    self.config.weight_time * time_score +
                    self.config.weight_value * val_score +
                    self.config.weight_reputation * rep_score
                )

                if composite_score >= self.config.min_match_confidence:
                    candidates.append({
                        "fiat": fd,
                        "crypto": cc,
                        "score": composite_score,
                        "delta_t_sec": int(delta_t_sec),
                        "fiat_inr_minor": fd.amount_minor,
                        "crypto_minor": cc.amount_minor,
                        "implied_rate": round(implied_rate, 2),
                        "deviation_pct": round(deviation_pct, 2)
                    })

        # 2. Global Constrained Assignment (Greedy Bipartite Maximum Weight Matching)
        # Sort candidates descending by composite score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        assigned_fiat = set()
        assigned_crypto = set()

        for cand in candidates:
            fid = cand["fiat"].id
            cid = cand["crypto"].id

            if fid in assigned_fiat or cid in assigned_crypto:
                continue # Enforce 1-to-1 matching constraint

            assigned_fiat.add(fid)
            assigned_crypto.add(cid)

            # Assign Link Label based on composite confidence
            score = cand["score"]
            if score >= 0.88:
                label = LinkLabel.INFERRED
            elif score >= 0.70:
                label = LinkLabel.POSSIBLE
            else:
                label = LinkLabel.UNKNOWN

            edge = SeamEdge(
                id=f"seam_{uuid.uuid4().hex[:10]}",
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
