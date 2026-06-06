"""
Phase 0 + Phase 1: Provision credentials and prove isolation.
Run this ONCE before starting the main flow.
Redis must be running (docker ps shows codebase_redis on port 6379).
"""

import os
from dotenv import load_dotenv

load_dotenv()

from auth.credential_broker import CredentialBroker, CredentialDeniedError
from auth.pdp import PolicyDecisionPoint, PDPRequest
from auth.pep import PolicyEnforcementPoint, PolicyEnforcementError, ApprovalRequiredError

# ── Provision ─────────────────────────────────────────────────────────
broker = CredentialBroker()
broker.provision("gmail",          os.getenv("GMAIL_API_KEY",      "mock-gmail-key"))
broker.provision("accounting_api", os.getenv("ACCOUNTING_API_KEY", "mock-accounting-key"))
broker.provision("payment_api",    os.getenv("PAYMENT_API_KEY",    "mock-payment-key-secret"))
broker.provision("resend",         os.getenv("RESEND_API_KEY",     "mock-resend-key"))
print("✓ Credentials provisioned in Redis\n")

# ── PDP decisions ──────────────────────────────────────────────────────
print("═══ PDP Policy Decisions ═══")
pdp = PolicyDecisionPoint()
tests = [
    ("intake",   "payment_api",    "write"),   # should DENY
    ("intake",   "gmail",          "read"),    # should ALLOW
    ("matching", "accounting_api", "read"),    # should ALLOW
    ("matching", "payment_api",    "write"),   # should DENY
    ("payment",  "payment_api",    "write"),   # should REQUIRE_APPROVAL
    ("payment",  "accounting_api", "read"),    # should DENY (not in policy)
]
for agent, provider, action in tests:
    r = pdp.evaluate(PDPRequest(agent, provider, action))
    sym = {"allow": "✓", "deny": "✗", "require_approval": "⏸"}.get(r.decision.value, "?")
    print(f"  {sym}  {agent:10} → {provider:15} [{action:5}]  "
          f"{r.decision.value.upper():20}  {r.reason}")

# ── PEP enforcement ────────────────────────────────────────────────────
print("\n═══ PEP Enforcement ═══")
pep = PolicyEnforcementPoint()

# Test 1: intake attempts to write to payment_api → must be BLOCKED
@pep.guard(agent="intake", provider="payment_api", action="write")
def intake_tries_to_pay(amount, auth_headers=None):
    return {"paid": amount}

# Test 2: payment attempts to write to payment_api → must be PAUSED for approval
@pep.guard(agent="payment", provider="payment_api", action="write")
def payment_executes(amount, auth_headers=None):
    return {"paid": amount, "headers_injected": bool(auth_headers)}

try:
    intake_tries_to_pay(50000)
    print("  ✗ SECURITY FAILURE: intake was NOT blocked (this should not happen)")
except PolicyEnforcementError as e:
    print(f"  ✓ BLOCKED: intake cannot access payment_api\n"
          f"    Reason: {e}")

try:
    payment_executes(50000)
    print("  ✗ Should have required approval")
except ApprovalRequiredError as e:
    print(f"\n  ⏸ PAUSED for approval (correct — payment requires human gate)")
    print(f"    Approval ID: {e.approval_id}")
    pending = pep.get_pending_approvals()
    print(f"    Pending approvals in queue: {len(pending)}")
    # Clean up test pending approval
    pep.mark_denied(e.approval_id)

# ── Audit log ──────────────────────────────────────────────────────────
print("\n═══ Audit Log ═══")
for entry in pdp.get_audit_log():
    import datetime
    ts  = datetime.datetime.fromtimestamp(entry["timestamp"]).strftime("%H:%M:%S")
    sym = {"allow": "✓", "deny": "✗", "require_approval": "⏸"}.get(entry["decision"], "?")
    print(f"  {sym} [{ts}] {entry['agent']:10} → {entry['provider']:15} "
          f"{entry['action']:5}  {entry['decision'].upper()}")

print("\n✓ Phase 0 + Phase 1 complete. Redis is working, isolation is proven.")
print("  Next: python main.py")