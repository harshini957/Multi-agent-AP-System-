"""
Intake Agent — reads the invoice, extracts structured data,
and detects prompt injection attempts.
Identity: "intake" — read-only on gmail. No payment credential.
"""

import json

INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "override",
    "bypass",
    "do not perform",
    "mark as approved",
    "immediately",
    "urgent",
    "high-priority override",
]


def run_intake(state: dict) -> dict:
    """LangGraph node. Parses invoice JSON and flags injections."""
    raw = state.get("raw_invoice", "")

    try:
        inv = json.loads(raw)
    except json.JSONDecodeError as e:
        return {**state, "error": f"Could not parse invoice: {e}"}

    # Collect all free-text fields that an attacker could poison
    free_text_fields = [
        inv.get("notes", "") or "",
        inv.get("payment_terms", "") or "",
        *[item.get("description", "") for item in inv.get("line_items", [])],
    ]
    all_text = " ".join(free_text_fields).lower()

    # Injection detection
    injection_detected = any(kw in all_text for kw in INJECTION_KEYWORDS)

    flags = []
    if injection_detected:
        snippet = (inv.get("notes", "") or "")[:120]
        flags.append(
            f"PROMPT INJECTION DETECTED in invoice notes: "
            f'"{snippet}..."'
        )

    # Suspicious payee heuristic
    payee = inv.get("payee_account", "") or ""
    if any(w in payee.upper() for w in ("ATTACKER", "FRAUD", "HACK", "TEST-EVIL")):
        flags.append(f"SUSPICIOUS PAYEE ACCOUNT: {payee}")

    invoice_data = {
        "invoice_number":    inv.get("invoice_number"),
        "vendor":            inv.get("vendor"),
        "po_number":         inv.get("po_number"),
        "amount":            float(inv.get("amount", 0)),
        "currency":          inv.get("currency", "INR"),
        "payee_account":     payee,
        "line_items":        inv.get("line_items", []),
        "notes":             inv.get("notes", ""),
        "injection_detected": injection_detected,
    }

    return {
        **state,
        "invoice_data": invoice_data,
        "intake_flags": flags,
    }