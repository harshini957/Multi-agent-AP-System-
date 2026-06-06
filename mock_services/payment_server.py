"""
Mock Payment API — simulates a bank/payment gateway.
Requires a valid Bearer token (the PAYMENT_API_KEY).
Only the payment agent's vault holds this key.
"""

import os
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Mock Payment API")


class PaymentRequest(BaseModel):
    amount:    float
    payee:     str
    reference: str


def _validate(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    token    = authorization.split("Bearer ", 1)[1]
    expected = os.getenv("PAYMENT_API_KEY", "mock-payment-key-secret")
    if token != expected:
        raise HTTPException(403, "Invalid payment API key — access denied")


@app.post("/pay")
async def execute_payment(
    req: PaymentRequest,
    authorization: str = Header(default=""),
):
    _validate(authorization)
    return {
        "status":         "success",
        "transaction_id": f"TXN-{req.reference}",
        "amount":         req.amount,
        "payee":          req.payee,
        "message":        "Payment executed successfully",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "payment"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")