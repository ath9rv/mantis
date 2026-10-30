# MANTIS: Multi-Rail Financial Intelligence & Investigation Platform

> **Core Philosophy:** Hardcode the intelligence framework, not the investigation logic or its outcomes. Build for unknown investigations, not known examples.

MANTIS is an evidence-first financial forensics platform designed for cybercrime investigators, State Cyber Cells, FIU-IND, and banking fraud ops. It bridges the critical seam between domestic banking rails (UPI, IMPS, NEFT) and public blockchains (TRON TRC-20, Ethereum ERC-20), solving the custody boundary problem at P2P exchanges and centralized services.

---

## 1. Quick Start

### Prerequisites
* Python 3.10+
* (Optional) PostgreSQL 16 (defaults to zero-config local SQLite `mantis.db`)

### Launch Web Cockpit & API
```bash
# 1. Run verification pipeline
python manage.py test

# 2. Seed test fixtures
python manage.py seed

# 3. Start local development server
python manage.py run
```

Open your browser to:
* **Interactive Investigation Cockpit:** [http://localhost:8000/](http://localhost:8000/)
* **Interactive Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 2. System Architecture

```
d:\Mantis\
├── mantis\
│   ├── config.py                     # Runtime configuration (thresholds, windows, FX bands)
│   ├── core\
│   │   └── models.py                 # CanonicalTransaction, CanonicalEntity, SeamEdge, GapRequest
│   ├── db\
│   │   ├── session.py                # Database session factory (SQLite WAL / PostgreSQL)
│   │   └── models.py                 # SQLAlchemy ORM models matching canonical schema
│   ├── ingest\
│   │   ├── base.py                   # IST->UTC normalizer, safe currency parser, balance invariant
│   │   └── bank_statement.py         # Dynamic CSV adapter with fuzzy column mapping & reconciliation
│   ├── correlation\
│   │   ├── record_linkage.py         # Fellegi-Sunter probabilistic record linker (Splink-grade)
│   │   └── seam_solver.py            # Global constrained bipartite assignment seam matcher
│   ├── graph\
│   │   ├── tracer.py                 # Forward, backward, convergence tracing + 3 taint models
│   │   └── gap_planner.py            # Custody boundary detector & Section 94 BNSS notice generator
│   ├── intelligence\
│   │   └── typologies.py             # Rapid pass-through, structuring, peel chain, multi-victim convergence
│   ├── recovery\
│   │   └── manager.py                # Section 106 BNSS disputed lien calculator (Rajasthan HC compliant)
│   ├── copilot\
│   │   └── grounded_querier.py       # Strict database-grounded query engine citing exact TxIDs
│   ├── api\
│   │   └── app.py                    # Production FastAPI REST application
│   └── web\
│       └── index.html                # Interactive Cockpit with Cytoscape.js canvas
├── data\scenario_1\                  # Scenario 1 test fixtures
├── generate_scenario.py              # Synthetic scenario generator
├── manage.py                         # CLI entrypoint (run, seed, test)
└── test_pipeline.py                  # End-to-end integration test
```

---

## 3. Core Capabilities

### A. Dynamic Bank-Agnostic Ingestion & Balance Reconciler
* Automatically detects column headers (`Date`, `Particulars`, `Ref No`, `Debit`, `Credit`, `Balance`) across any bank format.
* Enforces the mathematical reconciliation invariant:
  $$\text{Opening Balance} + \sum \text{Credits} - \sum \text{Debits} == \text{Closing Balance}$$
* Automatically normalizes Indian Standard Time (IST, UTC+5:30) to canonical UTC.
* Retains unmapped columns in raw metadata for complete forensic audit trails.

### B. Probabilistic Record Linkage (Fellegi-Sunter / Splink)
* Evaluates log-likelihood ratios $w = \log_2(m / u)$ across masked account numbers, UPI VPAs, phone numbers, and transliterated Indian names.
* Preserves counter-evidence alongside supporting signals.

### C. Constrained Multi-Rail Seam Matching
* Solves the fiat-to-crypto matching problem globally via Bipartite Assignment over a sliding window ($\Delta t \le 2\text{h}$) with an FX tolerance band ($\pm 3.5\%$).
* Matches ₹49,500 IMPS debits to 550.00 USDT on-chain credits without requiring identical transaction IDs.

### D. The Investigation Gap Planner
* Recognizes centralized exchange custody boundaries where public blockchain tracing halts.
* Quantifies unresolved stuck balances and auto-drafts statutory **Section 94 BNSS, 2023** (Sec 91 CrPC) requisitions for internal order books, customer KYC, and subsequent withdrawal addresses.

### E. Recovery Center (Section 106 BNSS Liens)
* Complies strictly with the **Rajasthan High Court** ruling in *Shree Balaji Enterprises v. RBI* (2026):
  * **Prohibits blanket debit freezing.**
  * Calculates and marks a **lien ONLY on the specific disputed amount**, preserving normal commercial operations for the account holder.

### F. Evidence-First AI Copilot
* The AI never computes a fact or hallucinates an unproven link.
* Natural-language queries execute deterministic database lookups; responses cite exact transaction references and monetary amounts.

---

## 4. Legal & Regulatory Compliance

* **Section 63 BSA 2023 (Bharatiya Sakshya Adhiniyam):** Secondary electronic evidence accompanied by SHA-256 cryptographic hashes and Schedule Part A & B certificates (*Pune Bar Association v. UOI*, May 2026).
* **Section 106 BNSS 2023:** Mandatory prompt intimation to jurisdictional Judicial Magistrate upon marking liens.
* **MHA SOP (Jan 2026):** 90-day administrative hold expiry tracking for non-adjudicated liens.
* **DPDP Act 2023 Section 17(1)(c):** Statutory exemption for prevention and investigation of offenses, backed by Section 8(5) audit safeguards.
