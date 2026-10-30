# tests/test_gnn_associator.py
"""Tests for the GNNAssociator stub.

The stub returns a deterministic fallback score of 0.5 when no model is loaded.
We verify that the class can be instantiated and that ``score_edge`` returns the
expected value for a minimal edge dictionary.
"""

import datetime

from mantis.graph.gnn_associator import GNNAssociator


def test_gnn_associator_fallback_score():
    # Create a dummy edge with minimal required fields.
    edge = {
        "ref": "tx_dummy",
        "amount_minor": 50000,
        "rail": "CRYPTO",
        "ts_utc": datetime.datetime(2024, 1, 1, 0, 0, tzinfo=datetime.timezone.utc),
    }
    assoc = GNNAssociator()  # No model path → fallback mode.
    score = assoc.score_edge(edge)
    assert isinstance(score, float)
    assert score == 0.5
