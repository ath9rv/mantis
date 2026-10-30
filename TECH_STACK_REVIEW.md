# MANTIS 2.0 stack review

## Recommendation

Use the pasted stack as a menu, not a shopping list. MANTIS needs dependable evidence, explicit uncertainty, and repeatable analysis before it needs more servers or AI. Keep FastAPI, Pydantic v2, SQLAlchemy, SQLite for local work, PostgreSQL for a shared deployment, and NetworkX for case-sized graphs. Add schema migrations and an evaluation harness before adding live chain providers or splitting the frontend.

## Decision matrix

| Proposal | Decision | Reason / condition |
| --- | --- | --- |
| Next.js 14 + TypeScript | Do not start on v14. | Next.js lists 14.x as unsupported; if MANTIS moves to a separately built frontend, use a currently supported major (16.x is Active LTS as of this review). A framework migration alone does not improve investigation accuracy. [Next.js support policy](https://nextjs.org/support-policy) |
| Tailwind + shadcn/ui | Defer until a frontend split. | The existing local cockpit can use a small design-token system without adding a Node build pipeline. Adopt a component system when multiple routes/forms and accessibility testing justify it. |
| Cytoscape.js + `fcose` | Keep graph visualization; benchmark layouts first. | Compound grouping and spring layouts can help on dense cases, but the current investigation graph is small and time ordered. Add layout extensions only after measuring readability. For very large cases, filter, collapse, and summarize first; WebGL does not solve visual overload. |
| Recharts Sankey + Framer Motion | Defer. | A Sankey can imply value conservation that current traces do not calculate. Add a replay timeline after balances, taint lots, and split/merge semantics are persisted. |
| FastAPI + Uvicorn | Keep. | Fits the current API and serves both local and later hosted deployments. Keep expensive provider queries and PDF rendering out of request handlers. |
| Pydantic v2 | Keep and constrain. | Runtime validation is already in use. Dependencies now specify Pydantic 2 and bounded compatible major versions. Validate transfer identifiers, timestamps, numeric ranges, and enum values at every ingest boundary. |
| PostgreSQL + SQLAlchemy + Alembic | PostgreSQL for multi-user operations; add Alembic before schema changes are deployed. | `create_all` is not a migration system. SQLite remains useful locally, but PostgreSQL deployment needs versioned migrations, backup/restore drills, authorization, and audited upgrade/rollback procedures. |
| NetworkX | Keep for current case graphs and matching. | A graph database adds operational burden without a demonstrated scale need. Define a storage interface only when a second backend or query benchmark requires it. The original Kùzu repository is archived; the attached warning is accurate. [Kùzu archive](https://github.com/kuzudb/kuzu) |
| Splink / Fellegi–Sunter | Pilot only after labels exist. | The current hand-set m/u values are not calibrated. This update removes the false `match_probability` claim and prevents the matcher from confirming identity. Use a labeled comparison set, blocking rules, and precision/recall review before calling the result probabilistic. |
| SciPy Hungarian solver | Keep the current sparse NetworkX objective for now. | MANTIS needs optional unmatched candidates. SciPy's assignment solver is a strong dense assignment tool, but using it here requires dummy assignments and care around non-candidates. The current NetworkX maximum-weight matching represents sparse edges and may leave records unmatched. [SciPy assignment API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html) |
| TronPy + Web3.py | Add behind provider adapters when provider/network requirements are selected. | SDKs do not make historical account data complete. TRON documentation distinguishes solidified reads from latest-head state and points historical account/TRC-20 queries to TronGrid or a self-hosted indexer. A provider adapter must paginate, checkpoint, preserve query and response provenance, handle retries/quotas, and expose the selected network and confirmation state. [TRON API selection](https://developers.tron.network/docs/api) |
| `chain_cache` | Add with live ingestion, not before. | Cache keys need network, address, contract, block range, query parameters, provider, fetched time, and source-response hash. A cache entry is a reproducible provider response, not an independent proof of chain state. |
| Claude API narrator | Do not send case data to an external model by default. | The grounded query helper is deterministic and local. Structured output constrains shape; it does not validate truth. If a model is later approved, give it a minimal set of structured, precomputed claims and require deterministic claim-ID/amount validation. Keep egress opt-in and auditable. |
| WeasyPrint + BSA certificate manifest | Defer court-facing certificates. | A PDF with hashes is not automatically a statutory certificate. Build a source manifest now; generate legal-form documents only from counsel-approved templates, with issuer identity, process metadata, signature workflow, and review. |
| pytest + Hypothesis | Add as development tooling. | Property-based testing can explore edge cases; it does not mathematically prove correctness. Compare money conservation and matching output to simple reference implementations on generated small inputs, then keep labeled end-to-end cases. |
| Docker Compose | Add when deployment is being packaged. | The current local one-process workflow is simple. A production compose profile should separate API, database, evidence volume, migrations, secrets, and health checks; it must not bake real evidence or API keys into images. |
| Redis/Celery | Defer. | A durable job table plus a recoverable worker is sufficient for the first import/report jobs. FastAPI `BackgroundTasks` alone is not durable across process crashes. Add a queue only when measured concurrency and retry needs justify it. |

## Changes made from this review

- Linkage now returns an uncalibrated review weight and itemized signals; it never marks a record pair as confirmed. The “name Jaro–Winkler” comparison was renamed to the actual token Jaccard method.
- Fiat/crypto seam matching now uses exact decimal arithmetic for amount ratios and checks only candidates inside the configured timestamp window. The former “reputation” bonus was removed; a score boost is possible only for an explicit shared `cross_rail_reference` field.
- Seam configuration rejects non-finite/negative weights, weights that do not sum to one, and invalid windows/tolerances.
- Python dependencies now declare supported major-version ranges instead of resolving without bounds.

## Production sequence

1. Add Alembic migrations and exact integer storage that supports full-width chain token units. The current ORM monetary columns are SQL `Integer`; this is too narrow for PostgreSQL's 32-bit `INTEGER` and for raw ERC-20 units.
2. Add individual identity, case-level authorization, and a tamper-evident audit sink anchored outside the operational database.
3. Build provider adapters for selected chain/data vendors, recording network, block number/hash, log index, confirmation/finality state, fetch time, provider, and raw response hash.
4. Create a reviewed and labeled linkage/seam benchmark; measure false positives, false negatives, calibration, and run time before changing weights or introducing Splink/SciPy/OR-Tools.
5. Specify asset-aware lots and conservation rules before displaying taint propagation, recoverable amounts, Sankey totals, or legal recovery recommendations.
6. Migrate the UI to a supported Next.js release only when product needs justify independent frontend deployment. Do not treat SSR as a security boundary; the API still needs case authorization.

The code remains a local evidence review tool until those deployment controls and independent validation are complete. Real uploaded data is supported, but live banking feeds, direct chain-provider calls, and organization accounts are not configured.
