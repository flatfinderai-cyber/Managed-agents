# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
"""
Persist vertical-stack evaluation rows after listings upsert — shared by all DB ingress paths.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Tuple

from vertical_stack import StackDecision

RawListingTuple = Tuple[Any, StackDecision, Any]


def record_vertical_stack_decisions(
    supabase,
    evaluated: Iterable[RawListingTuple],
    upsert_listing_rows: List[dict],
) -> None:
    """
    After `listings` upsert, write `listing_stack_decisions` + append-only events.

    :param supabase: Supabase client
    :param evaluated: same (raw, decision, market_median) tuples used to build listing rows
    :param upsert_listing_rows: `result.data` from listings upsert (needs id, external_id, source)
    """
    listing_map = {
        (row.get("external_id"), row.get("source")): row.get("id")
        for row in upsert_listing_rows
        if row.get("external_id") and row.get("source") and row.get("id")
    }

    decision_rows: list[dict] = []
    for raw, decision, _market_median in evaluated:
        listing_id = listing_map.get((raw.external_id, raw.source))
        if not listing_id:
            continue
        decision_rows.append({
            "listing_id": listing_id,
            "decision": decision.decision,
            "decision_reason": decision.decision_reason,
            "layer_results": decision.layer_results,
            "listing_fingerprint": decision.listing_fingerprint,
            "confidence_summary": decision.confidence_summary,
        })

    if not decision_rows:
        return

    supabase.table("listing_stack_decisions").upsert(
        decision_rows,
        on_conflict="listing_id",
    ).execute()

    supabase.table("listing_stack_decision_events").insert(decision_rows).execute()
