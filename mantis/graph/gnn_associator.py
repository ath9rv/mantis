"""Optional GNN association scorer.

This integration point intentionally returns ``None`` until a trained model is
configured. A neutral-looking numeric score would mislead downstream reviewers.
Model outputs are raw, uncalibrated rankings and must not be treated as
probabilities or as evidence of criminal activity.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import pathlib
from datetime import datetime, timezone
from typing import Any

try:
    import torch
except ImportError:  # The core application does not require the ML extra.
    torch = None  # type: ignore[assignment]

from mantis.db.models import AuditLogDB
from mantis.db.session import SessionLocal

logger = logging.getLogger(__name__)


class GNNAssociator:
    """Load an optional model; return no score when no usable model exists."""

    def __init__(self, model_path: str | pathlib.Path | None = None):
        self.model_path = pathlib.Path(model_path) if model_path else None
        self.model: Any | None = None
        if torch is None or self.model_path is None or not self.model_path.is_file():
            logger.info("GNN scoring unavailable: Torch or a configured model is missing")
            return
        try:
            # Require an exported TorchScript artifact; do not unpickle arbitrary objects.
            self.model = torch.jit.load(str(self.model_path), map_location="cpu")
            if not callable(self.model):
                raise TypeError("model artifact must load as a callable module")
            self.model.eval()
            logger.info("Loaded GNN model from %s", self.model_path)
        except Exception as exc:
            logger.warning("GNN model unavailable (%s)", exc)
            self.model = None

    @staticmethod
    def _canonical_hash(event: dict[str, Any]) -> str:
        body = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _audit(self, payload: dict[str, Any]) -> None:
        """Append a hash-linked system audit event using the application's format."""
        with SessionLocal() as db:
            previous = (
                db.query(AuditLogDB)
                .filter(AuditLogDB.case_id == "system")
                .order_by(AuditLogDB.seq.desc())
                .first()
            )
            prev_hash = previous.this_hash if previous else "0" * 64
            at = datetime.now(timezone.utc)
            event = {
                "case_id": "system", "actor": "gnn_associator",
                "action": "gnn_association_batch", "payload": payload,
                "prev_hash": prev_hash, "at": at.isoformat(),
            }
            db.add(AuditLogDB(
                case_id="system", actor="gnn_associator",
                action="gnn_association_batch",
                payload_json=json.dumps(payload, sort_keys=True, ensure_ascii=False),
                prev_hash=prev_hash, this_hash=self._canonical_hash(event), at=at,
            ))
            db.commit()

    @staticmethod
    def _features(edge: Any) -> list[float] | None:
        """Extract the current placeholder feature vector; reject invalid values."""
        try:
            amount = float(edge.get("amount_minor", 0))
            rail = 1.0 if edge.get("rail") == "CRYPTO" else 0.0
            ts_value = edge.get("ts_utc")
            timestamp = ts_value.timestamp() if ts_value else 0.0
            if not math.isfinite(amount) or not math.isfinite(timestamp):
                return None
            return [amount, rail, timestamp]
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None

    def score_edge(self, edge: Any) -> float | None:
        """Return an uncalibrated model score, or ``None`` if scoring is unavailable."""
        scores = self.score_batch([edge])
        return scores[0]

    def score_batch(self, edges: list[Any]) -> list[float | None]:
        """Score a batch, preserving unavailable/invalid entries as ``None``."""
        refs = [edge.get("ref") if hasattr(edge, "get") else None for edge in edges]
        features = [self._features(edge) for edge in edges]
        scores: list[float | None] = [None] * len(edges)

        if torch is not None and self.model is not None:
            valid_indices = [i for i, feature in enumerate(features) if feature is not None]
            if valid_indices:
                try:
                    tensor = torch.tensor([features[i] for i in valid_indices], dtype=torch.float32)
                    with torch.no_grad():
                        raw = self.model(tensor)
                        values = raw.reshape(-1).tolist()
                    if len(values) != len(valid_indices):
                        raise ValueError("model output count does not match batch size")
                    for index, value in zip(valid_indices, values):
                        value = float(value)
                        if value == value and abs(value) != float("inf"):
                            scores[index] = value
                except Exception as exc:
                    logger.warning("GNN batch scoring failed (%s); scores unavailable", exc)

        self._audit({
            "batch_size": len(edges), "edge_refs": refs,
            "scored_count": sum(score is not None for score in scores),
            "scores": scores,
            "model_available": self.model is not None and torch is not None,
            "score_semantics": "uncalibrated_model_output_or_unavailable",
        })
        return scores
