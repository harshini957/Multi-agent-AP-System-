"""
Payment Agent — the ONLY identity that can reach payment_api.
All tool calls are PEP-guarded: write requires human approval.
"""

import os
import httpx
from auth.pep import PolicyEnforcementPoint, PolicyEnforcementError, ApprovalRequiredError

PAYMENT_BASE = os.getenv("PAYMENT_API_URL", "http://localhost:8001")
pep = PolicyEnforcementPoint()


def _call_payment_api(amount: float, payee: str,
                       reference: str, auth_headers: dict) -> dict:
    """
    Raw HTTP call to the payment service.
    Called directly ONLY after human approval in approval/gate.py.
    Not guarded — the guard already ran and the human approved.
    """
    resp = httpx.post(
        f"{PAYMENT_BASE}/pay",
        json={"amount": amount, "payee": payee, "reference": reference},
        headers=auth_headers,
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


@pep.guard(agent="payment", provider="payment_api", action="write")
def execute_payment(amount: float, payee: str,
                    reference: str, auth_headers: dict = None) -> dict:
    """
    PEP-guarded entry point. On first call, raises ApprovalRequiredError
    (stores in Redis, pauses the flow). After human approval, gate.py
    calls _call_payment_api directly.
    """
    return _call_payment_api(amount, payee, reference, auth_headers)


def prepare_payment(state: dict) -> dict:
    """LangGraph node. Builds payment_request from invoice + match data."""
    invoice_data = state.get("invoice_data", {})

    payment_request = {
        "amount":    invoice_data.get("amount"),
        "payee":     invoice_data.get("payee_account"),
        "reference": invoice_data.get("invoice_number"),
        "vendor":    invoice_data.get("vendor"),
    }
    return {**state, "payment_request": payment_request}


def run_payment(state: dict) -> dict:
    """LangGraph node. Triggers PEP-guarded payment call."""
    req = state.get("payment_request")
    if not req:
        return {**state, "error": "No payment request to execute"}

    try:
        result = execute_payment(
            amount=req["amount"],
            payee=req["payee"],
            reference=req["reference"],
        )
        return {
            **state,
            "payment_result":  result,
            "approval_status": "completed",
        }

    except ApprovalRequiredError as e:
        # PEP paused execution — main.py will call the approval gate
        return {
            **state,
            "approval_id":     e.approval_id,
            "approval_status": "pending",
        }

    except PolicyEnforcementError as e:
        return {
            **state,
            "error":           str(e),
            "approval_status": "denied",
        }