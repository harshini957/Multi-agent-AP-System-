import json
import time
import uuid
import redis
from functools import wraps
from typing import Callable, Any

from auth.pdp import PolicyDecisionPoint, PDPRequest
from auth.policy_store import Decision
from auth.credential_broker import CredentialBroker, CredentialMissingError


class PolicyEnforcementError(Exception):
    """Raised when PDP returns DENY."""
    pass


class ApprovalRequiredError(Exception):
    """Raised when PDP returns REQUIRE_APPROVAL — execution is paused."""
    def __init__(self, approval_id: str, context: dict):
        self.approval_id = approval_id
        self.context     = context
        super().__init__(f"Human approval required. Approval ID: {approval_id}")


class PolicyEnforcementPoint:
    """
    Wraps tool functions with PDP evaluation.
    Agents call guarded tools — they can never bypass this wrapper.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.pdp         = PolicyDecisionPoint(redis_url)
        self.broker      = CredentialBroker(redis_url)
        self.r           = redis.from_url(redis_url)
        self.pending_key = "ap:pending_approvals"

    def guard(self, agent: str, provider: str, action: str) -> Callable:
        """
        Decorator factory. Wraps a tool function with PDP enforcement.

        Usage:
            pep = PolicyEnforcementPoint()

            @pep.guard(agent="payment", provider="payment_api", action="write")
            def execute_payment(amount, payee, reference, auth_headers=None):
                ...
        """
        def decorator(fn: Callable) -> Callable:
            @wraps(fn)
            def wrapper(*args, **kwargs) -> Any:
                request  = PDPRequest(
                    agent=agent,
                    provider=provider,
                    action=action,
                    context={"args": str(args), "kwargs": str(kwargs)},
                )
                response = self.pdp.evaluate(request)

                if response.denied:
                    raise PolicyEnforcementError(
                        f"PEP BLOCKED: {response.reason}\n"
                        f"Agent '{agent}' attempted '{action}' on "
                        f"'{provider}' — denied by policy."
                    )

                if response.needs_approval:
                    approval_id = str(uuid.uuid4())[:8]
                    pending = {
                        "id":       approval_id,
                        "agent":    agent,
                        "provider": provider,
                        "action":   action,
                        "args":     str(args),
                        "kwargs":   str(kwargs),
                        "status":   "pending",
                        "created":  time.time(),
                    }
                    self.r.hset(
                        self.pending_key,
                        approval_id,
                        json.dumps(pending),
                    )
                    raise ApprovalRequiredError(
                        approval_id=approval_id,
                        context=pending,
                    )

                # ALLOW — inject credential and execute
                try:
                    headers = self.broker.get_headers(agent, provider)
                    kwargs["auth_headers"] = headers
                except CredentialMissingError as e:
                    raise PolicyEnforcementError(f"Credential missing: {e}")

                return fn(*args, **kwargs)
            return wrapper
        return decorator

    # ------------------------------------------------------------------
    # Approval queue management
    # ------------------------------------------------------------------

    def get_pending_approvals(self) -> list:
        items = self.r.hgetall(self.pending_key)
        return [
            json.loads(v)
            for v in items.values()
            if json.loads(v)["status"] == "pending"
        ]

    def mark_approved(self, approval_id: str) -> None:
        self._update(approval_id, "approved")

    def mark_denied(self, approval_id: str) -> None:
        self._update(approval_id, "denied")

    def _update(self, approval_id: str, status: str) -> None:
        raw = self.r.hget(self.pending_key, approval_id)
        if raw:
            entry           = json.loads(raw)
            entry["status"] = status
            self.r.hset(self.pending_key, approval_id, json.dumps(entry))