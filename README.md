# MANTIS

MANTIS is a local, evidence-led workspace for reviewing financial transfers across bank statements and public-chain exports. It imports investigator-supplied source files, retains each original file by SHA-256, links parsed rows to their source document, and lets an investigator run and revisit seeded transfer traces.

## Run MANTIS in three steps

1. Install Python 3.10 or later for Windows.
2. Double-click `start_mantis.bat`. It creates an isolated `.venv`, installs the version-bounded dependencies once, starts the server on loopback, checks `/api/health`, and opens the cockpit in your browser. The server logs stay under `.mantis-runtime/`.
3. Create a case and import your statement CSV or TRON transfer export. No scenario seed is required. Double-click `stop_mantis.bat` to stop the server.

For terminal use, `python manage.py run` remains available after `python -m pip install -r requirements.txt`. SQLite and a local `evidence/` folder are used by default; case data and local runtime files are excluded from Git.

The case page supports:

- Bank statement CSV import, with supported date, narration, debit, credit, reference, and running-balance columns. Unmapped cells and source row numbers are retained. Inspect the parser result and reconciliation before relying on it.
- TRON transfer JSON import, as an array of transfer objects or `{ "transfers": [...] }`. Each object needs `tx_hash`, `from_address`, `to_address`, integer `amount_minor`, and `block_timestamp` in Unix milliseconds; `decimals` defaults to 6, `asset`/`token_symbol` defaults to USDT, and `event_index`/`log_index` defaults to 0. Include the event index when one transaction hash has multiple token-transfer events. These values must come from a source export you trust.
- A source register, original-file downloads, transaction ledger, entity review, seeded graph tracing, saved trace runs, heuristic indicators, and a hash-linked activity log.

For API users, interactive documentation is at <http://127.0.0.1:8000/docs>. Example workflow:

1. `POST /api/cases` to create a case.
2. `POST /api/cases/{case_id}/ingest/csv` or `/ingest/tron-json` using multipart form data.
3. `GET /api/cases/{case_id}/transactions` to select a seed transfer.
4. `POST /api/cases/{case_id}/trace` with `{"seed_transfer_id":"..."}`. An optional investigator-supplied `market_fx_rate` enables fiat/USDT candidate matching; when supplied, include `market_fx_source` and timezone-aware `market_fx_observed_at` (for example, `2026-10-30T06:00:00Z`). Without a rate, MANTIS does not invent one.
5. `GET /api/cases/{case_id}/trace-runs` and `/audit` to review saved analysis and activity.

## Operating configuration

The default server binds to loopback only. Set a strong `MANTIS_API_KEY` before binding to a non-local interface; the key is a shared bearer credential protecting API routes, not individual investigator accounts or case-level authorization. The cockpit accepts it in the top bar and keeps it in that browser tab's session storage.

For a PostgreSQL database, first install `python -m pip install -r requirements-postgres.txt`, then set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL. Before using or upgrading an existing PostgreSQL workspace, run `python manage.py db-upgrade`; this applies the versioned schema migrations, including 64-bit monetary storage.

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./mantis.db` | SQLAlchemy database URL; PostgreSQL can be configured for a managed deployment |
| `MANTIS_EVIDENCE_DIR` | `./evidence` | Content-addressed original-file storage |
| `MANTIS_MAX_UPLOAD_BYTES` | `26214400` | Maximum upload size per file |
| `MANTIS_API_KEY` | unset | Shared bearer key; required for a non-loopback bind |
| `MANTIS_AUDIT_ACTOR` | `local_operator` | Actor label written to the activity log |
| `MANTIS_CORS_ORIGINS` | local ports | Comma-separated browser origins allowed to call the API |
| `HOST`, `PORT` | `127.0.0.1`, `8000` | Listening address and port |

The optional `python manage.py seed` command creates synthetic development fixtures. It is not part of a real case workflow. `python manage.py test` runs the repository's synthetic pipeline checks.

## How to interpret results

- Imported bank and chain rows are observed records as represented by their uploaded files; MANTIS does not independently authenticate those files or query a bank or blockchain provider.
- Statement balance reconciliation checks arithmetic in the supplied export. It does not establish that the statement is genuine or complete.
- Similar narration is not treated as proof of shared identity. Rows without a stable reference stay separate unresolved entities.
- Traces are time-ordered graph walks over recorded transactions. They do not allocate mixed account balances or compute taint residuals.
- Fiat/crypto matches and typology indicators are candidate leads based on configurable heuristics. Scores are not calibrated probabilities or findings.
- The optional GNN integration does not score cases until a compatible trained TorchScript model, documented feature pipeline, and reviewed evaluation set are configured; unavailable scores are shown as unavailable. Install `requirements-ml.txt` only for ML development.
- The case activity log uses per-case SHA-256 links and reports whether the stored chain is internally consistent. A database administrator can rewrite the database and recompute hashes; this is not external immutable storage, a digital signature, or a legally sufficient chain-of-custody service.
- The recovery endpoint stays unavailable until the system stores independently verified balances and a defensible residual-taint calculation.

## Deployment boundary

This is a functional local case workspace, not a secure multi-user production service. Before an agency or organization uses it operationally, add individual identity and case-level authorization, an externally anchored and signed audit trail, encrypted storage and backups, database migrations, retention/access policies, validated institution-specific import adapters, independent source verification, and security review. Live blockchain data providers and bank integrations are not configured; select providers, obtain credentials, and define their evidentiary handling before connecting them. Do not expose sensitive case data on an untrusted network.

See [TECH_STACK_REVIEW.md](TECH_STACK_REVIEW.md) for the keep/change/defer decisions behind the proposed production stack.

## Repository map

- `mantis/api/app.py` — FastAPI endpoints for case creation, evidence ingestion, transaction review, tracing, and audit.
- `mantis/ingest/` — CSV adapter and content-addressed evidence storage.
- `mantis/correlation/` — candidate fiat-to-crypto seam scoring and assignment.
- `mantis/graph/` — transaction tracing and investigation gap planning.
- `mantis/intelligence/` — rule-based review indicators.
- `mantis/web/index.html` — case-driven browser workspace.
- `data/scenario_1/` and `generate_scenario.py` — synthetic development fixture generator.
