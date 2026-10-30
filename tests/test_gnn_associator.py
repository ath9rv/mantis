# tests/test_gnn_associator.py
"""Tests for safe unavailable behavior before a trained model is configured."""

import datetime

from mantis.graph.gnn_associator import GNNAssociator


def test_gnn_associator_does_not_invent_a_fallback_score(monkeypatch):
    # Create a dummy edge with minimal required fields.
    edge = {
        "ref": "tx_dummy",
        "amount_minor": 50000,
        "rail": "CRYPTO",
        "ts_utc": datetime.datetime(2024, 1, 1, 0, 0, tzinfo=datetime.timezone.utc),
    }
    assoc = GNNAssociator()  # No model path → scoring is unavailable.
    monkeypatch.setattr(assoc, "_audit", lambda payload: None)
    score = assoc.score_edge(edge)
    assert score is None


def test_gnn_associator_batch_unavailable_and_invalid_features(monkeypatch):
    assoc = GNNAssociator()
    monkeypatch.setattr(assoc, "_audit", lambda payload: None)
    scores = assoc.score_batch([{"ref": "valid", "amount_minor": 5}, {"ref": "bad", "amount_minor": "bad"}])
    assert scores == [None, None]
