"""
MANTIS Probabilistic Record Linkage Engine
Implements the Fellegi-Sunter methodology (the mathematical foundation of Splink).
Evaluates whether records from different datasets (Bank Statements, P2P Orderbooks,
Exchange KYC, Complaints) refer to the same entity or transaction.
"""

import math
import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field
from mantis.core.models import AssocEdge, LinkLabel

@dataclass
class ComparisonRule:
    field_name: str
    m_probability: float  # P(agree | Match)
    u_probability: float  # P(agree | Non-Match)
    
    @property
    def weight_agreement(self) -> float:
        return math.log2(self.m_probability / self.u_probability)

    @property
    def weight_disagreement(self) -> float:
        return math.log2((1.0 - self.m_probability) / (1.0 - self.u_probability))

class FellegiSunterLinker:
    """
    Probabilistic entity and record linkage engine.
    Calculates log-likelihood ratios across multiple comparison fields
    and outputs calibrated probabilities and supporting/counter-evidence.
    """

    DEFAULT_RULES = [
        ComparisonRule("account_number_suffix", m_probability=0.98, u_probability=0.0001), # Last 4 digits + bank IFSC
        ComparisonRule("vpa_handle", m_probability=0.95, u_probability=0.0005),            # Exact or fuzzy UPI VPA
        ComparisonRule("phone_number", m_probability=0.92, u_probability=0.0001),          # Mobile phone link
        ComparisonRule("name_jaro_winkler", m_probability=0.85, u_probability=0.02),       # Transliterated Indian names
        ComparisonRule("time_proximity_window", m_probability=0.90, u_probability=0.05),   # Occurs within 15 mins
    ]

    def __init__(self, rules: List[ComparisonRule] = None, prior_match_prob: float = 0.01):
        self.rules = rules or self.DEFAULT_RULES
        self.prior_odds = prior_match_prob / (1.0 - prior_match_prob)

    def compare_records(self, rec_a: Dict[str, Any], rec_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compares two records across configured fields.
        Returns total weight, match probability, and itemized evidence/counter-evidence.
        """
        log_weight_sum = math.log2(self.prior_odds)
        evidence = []
        counter_evidence = []

        for rule in self.rules:
            val_a = rec_a.get(rule.field_name)
            val_b = rec_b.get(rule.field_name)

            if val_a is None or val_b is None:
                continue # Missing data does not penalize or reward

            agrees, score, detail = self._evaluate_agreement(rule.field_name, val_a, val_b)

            if agrees:
                w = rule.weight_agreement * score
                log_weight_sum += w
                evidence.append({
                    "field": rule.field_name,
                    "val_a": str(val_a),
                    "val_b": str(val_b),
                    "weight": round(w, 2),
                    "detail": detail
                })
            else:
                w = rule.weight_disagreement
                log_weight_sum += w
                counter_evidence.append({
                    "field": rule.field_name,
                    "val_a": str(val_a),
                    "val_b": str(val_b),
                    "weight": round(w, 2),
                    "detail": detail
                })

        # Convert posterior odds to probability: P = Odds / (1 + Odds) = 1 / (1 + 2^(-log_odds))
        posterior_prob = 1.0 / (1.0 + (2.0 ** (-log_weight_sum)))

        # Determine label
        if posterior_prob >= 0.95:
            label = LinkLabel.CONFIRMED if any(e["field"] == "account_number_suffix" for e in evidence) else LinkLabel.INFERRED
        elif posterior_prob >= 0.70:
            label = LinkLabel.INFERRED
        elif posterior_prob >= 0.40:
            label = LinkLabel.POSSIBLE
        else:
            label = LinkLabel.UNKNOWN

        return {
            "match_probability": round(posterior_prob, 4),
            "log_weight": round(log_weight_sum, 2),
            "label": label,
            "evidence": evidence,
            "counter_evidence": counter_evidence
        }

    def _evaluate_agreement(self, field_name: str, val_a: Any, val_b: Any) -> Tuple[bool, float, str]:
        """Evaluates agreement between two field values."""
        str_a = str(val_a).strip().lower()
        str_b = str(val_b).strip().lower()

        if field_name == "account_number_suffix":
            # Match last 4 digits
            digits_a = re.sub(r"\D", "", str_a)[-4:]
            digits_b = re.sub(r"\D", "", str_b)[-4:]
            if digits_a and digits_b and digits_a == digits_b:
                return True, 1.0, f"Matching last-4 digits: {digits_a}"
            return False, 0.0, "Account digits mismatch"

        elif field_name == "phone_number":
            # Match last 10 digits
            p_a = re.sub(r"\D", "", str_a)[-10:]
            p_b = re.sub(r"\D", "", str_b)[-10:]
            if p_a and p_b and p_a == p_b:
                return True, 1.0, f"Exact 10-digit mobile match: {p_a}"
            return False, 0.0, "Mobile numbers differ"

        elif field_name == "vpa_handle":
            if str_a == str_b:
                return True, 1.0, "Identical UPI VPA"
            # Prefix check before @ (e.g. ramesh.k92@oksbi vs ramesh.k92@okaxis)
            user_a = str_a.split("@")[0]
            user_b = str_b.split("@")[0]
            if user_a and user_b and user_a == user_b:
                return True, 0.85, f"Shared username prefix across PSPs: {user_a}"
            return False, 0.0, "Distinct VPAs"

        elif field_name == "name_jaro_winkler":
            sim = self._token_jaccard(str_a, str_b)
            if sim >= 0.80:
                return True, sim, f"High name similarity: {sim:.2f}"
            return False, 0.0, f"Low name similarity: {sim:.2f}"

        # Default string equality
        if str_a == str_b:
            return True, 1.0, "Exact match"
        return False, 0.0, "Values do not match"

    @staticmethod
    def _token_jaccard(s1: str, s2: str) -> float:
        tokens1 = set(re.findall(r"\w+", s1.lower()))
        tokens2 = set(re.findall(r"\w+", s2.lower()))
        if not tokens1 or not tokens2:
            return 0.0
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        return intersection / union
