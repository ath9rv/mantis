# mantis/graph/gnn_associator.py
"""GNN Association Scorer (stub)

This module provides a placeholder implementation for a Graph Neural Network‑based
association scorer that will later replace or augment the rule‑based seam‑matching
logic. The class is deliberately lightweight – it loads a Torch model (CPU‑only)
if one is available and falls back to a deterministic score of ``0.5`` for every
edge. This allows the rest of the pipeline to be exercised while the actual
trained model is being developed.

The public API mirrors the existing ``seam_solver`` workflow:

```python
from mantis.graph.gnn_associator import GNNAssociator

gnn = GNNAssociator(model_path="models/gnn_associator.pt")
score = gnn.score_edge(edge)  # returns float in [0, 1]
```

The stub records an audit‑log entry (via ``mantis.db.models.AuditLogDB``) for
batch scoring to satisfy BSA §63 hash‑manifest requirements.
"""

from __future__ import annotations

import pathlib
import hashlib
import json
import logging
from typing import Any

try:
    import torch
    _TORCH_AVAILABLE = True
except Exception:  # pragma: no cover – torch may not be installed yet
    _TORCH_AVAILABLE = False
    torch = None  # type: ignore

from mantis.db import session as db_session
from mantis.db.models import AuditLogDB

logger = logging.getLogger(__name__)


class GNNAssociator:
    """Stub class for a GNN based edge‑association scorer.

    Parameters
    ----------
    model_path: str | pathlib.Path, optional
        Path to a serialized ``torch`` model. If the file does not exist or
        ``torch`` is unavailable, the associator operates in *fallback* mode,
        returning a constant score of ``0.5``.
    """

    def __init__(self, model_path: str | pathlib.Path | None = None):
        self.model_path = pathlib.Path(model_path) if model_path else None
        self.model: Any | None = None
        if _TORCH_AVAILABLE and self.model_path and self.model_path.is_file():
            try:
                self.model = torch.load(self.model_path, map_location="cpu")
                self.model.eval()
                logger.info("Loaded GNN model from %s", self.model_path)
            except Exception as exc:  # pragma: no cover – loading errors are rare
                logger.warning("Failed to load GNN model (%s); using fallback", exc)
                self.model = None
        else:
            logger.info("Torch not available or model path missing – using fallback scorer")

    def _hash_manifest(self, payload: dict) -> str:
        """Create a SHA‑256 hash of the JSON payload.

        This method is used to generate the *hash‑manifest* required by
        BSA §63 for any bulk processing step.
        """
        json_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(json_bytes).hexdigest()

    def _audit(self, payload: dict) -> None:
        """Write an audit‑log entry for the given payload.

        The audit log table stores ``timestamp``, ``operation`` and the computed
        ``hash_manifest``. A new DB session is opened for the insert and closed
        immediately to keep the call lightweight.
        """
        hash_val = self._hash_manifest(payload)
        with db_session.get_db() as db:  # type: ignore[arg-type]
            audit = AuditLogDB(
                operation="gnn_association_batch",
                payload_json=json.dumps(payload),
                hash_manifest=hash_val,
            )
            db.add(audit)
            db.commit()
        logger.debug("Audit log entry created with hash %s", hash_val)

    def score_edge(self, edge: Any) -> float:
        """Return an association score for a single graph edge.

        In the stub implementation the ``edge`` argument is expected to be a
        ``networkx`` edge data dictionary containing the keys ``"amount_minor"``,
        ``"rail"`` and ``"ts_utc"``. The method extracts a minimal feature vector
        and either runs it through the loaded Torch model or returns the fallback
        value ``0.5``.

        Returns
        -------
        float
            Score in the range ``[0.0, 1.0]`` where higher values indicate a
            stronger likelihood that the two transactions belong to the same
            laundering chain.
        """
        # Minimal feature extraction – can be expanded later.
        try:
            amount = float(edge.get("amount_minor", 0))
            # Encode rail as an integer (e.g., 0=FIAT, 1=CRYPTO). Adjust if needed.
            rail = 1 if edge.get("rail") == "CRYPTO" else 0
            timestamp = edge.get("ts_utc").timestamp() if edge.get("ts_utc") else 0.0
        except Exception as exc:  # pragma: no cover – defensive programming
            logger.warning("Edge feature extraction failed (%s); using fallback", exc)
            return 0.5

        if self.model is not None:
            # Convert features to a Torch tensor of shape (1, 3).
            tensor = torch.tensor([[amount, rail, timestamp]], dtype=torch.float32)
            with torch.no_grad():
                raw = self.model(tensor)
                # Assume the model outputs a single logit; apply sigmoid.
                prob = torch.sigmoid(raw).item()
                # Clamp to [0, 1] for safety.
                return max(0.0, min(1.0, prob))
        else:
            # Fallback deterministic score – still audit the request for compliance.
            payload = {"edge_id": edge.get("ref"), "features": {"amount": amount, "rail": rail, "ts": timestamp}}
            self._audit(payload)
            return 0.5

    def score_batch(self, edges: list[Any]) -> list[float]:
        """Score a list of edges in a single batch.

        The batch version records a single audit‑log entry containing the whole
        payload, satisfying the hash‑manifest requirement for bulk operations.
        """
        scores: list[float] = []
        if self.model is not None:
            # Vectorised scoring – build a tensor of shape (N, 3).
            feats = []
            ids = []
            for e in edges:
                try:
                    amount = float(e.get("amount_minor", 0))
                    rail = 1 if e.get("rail") == "CRYPTO" else 0
                    ts = e.get("ts_utc").timestamp() if e.get("ts_utc") else 0.0
                except Exception:  # pragma: no cover
                    amount, rail, ts = 0.0, 0, 0.0
                feats.append([amount, rail, ts])
                ids.append(e.get("ref"))
            tensor = torch.tensor(feats, dtype=torch.float32)
            with torch.no_grad():
                raw = self.model(tensor)
                probs = torch.sigmoid(raw).cpu().numpy().tolist()
                scores = [float(max(0.0, min(1.0, p))) for p in probs]
        else:
            # All fallback scores.
            scores = [0.5 for _ in edges]
        # Audit the whole batch.
        payload = {"batch_size": len(edges), "edge_refs": ids, "fallback": self.model is None}
        self._audit(payload)
        return scores

# The module can be exercised via a simple __main__ guard for manual testing.
if __name__ == "__main__":  # pragma: no cover
    dummy_edge = {"ref": "tx123", "amount_minor": 100000, "rail": "CRYPTO", "ts_utc": None}
    assoc = GNNAssociator()
    print("Score for dummy edge:", assoc.score_edge(dummy_edge))
