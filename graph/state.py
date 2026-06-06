from typing import TypedDict, Optional


class APState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────
    invoice_path:    str
    raw_invoice:     str

    # ── Intake agent output ────────────────────────────────────────────
    invoice_data:    Optional[dict]   # extracted fields
    intake_flags:    Optional[list]   # injection / suspicious content flags

    # ── Matching agent output ──────────────────────────────────────────
    po_data:         Optional[dict]
    grn_data:        Optional[dict]
    match_result:    Optional[dict]   # matched: bool, discrepancies: list

    # ── Payment ────────────────────────────────────────────────────────
    payment_request: Optional[dict]
    approval_id:     Optional[str]
    approval_status: Optional[str]    # pending / approved / denied / completed

    # ── Final ──────────────────────────────────────────────────────────
    payment_result:  Optional[dict]
    error:           Optional[str]