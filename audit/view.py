"""
Audit viewer — shows the PDP decision log and credential access log.
"""

import datetime
from rich.console import Console
from rich.table import Table
from rich import box

from auth.pdp import PolicyDecisionPoint
from auth.credential_broker import CredentialBroker

console = Console()


def show_audit_log() -> None:
    pdp    = PolicyDecisionPoint()
    broker = CredentialBroker()

    # ── PDP decisions ──────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]═══ PDP Decision Log ═══[/bold cyan]")

    t = Table(box=box.ROUNDED)
    t.add_column("Time",     style="dim")
    t.add_column("Agent",    style="bold", width=12)
    t.add_column("Provider", width=16)
    t.add_column("Action",   width=7)
    t.add_column("Decision", width=20)
    t.add_column("Reason",   style="dim")

    decision_style = {
        "allow":            "[green]ALLOW[/green]",
        "deny":             "[red]DENY[/red]",
        "require_approval": "[yellow]REQUIRE APPROVAL[/yellow]",
    }

    for entry in pdp.get_audit_log():
        ts  = datetime.datetime.fromtimestamp(
                  entry["timestamp"]).strftime("%H:%M:%S")
        dec = decision_style.get(entry["decision"], entry["decision"])
        t.add_row(
            ts,
            entry["agent"],
            entry["provider"],
            entry["action"],
            dec,
            entry["reason"][:55],
        )
    console.print(t)

    # ── Credential access log ──────────────────────────────────────────
    console.print()
    console.print("[bold cyan]═══ Credential Access Log ═══[/bold cyan]")

    t2 = Table(box=box.ROUNDED)
    t2.add_column("Time",     style="dim")
    t2.add_column("Agent",    style="bold", width=12)
    t2.add_column("Provider", width=16)
    t2.add_column("Result",   width=16)

    for entry in broker.get_audit_log():
        ts  = datetime.datetime.fromtimestamp(
                  entry["timestamp"]).strftime("%H:%M:%S")
        res = ("[green]✓ GRANTED[/green]"
               if entry["action"] == "granted"
               else "[red]✗ DENIED[/red]")
        t2.add_row(ts, entry["agent"], entry["provider"], res)
    console.print(t2)