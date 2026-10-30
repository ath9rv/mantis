# MANTIS: Three-person execution plan

## Mission and intended result

MANTIS should help an investigator move from supplied source files to a reviewable, reproducible set of leads without turning uncertainty into fact. It should make it easy to answer:

1. **What did the source actually say?** Preserve original bytes, source row/event, parser version, normalized values, and warnings.
2. **What did the software infer?** Keep candidates and heuristic indicators separate from observed records; show the evidence, counter-evidence, assumptions, and model/config version.
3. **What changes the conclusion?** Show uncertainty, alternative explanations, missing data, and the effect of accepting or rejecting a candidate relationship.
4. **What can an investigator safely do next?** Provide bounded search, evidence review, and draft requests with human authorization; never claim guilt, legal authority, source authenticity, or recoverable balance.
5. **Can another reviewer reproduce the result?** Retain the input snapshot and analysis manifest, preserve review history, and compare outputs against known cases.

### Definition of success

- Every imported fact points to a retained source file and row/event; ambiguous parsing is visible instead of silently normalized.
- Every analytic lead cites its supporting records and assumptions and has an explicit review state such as `unreviewed`, `supported`, `rejected`, or `unknown`.
- Money remains exact in integer minor units. Flow allocation never claims conservation unless the required balance and transfer data support it.
- Scores are called probabilities only after calibration on held-out, representative labels. Otherwise they remain rankings/heuristics.
- The core workflow is usable without AI or live provider connections: create case → import → inspect → trace → review → save/export.
- A fresh installation, migration, backup, and restore can be performed from written steps and verified on a throwaway database.

## What already exists

Current foundations include a local FastAPI app, SQLAlchemy persistence, SQLite default, PostgreSQL configuration, a CSV bank-statement parser, TRON JSON import, content-addressed evidence storage, statement arithmetic reconciliation, entity review, same-asset time-ordered graph tracing, one-to-one fiat/USDT candidate matching, heuristic typology indicators, saved trace runs, a hash-linked activity log, a deterministic record-query helper, and a browser cockpit.

Recent work has added FX source/time provenance, a trace analysis manifest, 64-bit minor-unit columns plus Alembic migration support, corrected name/time linkage comparisons, clearer score semantics, and a verified synthetic judge-demo upload pack. The optional GNN currently returns “unavailable” until a suitable trained model and evaluated feature pipeline exist. There are no live bank feeds or live blockchain-provider integrations.

### Important gaps to plan around

- There is not yet a representative, labeled evaluation corpus. Synthetic examples verify mechanics, not real-world accuracy.
- Trace reachability is a lead-discovery graph walk, not account-balance accounting. FIFO/haircut/poison calculations must not be presented as recovery value until their semantics and inputs are proven.
- Parser behavior still needs institution profiles, field-level warnings, robust duplicate handling, and realistic malformed-input coverage.
- A shared API key is not user identity, case-level authorization, or a production deployment security model.
- Migration support now exists; backup/restore drills, concurrency behavior, and operational deployment documentation still need verification.
- The UI needs tested investigator workflows, accessible text/controls, readable dense data, and trustworthy review states across real case sizes.

## Team split and integration boundaries

| Person | Owns | Primary files | Must not independently change |
|---|---|---|---|
| **1 — Data, evidence, and platform** | Storage schema, migrations, ingest, provenance, API reliability, security, operations | `mantis/db/`, `mantis/ingest/`, backend API contracts, `alembic/`, operations docs | Analytics meanings/thresholds; frontend layout |
| **2 — Analytics and validation** | Linkage, tracing, seam logic, typologies, evaluation corpus and metrics | `mantis/correlation/`, `mantis/graph/`, `mantis/intelligence/`, `mantis/recovery/`, `evals/` | Schema migrations; frontend; changes to factual labels without recorded rationale |
| **3 — Product, UX, and release** | Investigator workflows, UI, accessibility, demo/release experience | `mantis/web/`, user docs, launcher/docs, browser workflow | Algorithm scoring or database schema; invented output claims |

Each person should use a separate branch/worktree. Work in order **within** each person’s seven prompts. Before parallel implementation, Person 1 publishes the API/data contract and Person 2 publishes the evidence/score contract; Person 3 may prototype against existing endpoints and document any required API additions rather than inventing them.

## Shared rules for every prompt

Paste this instruction before any individual prompt:

> You are working in `D:\Mantis`. First read `README.md`, `TECHNOLOGY_REVIEW.md`, the relevant code, and `AGENTS.md` if present. Inspect the current branch/status and preserve unrelated edits. Work only in your assigned ownership area. Make small, reviewable changes; do not copy proprietary implementation details from other products. Do not add external services, AI/LLM calls, data egress, real personal data, hidden network enrichment, or new infrastructure without a written need. Keep observations, inferences, and analyst decisions distinct. Never present a heuristic score as a probability or a lead as proof. Write or update focused tests for changes, run the documented checks, and report commands/results, limitations, migration/rollback implications, and changed files. Do not commit, push, publish, or deploy unless explicitly assigned.

---

# Person 1 — Data, evidence, and platform reliability

**Outcome:** MANTIS accepts investigator-supplied records without silent loss, stores full-width exact amounts, preserves provenance, and can be upgraded/restored safely. Backend contracts are stable enough for the other two people to build against.

### Prompt 1.1 — Map the data contract and schema invariants

> Audit all persisted entities and API schemas in `mantis/db/`, `mantis/core/`, `mantis/api/`, and `alembic/`. Produce a field-level data dictionary covering observed facts, inferred relationships, analyst annotations, source provenance, timestamps/timezones, amount units/decimals, and deletion/retention behavior. Identify where one field currently mixes concepts or where null/unknown is conflated with zero. Do not change schema yet. Deliver a diagram/table, prioritized defects, a proposed versioned schema contract, and migration risks. Acceptance: every database model field and externally returned API field is accounted for; all money is represented as integer minor units plus asset/decimals; no source observation is overwritten by inference.

### Prompt 1.2 — Harden versioned migrations and full-width money

> Review `alembic/`, `mantis/db/models.py`, `mantis/db/session.py`, `manage.py db-upgrade`, and startup behavior. Verify fresh install, legacy SQLite upgrade, PostgreSQL upgrade, idempotent rerun, migration failure recovery, and rollback limits. Add throwaway-database migration checks, including values beyond 32-bit range and existing rows/indexes/foreign keys. Ensure a versioned database is changed only by migrations, not opportunistic `create_all`. Document the exact upgrade command and backup requirement. Acceptance: 64-bit ranges survive upgrade byte-for-byte as integer values; the live user database is not used in tests; upgrade status is observable; any non-safe downgrade is documented and blocked or fails clearly.

### Prompt 1.3 — Make ingestion explicit, loss-aware, and idempotent

> Improve bank CSV and TRON JSON import boundaries in `mantis/ingest/` and `mantis/api/app.py`. Define versioned parser profiles/aliases, required fields, numeric bounds, timezone assumptions, date precision, debit/credit sign rules, duplicate keys, and malformed-row behavior. Return a row-level import report with accepted/rejected counts, warning codes, source row/event IDs, and reconciliation status. A parser must not guess a counterparty identity from narration alone. Acceptance: duplicate upload and duplicate transfer event are deterministic; malformed rows are either rejected or retained with a visible warning and stable source location; bank opening + credits − debits is exact; no file is called verified/authentic by parsing alone.

### Prompt 1.4 — Establish evidence and audit lifecycle guarantees

> Review content-addressed evidence storage, source downloads, trace manifests, and `append_audit`. Define an append-only application behavior for source facts and review decisions; record actor, UTC time, action, affected IDs, input/output manifest hashes, and previous hash. Test missing/corrupt evidence, duplicate content, partial import failure, and transaction rollback. Add a clean boundary between operational database hashes and externally anchored/signed evidence. Acceptance: failed imports do not leave misleading partial rows; existing source bytes remain retrievable and hash-checkable; audit verification detects edited/deleted/reordered events; documentation makes clear that a local hash chain is not immutable legal custody.

### Prompt 1.5 — Secure the local and shared API modes

> Threat-model all routes and file handling in `mantis/api/app.py`. Implement a deployment mode that keeps loopback-only local use simple and requires individual authentication, case-scoped authorization, server-side session controls, and least-privilege roles before shared-network use. Validate CORS, upload size/type, filenames, path traversal, API-key handling, error leakage, rate limits, and authorization on every case route. Do not log raw account/phone data or secrets. Acceptance: automated checks prove one user cannot read or mutate another case; unauthenticated shared-mode calls fail closed; local demo still works without exposing a network listener.

### Prompt 1.6 — Make backup, restore, and operational status real

> Add documented and testable backup/restore workflows for the database and evidence directory, including SQLite WAL-consistent backup, PostgreSQL backup, restore verification, and retention. Add a health/status report that separates API readiness, database readiness, evidence-store readiness, migration revision, and available optional components without exposing sensitive case data. Acceptance: restore a throwaway case and its source files, re-verify every source hash, and reproduce the saved analysis manifest; explain backup age and migration compatibility; no “healthy” status when required persistence is unavailable.

### Prompt 1.7 — Publish stable API contracts for the other tracks

> Inventory routes and create a versioned API contract for cases, uploads, entities, traces, review decisions, saved searches, manifests, and exports. Normalize validation errors and pagination; specify compatibility rules and stable enums. Add request/response examples using only synthetic data. Coordinate with Person 2 on claim/evidence payloads and Person 3 on UI requirements. Acceptance: OpenAPI matches actual behavior; integration checks exercise the documented workflow; no UI feature depends on undocumented SQL or hidden assumptions.

---

# Person 2 — Analytics, algorithm quality, and evaluation

**Outcome:** Every analytic output has a clear meaning, an evaluation record, and an explanation. New algorithms improve discovery without implying identity, guilt, conservation, or recoverable value beyond the data.

### Prompt 2.1 — Build the evaluation protocol before tuning

> Create `evals/` with a versioned evaluation schema and a small deterministic corpus covering true links, hard non-links, ambiguous links, missing fields, reused identifiers, benign payroll/merchant flows, duplicate imports, date-only data, timezone offsets, fan-in/fan-out, and cross-rail cases. Separate development fixtures from a held-out evaluation set. Define labeling policy, adjudication, leakage controls, precision/recall, false-positive rate, calibration metrics, runtime, and per-case breakdowns. Acceptance: every fixture has source IDs, expected outputs, rationale, and a synthetic/real designation; one command prints a machine-readable and human-readable report; no synthetic score is represented as real-world accuracy.

### Prompt 2.2 — Calibrate and explain entity linkage

> Audit `mantis/correlation/record_linkage.py`. Replace hand-assumed m/u weights only if labeled data justifies it; otherwise retain a transparent review rank. Implement comparison levels for exact/partial/missing/invalid, field-specific normalization, time-window semantics, and counter-evidence. Detect duplicate identifiers and common identifiers that should not imply identity. Expose reviewer disposition and reason separately from algorithm ranking. Acceptance: compare against the evaluation corpus and a simple oracle; report false-positive/false-negative examples; last-four/account, shared phone, VPA prefix, and name similarity alone can never confirm identity; all output cites its fields and limitations.

### Prompt 2.3 — Specify and implement bounded time-respecting path search

> Audit `mantis/graph/tracer.py` and the current graph payload. Separate reachability discovery from amount allocation. Design a deterministic top-K simple-path/search method with explicit asset, time precision, hop, continuity window, max-result, and cycle constraints. Include pruning/memoization and explainable path ranking; do not use a raw heuristic score as a probability. Preserve parallel transfers and do not suppress valid branches merely because they converge. Acceptance: tests include cycles, ties, duplicate references, simultaneous events, date-only timestamps, fan-out, and a brute-force oracle on small graphs; output lists why each path was included/excluded and reports truncation limits.

### Prompt 2.4 — Correct flow and taint semantics or keep them unavailable

> Audit `compute_taint_models` and every recovery-facing output. Write formal definitions for poison, proportional/haircut, and FIFO using asset-specific balances/lots, fees, timestamps, and split/merge semantics. Implement only what required balances and transfer evidence support. Do not report a recovery value if source/destination balances are absent, mixed assets are unresolved, or conservation fails. Acceptance: each model has a hand-worked example and property checks for non-negativity, upper bounds, asset separation, exact conservation where assumptions permit, and explicit unknowns; if those conditions are unmet, keep the output disabled and explain the missing input.

### Prompt 2.5 — Rework cross-rail matching for real transaction shapes

> Audit `mantis/correlation/seam_solver.py` and trace integration. Preserve exact decimal arithmetic and FX provenance. First define when one-to-one matching is defensible; then design split/merge matching with capacities, fee intervals, time windows, and optional account/order references. Compare sparse NetworkX matching with a min-cost-flow/CP-SAT formulation only on evaluation cases that actually require it. Acceptance: one-to-one remains the safe baseline; split/merge candidates are never silently forced; unmatched records remain visible; every assignment includes candidate/alternate pairs, FX basis, fee assumptions, exact amounts, and solver objective.

### Prompt 2.6 — Evaluate typology indicators and uncertainty

> Audit `mantis/intelligence/typologies.py` and each threshold in config. For every detector, define the pattern, required data, unit, rule version, benign alternatives, evidence IDs, counter-evidence, and failure modes. Use labeled holdout cases to measure false positives and threshold sensitivity. Add threshold boundary and missing-data tests. Acceptance: output says “indicator/lead,” never “crime”; thresholds are configurable and versioned; no percentage is called confidence/probability without calibration; an indicator can be reviewed, rejected, and replayed without altering original transfers.

### Prompt 2.7 — Add sensitivity and “what would change this?” analysis

> Prototype bounded counterfactual sensitivity for uncertain links and paths. For each candidate relationship, compare the trace with the relationship included/excluded, report which nodes/paths change, and rank the next missing record by expected ability to distinguish competing hypotheses. Begin with deterministic rules and explicit assumptions; do not call the result causal or statistically optimal without a validated model. Acceptance: deterministic small cases, strict result caps, analyst-visible competing explanations, no automatic disposition, and metrics showing whether the sensitivity view helps identify fragile conclusions.

---

# Person 3 — Investigator workflow, UX, accessibility, and release

**Outcome:** A new investigator can complete the end-to-end workflow, understand what is fact versus inference, spot missing evidence, and explain the result to a reviewer without training or misleading visuals.

### Prompt 3.1 — Observe and map investigator tasks

> Review `mantis/web/index.html`, the live app, and the documented case workflow. Define primary users, first-session tasks, recurring review tasks, judge/demo tasks, error recovery, and case closure. Map each page to a task and identify duplicated navigation, dead ends, ambiguous terms, dense/low-contrast copy, and unsupported capabilities. Do not redesign from taste alone. Deliver task flows, ranked usability issues, and acceptance tasks that can be observed. Acceptance: create case, import files, reconcile, inspect source, trace, review a candidate, and reopen a prior run are all represented end-to-end.

### Prompt 3.2 — Establish a product-native design system

> Consolidate the current forest/paper look into accessible design tokens and reusable components in `mantis/web/`. Define type scale, spacing, contrast, interactive states, table density, status colors, typography, and responsive breakpoints. Remove repeated one-off inline styles and AI-template visual clichés. Keep color meaning stable (observed, inferred, needs review, rejected) and never rely on color alone. Acceptance: keyboard focus is visible, text contrast meets WCAG AA where applicable, reduced-motion is respected, 320px/mobile and desktop work, and a screenshot review covers each main view.

### Prompt 3.3 — Make source ingestion reviewable before/after upload

> Design the import flow around source preview, recognized columns, timezone/currency assumptions, warnings, duplicate detection, reconciliation, and accepted/rejected row counts. After upload, let the investigator drill from normalized transactions back to the exact source file and source row. Make failed imports recoverable without duplicate partial records. Coordinate required fields/errors with Person 1. Acceptance: one malformed/ambiguous row is visibly flagged; a reconciled statement is clearly distinguished from an unauthenticated source; the user can tell what was imported and what was skipped.

### Prompt 3.4 — Make the graph a controlled investigation surface

> Improve graph controls for seed selection, time range, asset/rail, hop depth, entity type, candidate relationship visibility, and result caps. Selecting a node/edge should show observed fields, source provenance, candidate rationale, counter-evidence, and review status. Add a synchronized ledger/timeline mode and useful empty/loading/error states. Avoid a “spaghetti graph” and avoid visual encoding that implies amount conservation when none was computed. Acceptance: a reviewer can find the seed, follow one path, distinguish observed flow from cross-rail candidate, inspect the exact source, and reset filters without losing the saved run.

### Prompt 3.5 — Build a review panel for claims, alternatives, and manifests

> Add clear candidate/indicator cards showing supporting and counter-evidence IDs, exact source links, algorithm/config version, FX source/time, analyst disposition, and the analysis-manifest hash. Allow review annotations to be added as new events, not edits to imported data. Show why a result is unavailable when inputs are missing. Acceptance: “observed,” “candidate,” “heuristic,” “reviewed,” and “unknown” have consistent wording across graph, table, query, and export; a user can compare saved runs; no probability or recovery amount is implied without evaluation.

### Prompt 3.6 — Make queries and exports grounded and review-safe

> Improve deterministic query UX and create a review export that includes case metadata, selected source IDs, import/parser warnings, trace manifest, FX provenance, candidate rationales, reviewer decisions, and limitations. Every answer/export claim must be linked to stored records; omitted or truncated data must be stated. Keep external LLMs and provider searches disabled by default. Acceptance: an export can be reconciled to UI/API records; amounts are asset-separated and exact; report language cannot convert candidates into facts or draft legal decisions into approved actions.

### Prompt 3.7 — Make the judge/demo and release path repeatable

> Verify the three-step local install/start/stop flow, synthetic judge pack, browser behavior, empty state, and error recovery. Add a demo reset that operates only on a named disposable test database and never on the user workspace. Document prerequisites, import steps, expected outputs, limitations, migration/backup command, and how to distinguish synthetic evidence from real records. Acceptance: a clean machine can start the app, upload the synthetic pack, show the three-edge chain trace and one possible candidate, reopen the saved run, and stop the service; no demo data is silently inserted into the real database.

---

## Integration cadence and release gates

1. **Kickoff:** agree on shared vocabulary (`observation`, `candidate`, `indicator`, `decision`, `unknown`), branch naming, synthetic-data policy, and API contracts.
2. **Contract checkpoint:** Person 1 publishes data/API contract; Person 2 publishes analytic output/evaluation schema; Person 3 aligns UI components to both.
3. **Weekly integration:** merge one small change per ownership area, run migration checks on temporary databases, run the analytic evaluation report, and exercise one browser workflow.
4. **Release candidate:** run a fresh install, legacy migration, backup/restore, CSV import, TRON import, trace, source drilldown, candidate review, saved-run reopen, and export. No workstream declares “done” based solely on code compilation.

### Exit gates before claiming “production ready”

- Real deployment identity, case-level authorization, secrets, encryption, audit anchoring, backup/restore, retention, and incident response have been reviewed and exercised.
- Institution-specific imports have approved schemas and field-level validation; every source row is accounted for.
- Algorithm claims are measured on representative, adjudicated, held-out cases; false positives and calibration are published internally.
- Flow/recovery calculations have documented conservation rules and tested balance inputs; otherwise they remain unavailable.
- Accessibility and investigator usability tasks have been tested with users; browser and API error states are handled.
- Provider integrations, if any, have source provenance, pagination/checkpoints, rate limits, retries, network/confirmation status, and a clear separation from uploaded evidence.
