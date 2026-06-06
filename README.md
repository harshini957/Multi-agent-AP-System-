# Multi-Agent Accounts Payable (AP) Maker-Checker System

A production-grade, security-first Accounts Payable automation pipeline built with **LangGraph**, **FastAPI**, and **Authsome** — demonstrating how multi-agent AI systems can enforce financial controls, detect prompt-injection attacks, and isolate credentials using a Policy Decision Point / Policy Enforcement Point (PDP/PEP) architecture.

---

## What This System Does

This system automates the end-to-end Accounts Payable invoice processing workflow using a chain of specialized AI agents. Each invoice travels through a structured pipeline — intake, validation, three-way matching, human approval, and payment — with every step independently audited and secured.

The project proves two key things simultaneously:

1. **Operational correctness** — a valid invoice navigates the full pipeline and executes payment automatically.
2. **Security robustness** — a malicious invoice embedding a prompt-injection attack is detected, flagged, and blocked before it can cause harm.

---

## Architecture Overview

```
Invoice (JSON)
     │
     ▼
┌────────────────────┐
│   Intake Agent     │  ← Scans for prompt injection / malicious payloads
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│   Parsing Agent    │  ← Extracts structured invoice data (vendor, amount, line items)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│   PO Lookup Agent  │  ← Fetches matching Purchase Order via MCP / mock service
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│   GRN Lookup Agent │  ← Fetches Goods Receipt Note to confirm delivery
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  3-Way Match Agent │  ← Validates Invoice ↔ PO ↔ GRN amounts & quantities
└────────┬───────────┘
         │ pass / fail
         ▼
┌────────────────────┐
│  Approval Gate     │  ← Human-in-the-loop checkpoint (CLI prompt)
└────────┬───────────┘
         │ approved / denied
         ▼
┌────────────────────┐
│  Payment Agent     │  ← Executes payment via mock payment service (port 8001)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│   Audit Logger     │  ← Writes immutable audit trail of all agent decisions
└────────────────────┘
```

The entire pipeline is orchestrated as a **LangGraph state machine** (`graph/build_graph.py`), where each node is a discrete agent function and edges encode conditional routing logic (e.g., skip payment if match failed, halt pipeline if injection detected).

---

## Key Technical Features

### 1. LangGraph State Machine Orchestration

The pipeline is modelled as a directed graph using LangGraph. Each agent is a node; the graph state is a typed `TypedDict` carrying all intermediate results:

```python
initial_state = {
    "invoice_path": invoice_path,
    "raw_invoice": raw_invoice,
    "invoice_data": None,
    "intake_flags": [],
    "po_data": None,
    "grn_data": None,
    "match_result": None,
    "payment_request": None,
    "approval_id": None,
    "approval_status": None,
    "payment_result": None,
    "error": None,
}
```

State is immutable between transitions — each node receives the full state and returns only its updates, making the pipeline deterministic and easy to debug.

### 2. PDP/PEP Credential Isolation

This is the most architecturally significant feature. Agents **never hold API keys directly**. Instead, credentials are provisioned into **Authsome** (running via Docker) and dispensed by a `CredentialBroker` only at the moment a tool call is authorized.

```
Agent requests credential
        │
        ▼
  CredentialBroker (PEP)
        │ asks: "is this agent allowed to use this credential?"
        ▼
  Authsome (PDP, port 7998)
        │ decision: permit / deny
        ▼
  Credential returned (or refused)
```

This pattern means that even if an agent were compromised by a prompt-injection attack and instructed to "call the payment API directly," it cannot — the credential would be denied by the PDP because the policy does not permit the intake agent to access the payment service.

Credentials are provisioned idempotently at startup:

```python
broker = CredentialBroker()
broker.provision("gmail", os.getenv("GMAIL_API_KEY", "mock-gmail-key"))
broker.provision("accounting_api", os.getenv("ACCOUNTING_API_KEY", ...))
broker.provision("payment_api", os.getenv("PAYMENT_API_KEY", ...))
broker.provision("resend", os.getenv("RESEND_API_KEY", ...))
```

### 3. Prompt Injection Detection

The **Intake Agent** runs before any business logic and scans the raw invoice payload for adversarial instructions. The fixture `fixtures/invoice_malicious.json` contains a deliberately crafted injection attack (e.g., instructions embedded in vendor fields designed to redirect payments or override agent behaviour).

The detection produces `intake_flags` — a list of human-readable descriptions of the suspicious content found. Downstream agents check this list and the graph routes to a hard-stop rather than continuing processing.

### 4. Three-Way Matching

A core AP control: the **3-Way Match Agent** compares three independent documents:

- **Invoice** — what the vendor claims was delivered and the amount owed
- **Purchase Order (PO)** — what the company agreed to buy
- **Goods Receipt Note (GRN)** — what was actually received

Discrepancies in amounts, quantities, or vendor identity surface as `discrepancies` in the match result and block payment. The matching logic operates on structured data extracted by the parsing agent, not on raw text, making it resistant to formatting tricks.

### 5. Human-in-the-Loop Approval Gate

After a successful three-way match, the pipeline pauses at `approval/gate.py`. The human operator is presented with the full invoice summary and discrepancy report (if any) and must explicitly approve or deny. This gate cannot be bypassed by agents — it is enforced by graph routing logic, not by an agent's own decision.

### 6. Mock Services for Local Development

Two `FastAPI` services run as daemon threads in the background:

- **Payment Service** (`mock_services/payment_server.py`) — port `8001`, simulates a payment gateway
- **Accounting Service** (`mock_services/accounting_server.py`) — port `8002`, simulates an ERP/ledger lookup

Both spin up automatically when `main.py` is executed, with a 1.5-second warm-up delay, so no external infrastructure is needed to run a full demo.

### 7. MCP Server Integration

The `mcp_servers/` directory exposes MCP (Model Context Protocol) endpoints, allowing LangChain/LangGraph agents to call tools — like PO lookup or GRN retrieval — using the standardized tool-use protocol. This makes the system straightforwardly extensible: replacing a mock MCP server with a real ERP connector requires only updating the server URL.

### 8. Structured Audit Logging

Every agent decision, flag, match result, approval action, and payment outcome is written to an append-only audit log (`audit/`). The `show_audit_log()` call at the end of each demo run prints the complete trail. In a production deployment, this log would be the basis for financial compliance reporting and fraud investigation.

---

## Repository Structure

```
Multi-agent-AP-System-/
├── main.py                    # Entrypoint — orchestrates demo acts
├── graph/
│   └── build_graph.py         # LangGraph pipeline definition
├── agents/                    # One module per agent
│   ├── intake_agent.py        # Prompt injection scanner
│   ├── parsing_agent.py       # Invoice parser
│   ├── po_agent.py            # Purchase Order lookup
│   ├── grn_agent.py           # Goods Receipt Note lookup
│   ├── match_agent.py         # Three-way match logic
│   └── payment_agent.py       # Payment execution
├── approval/
│   └── gate.py                # Human-in-the-loop checkpoint
├── audit/
│   └── view.py                # Audit log writer / viewer
├── auth/
│   └── credential_broker.py   # PEP — credential request handler
├── mcp_servers/               # MCP tool servers for agent tool calls
├── mock_services/
│   ├── payment_server.py      # FastAPI mock payment gateway (port 8001)
│   └── accounting_server.py   # FastAPI mock accounting ERP (port 8002)
├── providers/                 # LLM provider configuration
├── fixtures/
│   ├── invoice_valid.json     # Happy-path test invoice
│   └── invoice_malicious.json # Prompt injection attack invoice
├── docker-compose.yml         # Authsome PDP service
├── setup_credentials.py       # Credential provisioning utility
├── pyproject.toml
├── requirements.txt
└── .env                       # API keys (not committed)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM framework | LangChain, LangChain-OpenAI |
| HTTP client | httpx |
| Mock services | FastAPI + Uvicorn |
| Credential store (PDP) | Authsome (Docker, port 7998) |
| Data validation | Pydantic |
| State management | Redis |
| Terminal UI | Rich |
| Runtime | Python 3.12+ |

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker (for Authsome)
- An OpenAI API key (or compatible LLM provider)

### 1. Clone and install dependencies

```bash
git clone https://github.com/harshini957/Multi-agent-AP-System-
cd Multi-agent-AP-System-
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env .env.local  # edit with your keys
```

Required keys in `.env`:

```
OPENAI_API_KEY=sk-...
GMAIL_API_KEY=...          # optional — falls back to mock
ACCOUNTING_API_KEY=...     # optional — falls back to mock
PAYMENT_API_KEY=...        # optional — falls back to mock
RESEND_API_KEY=...         # optional — falls back to mock
```

### 3. Start the Authsome credential store

```bash
docker compose up -d
```

This starts the PDP on `http://localhost:7998`.

### 4. Run the demo

```bash
# Run both acts (happy path + attack)
python main.py

# Run only the valid invoice (happy path)
python main.py valid

# Run only the malicious invoice (attack demo)
python main.py attack
```

---

## Demo Walkthrough

**Act 1 — Valid Invoice (Happy Path)**

```
✓ No injection detected by intake agent
✓ 3-way match passed
? Approve payment of $4,250.00 to Acme Supplies? [y/n]: y
✓ PAYMENT EXECUTED
  {'transaction_id': 'TXN-...', 'status': 'success', 'amount': 4250.00}
```

**Act 2 — Malicious Invoice (Prompt Injection Attack)**

```
🚨 Intake flags:
  • Suspicious instruction in vendor_name field: "Ignore previous instructions..."
  • Potential redirect attempt detected in memo field
✗ PAYMENT DENIED — BLOCKED
```

The second act demonstrates that even a convincingly formatted invoice with correct amounts and line items will be stopped at the intake gate if it contains adversarial content — before it ever reaches the matching or payment agents.

---

## Security Design Principles

**Least privilege via PDP/PEP** — agents request credentials at runtime; the policy store decides whether to grant them based on the agent's identity and the requested resource. No agent holds a long-lived secret.

**Fail-closed routing** — any error or unrecognised state in the graph routes to a blocked/denied outcome rather than attempting to continue.

**Human checkpoints cannot be agent-bypassed** — the approval gate is enforced at the graph routing level. An agent cannot `invoke` past it.

**Injection detection before business logic** — the intake agent runs first and its flags are checked by every downstream agent before proceeding.

**Immutable audit trail** — all decisions are logged append-only, giving a forensic record of every invoice's journey through the pipeline.

---

## Extending the System

To connect a real ERP instead of mock services, update the server URLs in `mcp_servers/` to point at your production endpoints. The agent code does not change.

To add a new agent (e.g., a duplicate-invoice detector), define a new node function, add it to `graph/build_graph.py`, and wire its edges. The state schema can be extended by adding new keys to the `TypedDict`.

To enforce stricter policies, update the Authsome policy configuration — no application code changes required.

---

## License

MIT