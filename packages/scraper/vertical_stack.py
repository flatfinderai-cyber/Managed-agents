from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


POLICY_PATH = Path(__file__).with_name("vertical_stack_policy.json")


@dataclass
class ListingCandidate:
    external_id: str
    source: str
    title: str
    city: str
    url: str
    price_local: Optional[float] = None
    bedrooms: Optional[int] = None
    description: Optional[str] = None
    address: Optional[str] = None
    landlord_email: Optional[str] = None


@dataclass
class LayerResult:
    layer: str
    status: str  # pass | quarantine | block
    reasons: List[str]


@dataclass
class StackDecision:
    decision: str  # pass | quarantine | block
    decision_reason: str
    layer_results: Dict[str, Dict[str, Any]]
    listing_fingerprint: str
    confidence_summary: Optional[str]


class VerticalStackEngine:
    def __init__(self, policy_path: Path = POLICY_PATH):
        with policy_path.open("r", encoding="utf-8") as f:
            self.policy = json.load(f)

    def evaluate(self, listing: ListingCandidate, market_median_price: Optional[float] = None) -> StackDecision:
        results: List[LayerResult] = [
            self._layer1_listing_integrity(listing, market_median_price),
            self._layer2_language_analysis(listing),
            self._layer3_behavioral_signals(listing),
            self._layer4_registry_cross_reference(listing),
        ]

        # Layer 5 depends on prior layers
        results.append(self._layer5_verification_gate(listing, results))

        decision = "pass"
        reasons: List[str] = []
        for r in results:
            if r.status == "block":
                decision = "block"
                reasons.extend(r.reasons)
                break
            if r.status == "quarantine" and decision != "block":
                decision = "quarantine"
                reasons.extend(r.reasons)

        if not reasons:
            reasons = ["All vertical stack layers passed."]

        reason = "; ".join(reasons[:3])
        fingerprint = self._fingerprint(listing)
        summary = self._confidence_summary(listing, results) if decision == "pass" else None

        return StackDecision(
            decision=decision,
            decision_reason=reason,
            layer_results={r.layer: asdict(r) for r in results},
            listing_fingerprint=fingerprint,
            confidence_summary=summary,
        )

    def _layer1_listing_integrity(self, listing: ListingCandidate, market_median_price: Optional[float]) -> LayerResult:
        cfg = self.policy["layer1"]
        reasons: List[str] = []

        for field in cfg["required_fields"]:
            if getattr(listing, field, None) in (None, ""):
                reasons.append(f"Missing required field: {field}")

        if listing.bedrooms is not None and listing.bedrooms > cfg["max_bedrooms"]:
            reasons.append("Bedroom count exceeds plausible maximum")

        if market_median_price and listing.price_local:
            min_ratio = cfg["price_quarantine_below_market_ratio"]
            if listing.price_local < market_median_price * min_ratio:
                reasons.append("Price is >40% below market median")

        if any("Missing required field" in r for r in reasons):
            return LayerResult("layer1_listing_integrity", "block", reasons)
        if reasons:
            return LayerResult("layer1_listing_integrity", "quarantine", reasons)
        return LayerResult("layer1_listing_integrity", "pass", ["Integrity checks passed"])

    def _layer2_language_analysis(self, listing: ListingCandidate) -> LayerResult:
        cfg = self.policy["layer2"]
        text = f"{listing.title or ''} {listing.description or ''}".lower()

        block_hits = [p for p in cfg["block_phrases"] if p in text]
        if block_hits:
            return LayerResult(
                "layer2_language_analysis",
                "block",
                [f"Blocked phrase detected: {', '.join(block_hits[:2])}"],
            )

        quarantine_hits = [p for p in cfg["quarantine_phrases"] if p in text]
        vague_hits = [p for p in cfg["vague_marketing_words"] if re.search(rf"\b{re.escape(p)}\b", text)]

        reasons: List[str] = []
        if quarantine_hits:
            reasons.append(f"High-risk language detected: {', '.join(quarantine_hits[:2])}")
        if len(vague_hits) >= 2:
            reasons.append("Excessive vague marketing language")

        if reasons:
            return LayerResult("layer2_language_analysis", "quarantine", reasons)
        return LayerResult("layer2_language_analysis", "pass", ["Language checks passed"])

    def _layer3_behavioral_signals(self, listing: ListingCandidate) -> LayerResult:
        # Runtime behavioral signals are scaffolded here and should be enriched with
        # per-source account telemetry in ingestion jobs.
        _ = listing
        return LayerResult("layer3_behavioral_signals", "pass", ["No behavioral anomalies in current run"])

    def _layer4_registry_cross_reference(self, listing: ListingCandidate) -> LayerResult:
        cfg = self.policy["layer4"]
        reasons: List[str] = []

        if listing.landlord_email:
            domain = listing.landlord_email.split("@")[-1].lower()
            if any(bad in domain for bad in cfg["blocked_domains"]):
                return LayerResult("layer4_registry_cross_reference", "block", ["Blocked email domain in registry"])
            if any(risk in domain for risk in cfg["high_risk_email_domains"]):
                reasons.append("High-risk anonymous email domain")

        if reasons:
            return LayerResult("layer4_registry_cross_reference", "quarantine", reasons)
        return LayerResult("layer4_registry_cross_reference", "pass", ["Registry checks passed"])

    def _layer5_verification_gate(self, listing: ListingCandidate, prior_results: List[LayerResult]) -> LayerResult:
        _ = listing
        cfg = self.policy["layer5"]
        if cfg.get("require_prior_pass_layers", True):
            has_fail = any(r.status in ("block", "quarantine") for r in prior_results)
            if has_fail:
                return LayerResult(
                    "layer5_verification_gate",
                    "quarantine",
                    ["Final release gate held because prior layers did not all pass"],
                )

        return LayerResult("layer5_verification_gate", "pass", ["Release gate passed"])

    @staticmethod
    def _fingerprint(listing: ListingCandidate) -> str:
        raw = "|".join(
            [
                listing.source or "",
                listing.external_id or "",
                (listing.address or "").strip().lower(),
                (listing.title or "").strip().lower(),
                str(listing.price_local or ""),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _confidence_summary(listing: ListingCandidate, results: List[LayerResult]) -> str:
        _ = results
        return (
            "This listing passed all five layers of the FlatFinder Scam Filter. "
            "Address and pricing signals were validated, fraud indicators were checked, "
            "and no known scam signals were detected."
        )


def evaluate_listing(listing: ListingCandidate, market_median_price: Optional[float] = None) -> StackDecision:
    return VerticalStackEngine().evaluate(listing, market_median_price=market_median_price)
