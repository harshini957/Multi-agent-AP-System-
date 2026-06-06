import json
import time
import redis
from auth.policy_store import Decision, get_decision


class PDPRequest:
    def __init__(self, agent: str, provider: str,
                 action: str, context: dict = None):
        self.agent    = agent
        self.provider = provider
        self.action   = action
        self.context  = context or {}


class PDPResponse:
    def __init__(self, decision: Decision, reason: str,
                 request: PDPRequest):
        self.decision = decision
        self.reason   = reason
        self.request  = request

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.ALLOW

    @property
    def needs_approval(self) -> bool:
        return self.decision == Decision.REQUIRE_APPROVAL

    @property
    def denied(self) -> bool:
        return self.decision == Decision.DENY


class PolicyDecisionPoint:
    """
    Evaluates access requests against the policy store.
    Returns a PDPResponse — never executes anything itself.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r         = redis.from_url(redis_url)
        self.audit_key = "ap:pdp_audit"

    def evaluate(self, request: PDPRequest) -> PDPResponse:
        decision = get_decision(
            request.agent,
            request.provider,
            request.action,
        )

        reasons = {
            Decision.ALLOW:            "policy permits this agent/provider/action",
            Decision.DENY:             (
                f"'{request.agent}' has no policy entry for "
                f"'{request.action}' on '{request.provider}' — default DENY"
            ),
            Decision.REQUIRE_APPROVAL: "write action requires human approval",
        }

        response = PDPResponse(
            decision=decision,
            reason=reasons[decision],
            request=request,
        )
        self._log(response)
        return response

    def _log(self, response: PDPResponse) -> None:
        entry = {
            "timestamp": time.time(),
            "agent":     response.request.agent,
            "provider":  response.request.provider,
            "action":    response.request.action,
            "decision":  response.decision.value,
            "reason":    response.reason,
        }
        self.r.rpush(self.audit_key, json.dumps(entry))

    def get_audit_log(self) -> list:
        return [
            json.loads(e)
            for e in self.r.lrange(self.audit_key, 0, -1)
        ]

    def clear(self) -> None:
        self.r.delete(self.audit_key)