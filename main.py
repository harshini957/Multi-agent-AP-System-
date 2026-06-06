"""
Main entrypoint — runs both demo acts.
Usage:
    python main.py          # runs both acts
    python main.py valid    # happy path only
    python main.py attack   # malicious invoice only
"""

import os
import sys
import time
import threading
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()


# ── Start mock servers in background threads ───────────────────────────

def _start_servers():
    import uvicorn
    from mock_services.payment_server   import app as pay_app
    from mock_services.accounting_server import app as acc_app

    threading.Thread(
        target=lambda: uvicorn.run(pay_app, host="0.0.0.0",
                                   port=8001, log_level="error"),
        daemon=True,
    ).start()
    threading.Thread(
        target=lambda: uvicorn.run(acc_app, host="0.0.0.0",
                                   port=8002, log_level="error"),
        daemon=True,
    ).start()
    time.sleep(1.5)
    console.print("[dim]  Mock servers ready — payment:8001  accounting:8002[/dim]")


# ── Run a single invoice through the full pipeline ─────────────────────

def run_demo(invoice_path: str, label: str) -> dict:
    from graph.build_graph import build_graph
    from approval.gate import request_human_approval
    from audit.view import show_audit_log

    console.print()
    console.print(Panel.fit(
        f"[bold]{label}[/bold]\nInvoice: {invoice_path}",
        border_style="blue",
    ))

    raw_invoice = Path(invoice_path).read_text(encoding="utf-8")

    initial_state = {
        "invoice_path":    invoice_path,
        "raw_invoice":     raw_invoice,
        "invoice_data":    None,
        "intake_flags":    [],
        "po_data":         None,
        "grn_data":        None,
        "match_result":    None,
        "payment_request": None,
        "approval_id":     None,
        "approval_status": None,
        "payment_result":  None,
        "error":           None,
    }

    graph  = build_graph()
    result = graph.invoke(initial_state)

    # ── Show intake flags ──────────────────────────────────────────────
    if result.get("intake_flags"):
        console.print("\n[bold red]🚨 Intake flags:[/bold red]")
        for flag in result["intake_flags"]:
            console.print(f"  [red]• {flag}[/red]")
    else:
        console.print("\n[green]✓ No injection detected by intake agent[/green]")

    # ── Show match result ──────────────────────────────────────────────
    match = result.get("match_result") or {}
    if match:
        if match.get("matched"):
            console.print("[green]✓ 3-way match passed[/green]")
        else:
            console.print("[red]✗ 3-way match FAILED[/red]")
            for d in match.get("discrepancies", []):
                console.print(f"  [red]• {d}[/red]")

    # ── Handle approval gate ───────────────────────────────────────────
    if result.get("approval_status") == "pending":
        result = request_human_approval(result)

    # ── Final outcome ──────────────────────────────────────────────────
    console.print()
    status = result.get("approval_status")
    if status == "approved":
        console.print(Panel.fit(
            "[green bold]✓ PAYMENT EXECUTED[/green bold]\n"
            f"  {result.get('payment_result', {})}",
            border_style="green",
        ))
    elif status == "denied":
        console.print(Panel.fit(
            "[red bold]✗ PAYMENT DENIED — BLOCKED[/red bold]",
            border_style="red",
        ))
    elif result.get("error"):
        console.print(f"[red]Error: {result['error']}[/red]")

    show_audit_log()
    return result


# ── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    from auth.credential_broker import CredentialBroker

    console.print(Panel.fit(
        "[bold]Multi-Agent AP Maker-Checker System[/bold]\n"
        "PDP + PEP credential isolation demo",
        border_style="cyan",
    ))

    # Provision credentials (idempotent — safe to run multiple times)
    broker = CredentialBroker()
    broker.provision("gmail",          os.getenv("GMAIL_API_KEY",      "mock-gmail-key"))
    broker.provision("accounting_api", os.getenv("ACCOUNTING_API_KEY", "mock-accounting-key"))
    broker.provision("payment_api",    os.getenv("PAYMENT_API_KEY",    "mock-payment-key-secret"))
    broker.provision("resend",         os.getenv("RESEND_API_KEY",     "mock-resend-key"))
    console.print("[dim]  Credentials provisioned[/dim]")

    _start_servers()

    demo = sys.argv[1] if len(sys.argv) > 1 else "both"

    if demo in ("valid", "both"):
        console.print("\n" + "═" * 60)
        console.print("[bold green]ACT 1 — Valid Invoice (happy path)[/bold green]")
        console.print("═" * 60)
        run_demo("fixtures/invoice_valid.json", "Valid Invoice")

    if demo in ("attack", "both"):
        console.print("\n" + "═" * 60)
        console.print("[bold red]ACT 2 — Malicious Invoice (prompt injection attack)[/bold red]")
        console.print("═" * 60)
        run_demo("fixtures/invoice_malicious.json",
                 "Malicious Invoice — Prompt Injection Attack")