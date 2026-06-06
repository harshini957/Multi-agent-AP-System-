import json
import time
import redis
from dataclasses import dataclass


class CredentialDeniedError(Exception):
    """Raised when an agent requests a credential it is not allowed to hold."""
    pass


class CredentialMissingError(Exception):
    """Raised when a credential has not been provisioned yet."""
    pass


# Per-agent allow-list. Only payment can access payment_api.
AGENT_POLICY: dict[str, list[str]] = {
    "intake":   ["gmail"],
    "matching": ["accounting_api"],
    "payment":  ["payment_api", "resend"],
}


class CredentialBroker:
    """
    Per-agent credential store backed by Redis.
    Enforces least-privilege: each agent can only retrieve
    credentials listed in AGENT_POLICY for that agent.
    Mirrors the AuthSome identity/vault model.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r         = redis.from_url(redis_url)
        self.audit_key = "ap:cred_audit"

    # ------------------------------------------------------------------
    # Provisioning — run once at setup (equivalent to authsome login)
    # ------------------------------------------------------------------

    def provision(self, provider: str, api_key: str) -> None:
        """Store a credential. Called during setup, never by agents."""
        self.r.set(f"ap:creds:{provider}", api_key)

    # ------------------------------------------------------------------
    # Credential retrieval — called by agent tools via PEP
    # ------------------------------------------------------------------

    def get_headers(self, agent: str, provider: str) -> dict:
        """
        Return auth headers for provider if agent is allowed.
        Raises CredentialDeniedError if agent's policy doesn't cover provider.
        This is enforcement at the credential layer, not the prompt layer.
        """
        allowed = AGENT_POLICY.get(agent, [])

        if provider not in allowed:
            self._audit(agent, provider, "denied",
                        f"'{agent}' not in allow-list for '{provider}'")
            raise CredentialDeniedError(
                f"Agent '{agent}' is NOT allowed to access '{provider}'. "
                f"Allowed: {allowed}"
            )

        raw = self.r.get(f"ap:creds:{provider}")
        if not raw:
            raise CredentialMissingError(
                f"No credential provisioned for '{provider}'. "
                "Run setup_credentials.py first."
            )

        self._audit(agent, provider, "granted", "policy check passed")
        return {"Authorization": f"Bearer {raw.decode()}"}

    def get_token(self, agent: str, provider: str) -> str:
        headers = self.get_headers(agent, provider)
        return headers["Authorization"].replace("Bearer ", "")

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def _audit(self, agent: str, provider: str,
               action: str, reason: str) -> None:
        entry = {
            "timestamp": time.time(),
            "agent":     agent,
            "provider":  provider,
            "action":    action,
            "reason":    reason,
        }
        self.r.rpush(self.audit_key, json.dumps(entry))

    def get_audit_log(self) -> list:
        return [
            json.loads(e)
            for e in self.r.lrange(self.audit_key, 0, -1)
        ]

    def clear(self) -> None:
        self.r.delete(self.audit_key)