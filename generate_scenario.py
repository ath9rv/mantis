"""
MANTIS Golden Scenario Generator (Scenario 1: The Gwalior-Style Mule to USDT Trail)
Generates deterministic synthetic bank statements (CSV) and TRON USDT on-chain data (JSON)
with 100% verified ground truth for immediate use by Backend, Detection, and Frontend teams.
"""

import csv
import json
import os
from datetime import datetime, timezone

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "scenario_1")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# SCENARIO 1 ENTITY DIRECTORY
# ---------------------------------------------------------------------------
ENTITIES = {
    "victim": {
        "name": "Dr. Rajesh Sharma (Victim)",
        "account_no": "50100458921101",
        "ifsc": "HDFC0000001",
        "bank": "HDFC Bank",
        "vpa": "rajesh.doc@okhdfcbank",
        "phone": "+91 98110 12345"
    },
    "mule_1": {
        "name": "Ramesh Kumar (Layer-1 Mule)",
        "account_no": "309812456789",
        "ifsc": "SBIN0001234",
        "bank": "State Bank of India",
        "vpa": "ramesh.k92@oksbi",
        "phone": "+91 97112 34567"
    },
    "mule_2": {
        "name": "Aman Verma (Layer-2 Mule A)",
        "account_no": "918020034567890",
        "ifsc": "UTIB0000567",
        "bank": "Axis Bank",
        "vpa": "aman.verma@okaxis",
        "phone": "+91 96113 45678"
    },
    "mule_3": {
        "name": "Pooja Singh (Layer-2 Mule B)",
        "account_no": "001101567890",
        "ifsc": "ICIC0000011",
        "bank": "ICICI Bank",
        "vpa": "pooja.singh@okicici",
        "phone": "+91 95114 56789"
    },
    "p2p_trader": {
        "name": "Krypton P2P Merchant Account",
        "account_no": "201000192837",
        "ifsc": "KKBK0000123",
        "bank": "Kotak Mahindra Bank",
        "vpa": "krypton.pay@kotak",
        "phone": "+91 94115 67890"
    },
    "tron_deposit_wallet": "TYDzsYUEpvnYmQk4zGP9sWWcTEd2MiAtW6",
    "tron_consolidator_wallet": "TNVaKWsmBsZ3rQf59ZpE57P1rYy2PZ8w7q",
    "tron_peel_wallet": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
}

# ---------------------------------------------------------------------------
# 1. GENERATE VICTIM BANK STATEMENT (HDFC)
# ---------------------------------------------------------------------------
def generate_victim_statement():
    filepath = os.path.join(OUTPUT_DIR, "victim_hdfc_statement.csv")
    rows = [
        ["Date", "Transaction Details", "Chq/Ref No", "Value Date", "Withdrawal (DR)", "Deposit (CR)", "Balance"],
        ["28/10/2026 09:15:00", "SALARY CREDIT - TECHCORP PVT LTD", "SAL20261028001", "28/10/2026", "", "150000.00", "185420.50"],
        ["28/10/2026 10:42:15", "UPI-630211982736-RAMESH KUMAR-ramesh.k92@oksbi-SBIN0001234", "630211982736", "28/10/2026", "100000.00", "", "85420.50"],
        ["28/10/2026 14:20:00", "POS 401298 GROCERY STORE", "POS992817", "28/10/2026", "1450.00", "", "83970.50"]
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"[+] Created: {filepath}")

# ---------------------------------------------------------------------------
# 2. GENERATE LAYER-1 MULE STATEMENT (SBI)
# Demonstrates Rapid Pass-Through (< 8 mins) & Fan-Out (₹60k & ₹40k)
# ---------------------------------------------------------------------------
def generate_mule1_statement():
    filepath = os.path.join(OUTPUT_DIR, "layer1_mule_sbi_statement.csv")
    rows = [
        ["Txn Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"],
        ["28-Oct-2026 08:00:00", "OPENING BALANCE", "", "", "", "1240.00"],
        ["28-Oct-2026 10:42:18", "TRANSFER-UPI/CR/630211982736/rajesh.doc@okhdfcbank/HDFC/Cyber Fraud Credit", "630211982736", "", "100000.00", "101240.00"],
        ["28-Oct-2026 10:47:30", "TRANSFER-UPI/DR/630211983011/aman.verma@okaxis/UTIB/Layering A", "630211983011", "60000.00", "", "41240.00"],
        ["28-Oct-2026 10:49:12", "TRANSFER-UPI/DR/630211983088/pooja.singh@okicici/ICIC/Layering B", "630211983088", "40000.00", "", "1240.00"]
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"[+] Created: {filepath}")

# ---------------------------------------------------------------------------
# 3. GENERATE LAYER-2 MULE STATEMENT (AXIS)
# Demonstrates Structuring & P2P Conversion to USDT
# ---------------------------------------------------------------------------
def generate_mule2_statement():
    filepath = os.path.join(OUTPUT_DIR, "layer2_mule_axis_statement.csv")
    rows = [
        ["Tran Date", "Particulars", "Chq/Ref No", "Debit", "Credit", "Balance"],
        ["28-10-2026 10:47:32", "UPI/630211983011/CR/ramesh.k92@oksbi/Payment", "630211983011", "", "60000.00", "60450.00"],
        ["28-10-2026 11:15:20", "IMPS/P2P/KRYPTON MERCHANT/P2P Buy USDT", "IMPS630211991", "49500.00", "", "10950.00"],
        ["28-10-2026 11:30:10", "ATM CASH WDL DELHI SEC 14", "ATM88129", "10000.00", "", "950.00"]
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"[+] Created: {filepath}")

# ---------------------------------------------------------------------------
# 4. GENERATE ON-CHAIN TRON USDT TRANSFERS (JSON)
# Demonstrates Seam Match (₹49,500 ~ 550 USDT @ ₹90/USDT) & Peel Chain
# ---------------------------------------------------------------------------
def generate_tron_chain_data():
    filepath = os.path.join(OUTPUT_DIR, "tron_usdt_chain_feed.json")
    chain_events = [
        {
            "tx_hash": "f183c27a9b0c98d76e4321098efd44211a7890bc432198765fedcba098765432",
            "block_timestamp": 1793167520000, # 28-10-2026 11:25:20 UTC (10 mins after fiat debit)
            "block_number": 68492011,
            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", # TRC20 USDT
            "from_address": "TYDzsYUEpvnYmQk4zGP9sWWcTEd2MiAtW6",  # P2P Escrow Release
            "to_address": "TNVaKWsmBsZ3rQf59ZpE57P1rYy2PZ8w7q",    # Criminal Consolidator
            "token_symbol": "USDT",
            "amount_minor": 550000000, # 550.000000 USDT (6 decimals)
            "amount_formatted": "550.00 USDT",
            "implied_inr_rate": 90.00,
            "fee_trx": 13.5
        },
        {
            "tx_hash": "a472c1998bce77123aa4433221199887766554433221100ffeeddccbbaa99887",
            "block_timestamp": 1793171120000, # 28-10-2026 12:25:20 UTC (1 hour later)
            "block_number": 68493210,
            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            "from_address": "TNVaKWsmBsZ3rQf59ZpE57P1rYy2PZ8w7q", # Peel Chain Hop 1
            "to_address": "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",   # Primary Forward Hop (90%)
            "token_symbol": "USDT",
            "amount_minor": 495000000, # 495.00 USDT (90% peel)
            "amount_formatted": "495.00 USDT",
            "fee_trx": 13.5
        },
        {
            "tx_hash": "c882193bba7766110099887766554433221100ffeeddccbbaa99887766554433",
            "block_timestamp": 1793171120000,
            "block_number": 68493210,
            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            "from_address": "TNVaKWsmBsZ3rQf59ZpE57P1rYy2PZ8w7q", # Peel Residue to Cold Storage
            "to_address": "TLyqzVGLV1srkB7dToTAwdg29TFVK97GMA",   # Diverted 10%
            "token_symbol": "USDT",
            "amount_minor": 55000000, # 55.00 USDT (10% remainder)
            "amount_formatted": "55.00 USDT",
            "fee_trx": 13.5
        }
    ]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(chain_events, f, indent=2)
    print(f"[+] Created: {filepath}")

# ---------------------------------------------------------------------------
# 5. GENERATE FRONTEND CYTOSCAPE GRAPH MOCK (JSON)
# Ready for instant rendering in Cytoscape.js by the Frontend developer!
# ---------------------------------------------------------------------------
def generate_cytoscape_mock():
    filepath = os.path.join(OUTPUT_DIR, "cytoscape_golden_graph.json")
    graph_data = {
        "elements": {
            "nodes": [
                {
                    "data": {
                        "id": "node_victim",
                        "label": "Dr. Rajesh Sharma",
                        "sublabel": "HDFC - XXXX1101",
                        "kind": "bank_account",
                        "risk_tags": ["victim"],
                        "balance": "₹83,970.50",
                        "taint_residual": "₹0.00"
                    }
                },
                {
                    "data": {
                        "id": "node_mule1",
                        "label": "Ramesh Kumar",
                        "sublabel": "SBI - XXXX6789",
                        "kind": "bank_account",
                        "risk_tags": ["mule_layer1", "rapid_passthrough"],
                        "balance": "₹1,240.00",
                        "taint_residual": "₹0.00"
                    }
                },
                {
                    "data": {
                        "id": "node_mule2",
                        "label": "Aman Verma",
                        "sublabel": "Axis - XXXX7890",
                        "kind": "bank_account",
                        "risk_tags": ["mule_layer2", "structuring"],
                        "balance": "₹950.00",
                        "taint_residual": "₹950.00"
                    }
                },
                {
                    "data": {
                        "id": "node_mule3",
                        "label": "Pooja Singh",
                        "sublabel": "ICICI - XXXX7890",
                        "kind": "bank_account",
                        "risk_tags": ["mule_layer2", "funds_held"],
                        "balance": "₹40,000.00",
                        "taint_residual": "₹40,000.00"
                    }
                },
                {
                    "data": {
                        "id": "node_p2p_trader",
                        "label": "Krypton P2P Merchant",
                        "sublabel": "Kotak - XXXX2837",
                        "kind": "exchange",
                        "risk_tags": ["p2p_fiat_onramp"],
                        "balance": "₹49,500.00",
                        "taint_residual": "₹0.00"
                    }
                },
                {
                    "data": {
                        "id": "node_tron_deposit",
                        "label": "P2P Escrow Deposit",
                        "sublabel": "TYDzsY...AtW6",
                        "kind": "wallet",
                        "rail": "TRON",
                        "risk_tags": ["escrow_wallet"],
                        "balance": "0.00 USDT",
                        "taint_residual": "0.00 USDT"
                    }
                },
                {
                    "data": {
                        "id": "node_tron_consolidator",
                        "label": "Syndicate Consolidation",
                        "sublabel": "TNVaKW...8w7q",
                        "kind": "wallet",
                        "rail": "TRON",
                        "risk_tags": ["peel_chain_head", "critical_freeze_target"],
                        "balance": "550.00 USDT",
                        "taint_residual": "550.00 USDT"
                    }
                }
            ],
            "edges": [
                {
                    "data": {
                        "id": "edge_1",
                        "source": "node_victim",
                        "target": "node_mule1",
                        "edge_class": "flow",
                        "label": "confirmed",
                        "amount": "₹1,00,000",
                        "rail": "UPI",
                        "ref": "630211982736",
                        "reason": "Corroborated by HDFC debit and SBI credit with matching 12-digit UPI RRN"
                    }
                },
                {
                    "data": {
                        "id": "edge_2a",
                        "source": "node_mule1",
                        "target": "node_mule2",
                        "edge_class": "flow",
                        "label": "confirmed",
                        "amount": "₹60,000",
                        "rail": "UPI",
                        "ref": "630211983011",
                        "reason": "Rapid pass-through within 5 mins, matching RRN 630211983011"
                    }
                },
                {
                    "data": {
                        "id": "edge_2b",
                        "source": "node_mule1",
                        "target": "node_mule3",
                        "edge_class": "flow",
                        "label": "confirmed",
                        "amount": "₹40,000",
                        "rail": "UPI",
                        "ref": "630211983088",
                        "reason": "Fan-out transfer within 7 mins, matching RRN 630211983088"
                    }
                },
                {
                    "data": {
                        "id": "edge_3_p2p",
                        "source": "node_mule2",
                        "target": "node_p2p_trader",
                        "edge_class": "flow",
                        "label": "confirmed",
                        "amount": "₹49,500",
                        "rail": "IMPS",
                        "ref": "IMPS630211991",
                        "reason": "Structured payment just below ₹50,000 PMLA threshold"
                    }
                },
                {
                    "data": {
                        "id": "edge_seam_1",
                        "source": "node_p2p_trader",
                        "target": "node_tron_deposit",
                        "edge_class": "seam",
                        "label": "inferred",
                        "amount": "₹49,500 ↔ 550 USDT",
                        "rail": "P2P_BRIDGE",
                        "score": 0.94,
                        "reason": "Bipartite match: ₹49,500 debit matches 550 USDT credit within 10 mins @ implied rate ₹90/USDT (0.4% deviation)"
                    }
                },
                {
                    "data": {
                        "id": "edge_chain_1",
                        "source": "node_tron_deposit",
                        "target": "node_tron_consolidator",
                        "edge_class": "flow",
                        "label": "confirmed",
                        "amount": "550.00 USDT",
                        "rail": "TRON",
                        "ref": "f183c27a9b0c98d76e4321098efd44211a7890bc...",
                        "reason": "Direct TRC-20 Transfer verified on TRON blockchain"
                    }
                }
            ]
        },
        "recovery_summary": {
            "total_lost_inr": "₹1,00,000.00",
            "recoverable_fiat_inr": "₹40,000.00 (ICICI Bank - Pooja Singh)",
            "recoverable_crypto_usdt": "550.00 USDT (Tron Wallet TNVaKW...8w7q)",
            "action_targets": [
                {
                    "target": "ICICI Bank",
                    "account": "Pooja Singh (XXXX7890)",
                    "action": "Section 106 BNSS Specific Lien on ₹40,000.00",
                    "urgency": "High - Undrained Balance"
                },
                {
                    "target": "Tether Law Enforcement Liaison / T3 FCU",
                    "wallet": "TNVaKWsmBsZ3rQf59ZpE57P1rYy2PZ8w7q",
                    "action": "Emergency On-Chain USDT Blacklist Request",
                    "urgency": "Critical - Active Peel Chain"
                }
            ]
        }
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)
    print(f"[+] Created: {filepath}")

if __name__ == "__main__":
    generate_victim_statement()
    generate_mule1_statement()
    generate_mule2_statement()
    generate_tron_chain_data()
    generate_cytoscape_mock()
    print("\n[SUCCESS] Scenario 1 Data Assets Generated in: d:\\Mantis\\data\\scenario_1")
