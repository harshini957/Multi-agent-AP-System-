"""
Human-in-the-loop approval gate.
This is YOUR novel contribution — AuthSome has no equivalent.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from auth.authsome_clients import get_payment_headers
from auth.pep import PolicyEnforcementPoint
from agents.payment_agent import _call_payment_api

console = Console()
pep     = PolicyEnforcementPoint()


def _show_panel(state: dict) -> None:
    invoice = state.get("invoice_data", {})
    match   = state.get("match_result", {})
    req     = state.get("payment_request", {})
    flags   = state.get("intake_flags", [])

    console.print()
    console.print(Panel.fit(
        "[bold yellow]⚠  PAYMENT APPROVAL REQUIRED[/bold yellow]",
        border_style="yellow",
    ))

    t = Table(box=box.ROUNDED, show_header=False)
    t.add_column("Field", style="dim", width=22)
    t.add_column("Value", style="bold")

    t.add_row("Invoice",      invoice.get("invoice_number", ""))
    t.add_row("Vendor",       invoice.get("vendor", ""))
    t.add_row("Amount",       f"₹{req.get('amount', 0):,.2f}")
    t.add_row("Payee Account", req.get("payee", ""))
    t.add_row("PO Match",
              "[green]✓ Matched[/green]"
              if match.get("matched")
              else "[red]✗ MISMATCH[/red]")

    for d in match.get("discrepancies", []):
        t.add_row("⚠ Discrepancy", f"[red]{d}[/red]")

    for f in flags:
        t.add_row("🚨 Security Flag", f"[bold red]{f}[/bold red]")

    console.print(t)


def request_human_approval(state: dict) -> dict:
    """
    Display payment details to the human operator and ask approve/deny.
    On approval: fetches payment credentials and calls the payment API.
    On denial: marks the approval as denied, payment is cancelled.
    """
    _show_panel(state)

    console.print()
    console.print("[bold]Approve this payment? (yes / no): [/bold]", end="")
    answer = input().strip().lower()

    if answer in ("yes", "y"):
        console.print("\n[green]✓ Approved — executing payment...[/green]")

        try:
            # Fetch payment credential directly (human has approved)
            auth_headers = get_payment_headers("payment_api")
            result = _call_payment_api(
                amount=state["payment_request"]["amount"],
                payee=state["payment_request"]["payee"],
                reference=state["payment_request"]["reference"],
                auth_headers=auth_headers,
            )
            pep.mark_approved(state["approval_id"])
            return {
                **state,
                "approval_status": "approved",
                "payment_result":  result,
            }
        except Exception as e:
            console.print(f"[red]Payment failed: {e}[/red]")
            return {**state, "approval_status": "denied", "error": str(e)}

    else:
        console.print("\n[red]✗ Denied — payment cancelled.[/red]")
        pep.mark_denied(state["approval_id"])
        return {**state, "approval_status": "denied"}