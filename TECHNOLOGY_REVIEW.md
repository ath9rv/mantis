# MANTIS Technology and Algorithm Review

## Recommendation

Keep the current Python/FastAPI/SQLAlchemy/NetworkX foundation for the local case workspace. Do not add a graph database, streaming platform, vector database, or LLM-based detector yet. The strongest improvements still come from defensible evidence handling, correct flow models, and measured false positives.

## What the code does today

| Area | Current implementation | Practical assessment |
|---|---|---|
| Ingestion | CSV bank-statement adapter and frozen TRON JSON export adapter; content-addressed original files; source row context | Usable with investigator-supplied exports, but institution formats need validated parser profiles. No live bank or blockchain provider is connected. |
| Entity linkage | Hand-written Fellegi–Sunter-like weights | Not yet a trained/calibrated Fellegi–Sunter model. The default probabilities are assumptions; the `name_jaro_winkler` comparison is token Jaccard, and the time comparison currently falls back to exact equality. A last-four account match can label a result confirmed. |
| Fiat/crypto seam | Time/value scoring followed by NetworkX maximum-weight one-to-one matching | The solver is exact for its one-to-one objective, but its score is heuristic and it cannot represent split/merged payments. A rate is now investigator-supplied; without one, cross-asset candidates are not generated. |
| Tracing and taint | Time-ordered graph walk plus poison, haircut, and FIFO dictionaries | The graph walk is useful for candidate discovery, but it does not prove that a particular amount propagated. The FIFO and poison paths currently use the same transfer rule; haircut depends on externally supplied balances that the API does not persist. |
| Typologies | Hand-tuned pass-through, near-threshold, and peel-chain rules | Useful as explainable indicators, but hard-coded scores are not probabilities. A single transfer near a threshold is not enough to establish structuring; benign lookalikes need measured false-positive rates. |
| Persistence | SQLite by default, configurable PostgreSQL, content-addressed evidence files, indexes, saved trace runs | Fits a single-user local workflow. There is no migration history or case-level authorization. The per-case audit hash chain detects internal edits but is not externally anchored or signed. |
| Copilot | Deterministic query routing over the selected case records, surfaced in the UI | Keep deterministic. It is a query helper, not an AI analyst; answers may be incomplete and include cited record IDs. |

## Prioritized changes

### P0 — Make outputs defensible

1. **Build a labeled evaluation pack before tuning models.** Add synthetic positive, negative, and ambiguous cases for repeated references, shared accounts, missing data, split payments, benign payroll/merchant flows, and multi-asset transfers. Store expected links, expected flow allocations, and reasons. Report link precision/recall, false-positive rate, seam candidate precision, calibration, and runtime per case. Keep a frozen replay pack so results do not depend on a live blockchain API.
2. **Complete evidence provenance.** Original upload bytes, SHA-256, parser, raw CSV row, source row number, and import/analysis activity are now retained. Add parser versions, normalized field-level warnings, and supporting/counter-evidence IDs for each later claim. A hash alone does not establish a complete chain of custody; anchor event hashes outside the mutable database and sign them before operational use.
3. **Correct taint semantics before exposing recovery estimates.** Model balances as asset-specific lots with timestamps and source evidence. Implement FIFO as actual consumption of ordered lots; implement haircut as proportional allocation from a defined balance snapshot; define poison separately. Record assumptions and compare outcomes. Do not emit a “recoverable” amount if a required balance or allocation is unknown.
4. **Separate a score from a probability.** The UI now calls rule outputs heuristic scores and candidate seams rather than calibrated confidence. Keep them that way until evaluation on labeled held-out cases supports a probability claim. Add explicit investigator states such as `supported`, `rejected`, and `unknown`, with reasons and reviewer identity.

### P1 — Improve matching quality

5. **Replace the generic hand-weighted linker with Splink when multiple statement/customer datasets need linking.** Keep exact matches for authoritative identifiers, then use a configured Fellegi–Sunter model with comparison levels, blocking, term-frequency adjustments, and a comparison review process. Splink exposes these controls and supports DuckDB locally or larger backends; it remains an implementation, not a substitute for labeled validation. [Splink overview](https://moj-analytical-services.github.io/splink/), [comparison levels](https://moj-analytical-services.github.io/splink/api_docs/comparison_level_library.html)
6. **Keep NetworkX for current case-sized one-to-one seam matching.** It already computes maximum-weight matchings; its documented algorithm is cubic in graph node count, which is acceptable until measured candidate graphs become large. Move to OR-Tools only when the model needs split/merge flows, capacity constraints, fee variables, or other integer constraints. OR-Tools offers assignment, min-cost-flow, MIP, and CP-SAT tools for those broader formulations. [NetworkX matching](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.matching.max_weight_matching.html), [OR-Tools assignment](https://developers.google.com/optimization/assignment)
7. **Use observed FX data, not the fixed default.** Store the rate, source, timestamp, spread/fee assumptions, and conversion calculation with each seam candidate. If no rate evidence is available, emit a wider/unknown value signal rather than implying a market-rate match.

### P2 — Make the data layer safer and faster

8. **Use PostgreSQL plus Alembic for shared or operational deployments; retain SQLite for local use.** Basic query indexes, transaction pagination, and batch entity writes are in place. Add migrations, uniqueness/foreign-key constraints, asset-aware query indexes, backup/restore procedures, and load benchmarks before shared use. [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
9. **Add case-scoped authentication/authorization before exposing the API beyond localhost.** A shared bearer key can protect API routes from casual access but is not user identity or case authorization. Prefer an organization’s OIDC provider and explicit case roles. [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/)
10. **Add property-based and differential tests.** Use Hypothesis for amount parsing, reconciliation invariants, time monotonicity, conservation, and random small matching graphs. Compare optimized results against a simple brute-force oracle for small cases. Hypothesis is designed to generate edge cases and shrink failing inputs. [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/)

## Keep / defer / avoid

| Decision | Recommendation | Why |
|---|---|---|
| Python, FastAPI, SQLAlchemy | Keep | Fits the current code and lets the team focus on evidence semantics. |
| NetworkX | Keep for now | Good for explainable, case-sized graphs and current matching. Benchmark before replacing it. |
| PostgreSQL | Add when multiple users/cases need a shared deployment | Better operational database foundation; pair with Alembic and authorization. |
| Splink | Pilot after labeling a linkage benchmark | Directly addresses the current hand-set linkage assumptions. Review its output rather than treating it as truth. |
| OR-Tools | Defer until split/merge and capacity-constrained seam requirements are specified | More powerful solvers do not fix missing transaction/counterparty evidence. |
| Graph database | Defer | Current scale and product need do not justify operating another database. Add a storage interface first if benchmarks show PostgreSQL/NetworkX are insufficient. |
| LLM, embeddings, vector database | Avoid for core detection and amount calculation | They cannot repair missing evidence or uncalibrated rules. If later used to draft summaries, constrain them to structured claims and validate every ID and amount deterministically. |
| Kafka, Spark, microservices, GPUs | Avoid for this stage | No measured throughput requirement warrants the added deployment and debugging burden. |

## Suggested implementation order

1. Freeze and label a small evaluation corpus; expose current false positives and algorithm outputs in a report.
2. Correct evidence schema and asset-specific flow allocation; block recovery output until inputs are verified.
3. Calibrate linkage and seam scoring against the corpus; pilot Splink on entity linkage.
4. Add migrations, authorization, provenance/audit behavior, and API-level tests before any shared deployment.
5. Benchmark realistic case sizes; only then decide on OR-Tools, a graph database, or background workers.
