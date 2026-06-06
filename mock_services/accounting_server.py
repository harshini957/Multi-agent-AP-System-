"""
Mock Accounting API — returns Purchase Orders and Goods Receipt Notes.
The matching agent uses this (read-only). Payment agent has no access.
"""

import os
from fastapi import FastAPI, HTTPException, Header
import uvicorn

app = FastAPI(title="Mock Accounting API")

PURCHASE_ORDERS = {
    "PO-001": {
        "po_number":            "PO-001",
        "vendor":               "Tata Consultancy Services",
        "amount":               50000.00,
        "currency":             "INR",
        "approved_payee_account": "TCS-BANK-ACC-123",
        "status":               "open",
        "line_items": [
            {"description": "Cloud Services - Q1", "quantity": 1, "unit_price": 50000.00}
        ],
    }
}

GOODS_RECEIPTS = {
    "GRN-001": {
        "grn_number": "GRN-001",
        "po_number":  "PO-001",
        "received":   True,
        "line_items": [
            {"description": "Cloud Services - Q1", "quantity": 1}
        ],
    }
}


def _validate(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    token    = authorization.split("Bearer ", 1)[1]
    expected = os.getenv("ACCOUNTING_API_KEY", "mock-accounting-key")
    if token != expected:
        raise HTTPException(403, "Invalid accounting API key")


@app.get("/po/{po_number}")
async def get_po(po_number: str, authorization: str = Header(default="")):
    _validate(authorization)
    po = PURCHASE_ORDERS.get(po_number)
    if not po:
        raise HTTPException(404, f"PO {po_number} not found")
    return po


@app.get("/grn/{po_number}")
async def get_grn(po_number: str, authorization: str = Header(default="")):
    _validate(authorization)
    for grn in GOODS_RECEIPTS.values():
        if grn["po_number"] == po_number:
            return grn
    raise HTTPException(404, f"GRN for {po_number} not found")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "accounting"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")