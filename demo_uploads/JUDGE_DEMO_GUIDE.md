# MANTIS judge demo upload pack

**These files contain entirely synthetic test data. They are not real bank records, blockchain activity, or market-price evidence.** Keep that distinction clear in the demonstration.

## Upload and show the workflow

1. Open `http://127.0.0.1:8000` and create a case named `Synthetic judge demo`.
2. In **Evidence & imports**, upload `01_synthetic_bank_statement.csv` as the bank statement. Use `Demo Bank Account` as the account-holder label. The statement should reconcile: opening ₹100,000 + credit ₹100,000 − debit ₹49,500 = closing ₹150,500.
3. Upload `02_synthetic_tron_transfers.json` as the TRON transfer export. It contains a 550 USDT receipt followed by two outgoing transfers (495 and 55 USDT).
4. Open **Trace & analysis** and select the 550 USDT TRON receipt at 09:08 on 30 October 2026 as the seed.
5. For the optional cross-rail candidate, enter rate `90`, source `Synthetic demo assumption — not market data`, and observation time `30 October 2026, 09:08` in the browser's local timezone. Run the trace.

## Expected result

- Five imported transfer records across the two files.
- A reconciled bank statement and retained source-file hashes.
- A three-record TRON trace: the 550 USDT seed and its 495/55 USDT outgoing transfers.
- One possible fiat/crypto candidate linking the ₹49,500 debit to the 550 USDT receipt at the synthetic rate assumption.
- A saved analysis manifest and activity-log entry.

The candidate is deliberately presented as an investigative lead, not proof. Do not describe the synthetic rate as a market observation or the generated activity as a real case.
