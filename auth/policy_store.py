from enum import Enum


class Decision(Enum):
    ALLOW            = "allow"
    DENY             = "deny"
    REQUIRE_APPROVAL = "require_approval"


# Policy rules: (agent, provider, action) -> Decision
# action is "read" or "write"
# Deny-by-default: anything not listed is automatically DENY.
POLICIES: dict[tuple[str, str, str], Decision] = {
    # Intake agent: read-only on gmail. Cannot touch payment or accounting write.
    ("intake",   "gmail",          "read"):  Decision.ALLOW,
    ("intake",   "gmail",          "write"): Decision.DENY,

    # Matching agent: read-only on accounting. Cannot touch payment.
    ("matching", "accounting_api", "read"):  Decision.ALLOW,
    ("matching", "accounting_api", "write"): Decision.DENY,

    # Payment agent: read on payment, write requires human approval.
    # This is the ONLY identity that can reach payment_api.
    ("payment",  "payment_api",    "read"):  Decision.ALLOW,
    ("payment",  "payment_api",    "write"): Decision.REQUIRE_APPROVAL,
    ("payment",  "resend",         "write"): Decision.REQUIRE_APPROVAL,
}


def get_decision(agent: str, provider: str, action: str) -> Decision:
    """
    Return the policy decision for (agent, provider, action).
    Defaults to DENY for anything not explicitly listed.
    """
    return POLICIES.get((agent, provider, action), Decision.DENY)