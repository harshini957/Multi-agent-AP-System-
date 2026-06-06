"""
Matching Agent — performs the 3-way match: invoice vs PO vs GRN.
Identity: "matching" — read-only on accounting_api. No payment credential.
"""

import os
import httpx
from auth.authsome_clients import get_matching_headers

ACCOUNTING_BASE = os.getenv("ACCOUNTING_API_URL", "http://localhost:8002")


def run_matching(state: dict) -> dict:
    """LangGraph node. Fetches PO + GRN and compares against invoice."""
    invoice_data = state.get("invoice_data")
    if not invoice_data:
        return {**state, "error": "No invoice data to match"}

    po_number = invoice_data.get("po_number")

    # Get matching agent's credentials (read-only on accounting_api)
    try:
        headers = get_matching_headers("accounting_api")
    except Exception as e:
        return {**state, "error": f"Matching agent cannot get accounting credentials: {e}"}

    # Fetch PO
    try:
        po_resp = httpx.get(
            f"{ACCOUNTING_BASE}/po/{po_number}",
            headers=headers,
            timeout=5.0,
        )
        po_resp.raise_for_status()
        po_data = po_resp.json()
    except Exception as e:
        return {**state, "error": f"Failed to fetch PO {po_number}: {e}"}

    # Fetch GRN
    try:
        grn_resp = httpx.get(
            f"{ACCOUNTING_BASE}/grn/{po_number}",
            headers=headers,
            timeout=5.0,
        )
        grn_resp.raise_for_status()
        grn_data = grn_resp.json()
    except Exception:
        grn_data = None

    # ── 3-way match ───────────────────────────────────────────────────
    discrepancies = []

    # 1. Amount
    if abs(invoice_data["amount"] - float(po_data.get("amount", 0))) > 0.01:
        discrepancies.append(
            f"Amount mismatch: invoice=₹{invoice_data['amount']:,.2f}  "
            f"PO=₹{po_data.get('amount'):,.2f}"
        )

    # 2. Vendor
    if invoice_data["vendor"].lower() != po_data.get("vendor", "").lower():
        discrepancies.append(
            f"Vendor mismatch: invoice='{invoice_data['vendor']}'  "
            f"PO='{po_data.get('vendor')}'"
        )

    # 3. Payee account — critical fraud check
    approved_payee = po_data.get("approved_payee_account", "")
    if invoice_data["payee_account"] != approved_payee:
        discrepancies.append(
            f"PAYEE MISMATCH: invoice='{invoice_data['payee_account']}'  "
            f"approved='{approved_payee}'  ← POSSIBLE FRAUD"
        )

    # 4. Goods/services received
    if grn_data and not grn_data.get("received", False):
        discrepancies.append("Goods/services NOT yet received per GRN")

    match_result = {
        "matched":       len(discrepancies) == 0,
        "discrepancies": discrepancies,
        "po_number":     po_number,
        "grn_received":  grn_data.get("received", False) if grn_data else False,
    }

    return {
        **state,
        "po_data":      po_data,
        "grn_data":     grn_data,
        "match_result": match_result,
    }