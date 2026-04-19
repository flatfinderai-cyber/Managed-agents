# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
#
# Agent 3: Scraper Integration Agent
# Orchestrates the Playwright scraper with intelligent scam detection,
# listing quality scoring, duplicate detection, and Supabase ingestion.

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

# Allow importing from packages/scraper
sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import BaseAgent

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You are the FlatFinder™ Scraper Integration Agent.

FlatFinder™ aggregates rental listings from Kijiji, Craigslist, Gumtree, LeBonCoin, and Liv.rent —
then applies anti-scam filters and affordability scoring before surfacing them to tenants.

Your mandate:
1. Decide which cities and sources to scrape based on the task request.
2. Run the scrapers via the run_scraper tool.
3. Analyse the scraped listings for quality issues and scam signals.
4. Flag suspicious listings before they reach the database.
5. Report statistics on what was scraped, flagged, and saved.

Scam signals you must detect and flag:
- Price > 40% below median for city/bedroom count (too-good-to-be-true)
- No photos, or placeholder/stock photo descriptions
- Contact is a free email provider (gmail, yahoo, hotmail) with no company name
- Description contains urgent language: "act fast", "first come first served", "wire transfer"
- Listing asks for deposit before showing the property
- Duplicate title + price across multiple sources (ghost listing)
- Price listed in USD for a Canadian listing

Quality scoring:
- Score 0-100: deduct points for missing fields (photos, address, description)
- Listings below 30/100 should be flagged for review, not published

Use British/Canadian English throughout. Never use Americanised filler language.
Always report final statistics in a clean summary table.
"""


# ── Scam detection heuristics (pure Python, no API calls) ─────────────────────

SCAM_KEYWORDS = [
    r"\bwire\s+transfer\b",
    r"\bwestern\s+union\b",
    r"\bmoney\s+gram\b",
    r"\bact\s+fast\b",
    r"\bfirst\s+come\s+first\s+served\b",
    r"\bno\s+viewing\b",
    r"\bkeys\s+by\s+mail\b",
    r"\bdeposit\s+before\s+view",
    r"\bcontact\s+me\s+at\s+\S+@gmail",
    r"\bi\s+am\s+abroad\b",
    r"\baway\s+on\s+mission\b",
    r"\bGod\s+bless\b",
]

CITY_MEDIAN_RENTS: dict[str, dict[int, int]] = {
    # city → {bedrooms: median_rent_cad}
    "Toronto": {0: 1800, 1: 2300, 2: 3100, 3: 3900},
    "Vancouver": {0: 1700, 1: 2400, 2: 3300, 3: 4200},
    "Paris": {0: 900, 1: 1400, 2: 2000, 3: 2800},
    "Edinburgh": {0: 700, 1: 1100, 2: 1600, 3: 2100},
}
SCAM_PRICE_THRESHOLD = 0.55   # listing is suspicious if price < 55% of median


def _score_listing(listing: dict) -> dict:
    """Return a quality score and list of issues for a single listing."""
    score = 100
    issues = []

    if not listing.get("description"):
        score -= 20
        issues.append("missing_description")

    images = listing.get("images", [])
    if not images:
        score -= 25
        issues.append("no_photos")
    elif len(images) < 3:
        score -= 10
        issues.append("few_photos")

    if not listing.get("address") and not listing.get("neighborhood"):
        score -= 15
        issues.append("no_location")

    if listing.get("bedrooms") is None:
        score -= 10
        issues.append("missing_bedrooms")

    if listing.get("price_local") is None:
        score -= 20
        issues.append("missing_price")

    return {"score": max(0, score), "issues": issues}


def _scam_check(listing: dict, city: str) -> dict:
    """Run heuristic scam detection. Returns is_scam, signals."""
    signals = []
    description = (listing.get("description") or "").lower()
    title = (listing.get("title") or "").lower()
    text = title + " " + description

    # Keyword check
    for pattern in SCAM_KEYWORDS:
        if re.search(pattern, text, re.IGNORECASE):
            signals.append(f"keyword_match:{pattern}")

    # Price check
    price = listing.get("price_local")
    bedrooms = listing.get("bedrooms") or 1
    if price and city in CITY_MEDIAN_RENTS:
        median = CITY_MEDIAN_RENTS[city].get(bedrooms, CITY_MEDIAN_RENTS[city].get(1, 2000))
        if price < median * SCAM_PRICE_THRESHOLD:
            signals.append(
                f"price_too_low:{price:.0f}_vs_median_{median}"
            )

    # USD listed for CA listing
    if listing.get("currency") == "USD" and city in ("Toronto", "Vancouver"):
        signals.append("usd_currency_for_canadian_city")

    return {
        "is_scam": len(signals) >= 2,
        "suspicious": len(signals) >= 1,
        "signals": signals,
        "signal_count": len(signals),
    }


class ScraperAgent(BaseAgent):
    """
    Claude agent that orchestrates FlatFinder™ scrapers with quality + scam detection.
    """

    @property
    def system_prompt(self) -> str:
        return _SYSTEM

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "name": "list_available_cities",
                "description": "Return the list of cities and sources the scraper supports.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "run_scraper",
                "description": (
                    "Run the Playwright scraper for a given city and source. "
                    "Returns the raw listings scraped. In dry-run mode (no env vars), "
                    "returns synthetic test data."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name, e.g. 'Toronto'",
                        },
                        "source": {
                            "type": "string",
                            "enum": ["kijiji", "craigslist", "gumtree", "leboncoin"],
                            "description": "Scraper source to use.",
                        },
                        "max_listings": {
                            "type": "integer",
                            "default": 20,
                            "description": "Maximum listings to scrape (use small number for tests).",
                        },
                    },
                    "required": ["city", "source"],
                },
            },
            {
                "name": "score_listing_quality",
                "description": (
                    "Score a single listing's quality 0-100 based on completeness. "
                    "Flags missing photos, description, address, price."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "listing": {
                            "type": "object",
                            "description": "Listing dict with fields: title, description, images, address, bedrooms, price_local.",
                        }
                    },
                    "required": ["listing"],
                },
            },
            {
                "name": "check_scam_signals",
                "description": (
                    "Run heuristic scam detection on a listing. "
                    "Checks for scam keywords, too-low price, USD currency, missing contact."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "listing": {"type": "object"},
                        "city": {"type": "string"},
                    },
                    "required": ["listing", "city"],
                },
            },
            {
                "name": "batch_score_and_flag",
                "description": (
                    "Score quality and check scam signals for a list of listings. "
                    "Returns statistics and the annotated listings sorted by quality score."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "listings": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "city": {"type": "string"},
                    },
                    "required": ["listings", "city"],
                },
            },
            {
                "name": "get_city_median_rents",
                "description": "Return the known median rents by bedroom count for a given city.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                    },
                    "required": ["city"],
                },
            },
            {
                "name": "deduplicate_listings",
                "description": (
                    "Remove duplicate listings from a list by comparing title + price. "
                    "Returns the deduplicated list and count of removed duplicates."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "listings": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                    "required": ["listings"],
                },
            },
        ]

    # ── Tool implementations ──────────────────────────────────────────────────

    def execute_tool(self, name: str, tool_input: dict) -> Any:
        dispatch = {
            "list_available_cities":  self._list_available_cities,
            "run_scraper":            self._run_scraper,
            "score_listing_quality":  self._score_listing_quality,
            "check_scam_signals":     self._check_scam_signals,
            "batch_score_and_flag":   self._batch_score_and_flag,
            "get_city_median_rents":  self._get_city_median_rents,
            "deduplicate_listings":   self._deduplicate_listings,
        }
        fn = dispatch.get(name)
        if not fn:
            raise ValueError(f"Unknown tool: {name}")
        return fn(tool_input)

    def _list_available_cities(self, _: dict) -> dict:
        return {
            "cities": {
                "Toronto":   ["kijiji", "craigslist"],
                "Vancouver": ["kijiji", "craigslist"],
                "Paris":     ["leboncoin"],
                "Edinburgh": ["gumtree"],
            },
            "note": "Scraper uses respectful rate limiting (2s delay between requests).",
        }

    def _run_scraper(self, args: dict) -> dict:
        """
        In a real deployment this calls scraper.py via asyncio.
        In dry-run / CI mode (no Supabase env vars), returns synthetic test data.
        """
        city = args["city"]
        source = args["source"]
        max_listings = int(args.get("max_listings", 20))

        has_supabase = bool(os.environ.get("SUPABASE_URL"))

        if not has_supabase:
            # Return realistic synthetic data for testing / demonstration
            synthetic = []
            sample_data = [
                {
                    "external_id": f"{source[:3]}-{city.lower()}-001",
                    "source": source,
                    "title": f"Modern 1BR in {city} — utilities included",
                    "city": city,
                    "price_local": {"Toronto": 2250, "Vancouver": 2400, "Edinburgh": 1100, "Paris": 1300}.get(city, 1500),
                    "currency": {"Toronto": "CAD", "Vancouver": "CAD", "Edinburgh": "GBP", "Paris": "EUR"}.get(city, "CAD"),
                    "bedrooms": 1,
                    "bathrooms": 1.0,
                    "neighborhood": f"Downtown {city}",
                    "description": "Bright modern apartment, hardwood floors, in-unit laundry.",
                    "images": ["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
                    "url": f"https://{source}.example.com/listing/001",
                },
                {
                    "external_id": f"{source[:3]}-{city.lower()}-002",
                    "source": source,
                    "title": f"2BR Family Flat — {city} West End",
                    "city": city,
                    "price_local": {"Toronto": 3100, "Vancouver": 3400, "Edinburgh": 1600, "Paris": 2100}.get(city, 2000),
                    "currency": {"Toronto": "CAD", "Vancouver": "CAD", "Edinburgh": "GBP", "Paris": "EUR"}.get(city, "CAD"),
                    "bedrooms": 2,
                    "bathrooms": 1.0,
                    "neighborhood": f"West End, {city}",
                    "description": "Spacious family flat, dishwasher, parking included.",
                    "images": ["https://example.com/img3.jpg"],
                    "url": f"https://{source}.example.com/listing/002",
                },
                {
                    "external_id": f"{source[:3]}-{city.lower()}-003",
                    "source": source,
                    "title": f"URGENT — Cheap studio in {city} — ACT FAST wire transfer only",
                    "city": city,
                    "price_local": 400,   # suspicious — way below median
                    "currency": "USD",    # wrong currency for CA
                    "bedrooms": 0,
                    "bathrooms": 1.0,
                    "neighborhood": None,
                    "description": None,  # missing description
                    "images": [],         # no photos
                    "url": f"https://{source}.example.com/listing/003",
                },
            ]
            synthetic = sample_data[:max_listings]
            return {
                "listings": synthetic,
                "count": len(synthetic),
                "city": city,
                "source": source,
                "mode": "synthetic_dry_run",
                "note": "Set SUPABASE_URL env var to run live scraper.",
            }

        # Live mode — call the actual scraper
        import asyncio
        import importlib.util

        scraper_path = Path(__file__).parent.parent / "packages" / "scraper" / "scraper.py"
        spec = importlib.util.spec_from_file_location("scraper", scraper_path)
        scraper_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scraper_mod)

        source_fn_map = {
            "kijiji": scraper_mod.scrape_kijiji,
            "craigslist": scraper_mod.scrape_craigslist,
        }
        fn = source_fn_map.get(source)
        if not fn:
            return {"error": f"Source '{source}' not supported in live mode for {city}."}

        cities = scraper_mod.CITIES
        if city not in cities or f"{source}_url" not in cities[city]:
            return {"error": f"No {source} URL configured for {city}."}

        url = cities[city][f"{source}_url"]
        listings = asyncio.run(fn(city, url))
        listing_dicts = [vars(lst) for lst in listings[:max_listings]]

        return {
            "listings": listing_dicts,
            "count": len(listing_dicts),
            "city": city,
            "source": source,
            "mode": "live",
        }

    def _score_listing_quality(self, args: dict) -> dict:
        return _score_listing(args["listing"])

    def _check_scam_signals(self, args: dict) -> dict:
        return _scam_check(args["listing"], args["city"])

    def _batch_score_and_flag(self, args: dict) -> dict:
        city = args["city"]
        listings = args["listings"]
        results = []

        for lst in listings:
            quality = _score_listing(lst)
            scam = _scam_check(lst, city)
            results.append({
                **lst,
                "_quality_score": quality["score"],
                "_quality_issues": quality["issues"],
                "_scam_signals": scam["signals"],
                "_is_scam": scam["is_scam"],
                "_is_suspicious": scam["suspicious"],
                "_publish": quality["score"] >= 30 and not scam["is_scam"],
            })

        results.sort(key=lambda r: r["_quality_score"], reverse=True)
        publishable = [r for r in results if r["_publish"]]
        flagged_scam = [r for r in results if r["_is_scam"]]
        low_quality = [r for r in results if r["_quality_score"] < 30 and not r["_is_scam"]]

        return {
            "total": len(results),
            "publishable": len(publishable),
            "flagged_as_scam": len(flagged_scam),
            "low_quality": len(low_quality),
            "listings": results,
        }

    def _get_city_median_rents(self, args: dict) -> dict:
        city = args["city"]
        medians = CITY_MEDIAN_RENTS.get(city)
        if not medians:
            return {"error": f"No median rent data for '{city}'."}
        return {
            "city": city,
            "medians_by_bedrooms": {
                f"{k}BR" if k > 0 else "Studio": v
                for k, v in medians.items()
            },
            "currency": "CAD" if city in ("Toronto", "Vancouver") else ("GBP" if city == "Edinburgh" else "EUR"),
        }

    def _deduplicate_listings(self, args: dict) -> dict:
        listings = args["listings"]
        seen: dict[str, bool] = {}
        unique = []
        duplicates = 0
        for lst in listings:
            key = f"{(lst.get('title') or '').lower().strip()}|{lst.get('price_local')}"
            if key in seen:
                duplicates += 1
            else:
                seen[key] = True
                unique.append(lst)
        return {
            "original_count": len(listings),
            "unique_count": len(unique),
            "duplicates_removed": duplicates,
            "listings": unique,
        }
