from langgraph.graph import StateGraph, END
from graph.state import APState
from agents.intake_agent import run_intake
from agents.matching_agent import run_matching
from agents.payment_agent import prepare_payment, run_payment


def route_after_matching(state: APState) -> str:
    if state.get("error"):
        return "end"
    return "prepare_payment"


def route_after_payment(state: APState) -> str:
    status = state.get("approval_status")
    if status == "pending":
        return "end"       # pause — main.py drives the approval gate
    if status == "completed":
        return "end"
    return "end"           # denied or error


def build_graph():
    g = StateGraph(APState)

    g.add_node("intake",          run_intake)
    g.add_node("matching",        run_matching)
    g.add_node("prepare_payment", prepare_payment)
    g.add_node("payment",         run_payment)

    g.set_entry_point("intake")
    g.add_edge("intake", "matching")
    g.add_conditional_edges(
        "matching",
        route_after_matching,
        {"prepare_payment": "prepare_payment", "end": END},
    )
    g.add_edge("prepare_payment", "payment")
    g.add_conditional_edges(
        "payment",
        route_after_payment,
        {"end": END},
    )

    return g.compile()