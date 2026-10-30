# Integration Roadmap for MANTIS

## Overview
This document maps the most valuable capabilities from identified competitor/analogue tools to concrete enhancement opportunities within **MANTIS**. Each entry lists the source system, the feature to be borrowed, the target module in the MANTIS code‑base, any legal or operational constraints, and a priority rating (Impact × Effort).

## Source Systems & Key Features
| # | System / Paper | Core Feature(s) | Why it matters for MANTIS |
|---|----------------|----------------|----------------------------|
| 1 | **Chainalysis Reactor** | On‑chain clustering heuristics (change‑address detection, address‑reuse scoring, multi‑address entity linking) | Improves detection of hidden crypto‑mixing and layered transfers; can be integrated into `intelligence/typologies.py`.
| 2 | **Quantexa Entity Resolution** | Probabilistic graph‑based entity resolution across heterogeneous data sources (bank, telecom, KYC) | Extends `correlation/record_linkage.py` beyond pairwise Fellegi‑Sunter to multi‑node Bayesian networks.
| 3 | **Palantir Foundry Graph ML** | Graph Neural Network (GNN) association scoring for large‑scale money‑trail graphs | Provides a learned alternative to rule‑based seam matching; target module `graph/gnn_associator.py`.
| 4 | **GO.Data (WHO)** | Visual case‑linkage UI with customizable event types and timeline filters | Enhances the web UI (`web/index.html`) with richer timeline navigation and annotation layers.
| 5 | **Snyk SBOM & Dependency Graph** | Software supply‑chain provenance and vulnerability mapping | Can be repurposed for **software‑asset trace** when investigating ransomware‑related fund‑flow (future extension).
| 6 | **TronGrid / Etherscan APIs** | Real‑time on‑chain data ingestion, rate‑limit handling, transaction enrichment | Drives the `ingest` layer for blockchain sources; informs retry/back‑off strategies.
| 7 | **AMLWorld / IBM Synthetic AML Datasets** | Benchmark graphs with known money‑laundering patterns (structuring, layering, integration) | Supplies training/evaluation data for the GNN and typology detectors.
| 8 | **FlowShield (arXiv 2608.17355)** | Flow‑based anomaly detection using attention over transaction sequences | Adds a new detection engine (possible future module `intelligence/flow_anomaly.py`).
| 9 | **AMLGuard / Tracing the Shadows (arXiv 2607.18869)** | Empirical study of 82 real cases, feature taxonomy | Guides the design of rule sets for `typologies.py` and informs evaluation metrics.
|10| **Kuzu Graph DB (archived)** | High‑performance native graph storage + query language | Could replace NetworkX for production‑scale graphs if revived; note deprecation risk.

## Mapping to MANTIS Modules
| Target Module | Feature to Incorporate | Implementation Sketch |
|---------------|------------------------|----------------------|
| `intelligence/typologies.py` | Change‑address detection & address‑reuse scoring (Chainalysis) | Add functions `detect_change_address` and `score_address_reuse` using transaction metadata; expose via new API endpoint `/typology/address_reuse`.
| `correlation/record_linkage.py` | Multi‑source Bayesian entity resolution (Quantexa) | Replace Fellegi‑Sunter with a simple factor graph using `pgmpy`; fallback to existing matcher for low‑confidence cases.
| `graph/gnn_associator.py` *(new)* | GNN‑based edge scoring (Palantir) | Stub class `GNNAssociator` that loads a Torch model (CPU‑only) and provides `score_edge(edge)`; later pipeline will call this after `seam_solver` to re‑rank matches.
| `web/index.html` | Timeline UI, event annotations (GO.Data) | Add a timeline control (e.g., `<input type="range">`) that filters graph edges by timestamp; overlay event tags from typology detectors.
| `ingest/blockchain` (future) | Real‑time on‑chain ingestion (Tron/Etherscan) | Implement adapters `TronGridAdapter` and `EtherscanAdapter` respecting rate limits from research subagent; store raw on‑chain payloads in `BlockDataDB`.
| `intelligence/flow_anomaly.py` (future) | Sequence‑level attention anomaly (FlowShield) | New detector class using PyTorch `nn.TransformerEncoder` over transaction sequences.
| `graph/storage` (future) | High‑performance graph backend (Kuzu) | Abstract graph interface; provide Kuzu implementation as optional plugin.

## Legal & Operational Constraints
| Constraint | Affected Feature | Mitigation |
|-----------|------------------|------------|
| **BSA §63 hash‑manifest** | Bulk GNN scoring (potentially large batch) | After each batch, insert an `AuditLogDB` entry with SHA‑256 of the processed payload (as required by Section 63 BSA). |
| **DPDP Act 2023** (data‑privacy) | Ingestion of personal bank statements | Anonymise PII (account numbers, names) before persisting; store original encrypted blob separate from analysis DB.
| **RBI freeze rules** | Automated freeze requests (gap planner) | Ensure any generated statutory notice is a *draft*; actual freeze must be manually authorised by a compliance officer.
| **API rate limits** (Tron/Etherscan) | Real‑time blockchain ingestion | Implement exponential back‑off and token‑bucket throttling per the limits discovered by the research subagent.
| **Proprietary algorithm licensing** (Chainalysis, Quantexa) | Direct code reuse | Re‑implement similar heuristics from open‑source literature; avoid copying proprietary code.

## Prioritisation Matrix
| Priority | Feature | Impact (1‑5) | Effort (1‑5) | Score (Impact × Effort) |
|----------|---------|--------------|--------------|--------------------------|
| **P1** | GNN association scorer (Palantir) | 5 | 4 | 20 |
| **P2** | Change‑address & reuse heuristics (Chainalysis) | 5 | 2 | 10 |
| **P3** | Multi‑source Bayesian entity resolution (Quantexa) | 4 | 3 | 12 |
| **P4** | Real‑time blockchain adapters (Tron/Etherscan) | 4 | 3 | 12 |
| **P5** | GO.Data‑style timeline UI | 3 | 2 | 6 |
| **P6** | FlowShield‑style anomaly detector | 3 | 4 | 12 |
| **P7** | Kuzu graph backend (optional) | 2 | 5 | 10 |

*We will start with **P1** (GNN associator) because it offers the highest combined impact/effort and creates a flexible foundation for later ML‑driven enhancements.*

---
**Next Steps**
1. Implement the GNN stub (`mantis/graph/gnn_associator.py`).
2. Add unit test under `tests/`.
3. Update `requirements.txt` with `torch` (CPU‑only). 
4. Commit on a new branch `feature/gnn-associator` and push.
5. Continue fleshing out the roadmap items as research results arrive.
