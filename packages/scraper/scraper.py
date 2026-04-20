# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Confidential & Proprietary Intellectual Property
# Canadian Corporation | Canadian Kind, Scottish Strong
#
# FlatFinder™ Python Scraper — Playwright-based
# Sources: Kijiji, Craigslist, Liv.rent, LeBonCoin (Paris), Gumtree (Edinburgh)

import asyncio
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright
from supabase import create_client

from vertical_stack import ListingCandidate, evaluate_listing
from browser_use_fallback import BrowserUseFallbackAgent

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

DELAY_MS = int(os.environ.get("SCRAPER_DELAY_MS", "2000"))
MAX_LISTINGS = int(os.environ.get("SCRAPER_MAX_LISTINGS", "200"))
ENABLE_BROWSER_USE_FALLBACK = os.environ.get("SCRAPER_ENABLE_BROWSER_USE_FALLBACK", "false").lower() == "true"

CITIES = {
    "Toronto": {
        "country": "CA",
        "currency": "CAD",
        "kijiji_url": "https://www.kijiji.ca/b-apartments-condos/city-of-toronto/c37l1700273",
        "craigslist_url": "https://toronto.craigslist.org/search/apa",
    },
    "Vancouver": {
        "country": "CA",
        "currency": "CAD",
        "kijiji_url": "https://www.kijiji.ca/b-apartments-condos/vancouver/c37l1700287",
        "craigslist_url": "https://vancouver.craigslist.org/search/apa",
    },
    "Paris": {
        "country": "FR",
        "currency": "EUR",
        "leboncoin_url": "https://www.leboncoin.fr/annonces/offres/ile_de_france/",
    },
    "Edinburgh": {
        "country": "GB",
        "currency": "GBP",
        "gumtree_url": "https://www.gumtree.com/flats-houses/edinburgh",
    },
}


@dataclass
class RawListing:
    external_id: str
    source: str
    title: str
    city: str
    url: str
    price_local: Optional[float] = None
    currency: str = "CAD"
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    address: Optional[str] = None
    neighborhood: Optional[str] = None
    description: Optional[str] = None
    images: list = field(default_factory=list)
    agent_name: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def normalize_price_to_cents(price: Optional[float]) -> Optional[int]:
    if price is None:
        return None
    return int(price * 100)


def get_market_median_price(city: str, source: str) -> Optional[float]:
    """
    Returns median monthly rent (local currency) for active listings in source+city.
    Falls back to city-only median if source-specific has no data.
    """
    try:
        source_rows = (
            supabase.table("listings")
            .select("price")
            .eq("city", city)
            .eq("source", source)
            .eq("is_active", True)
            .not_.is_("price", "null")
            .limit(400)
            .execute()
        )
        rows = source_rows.data or []

        if not rows:
            city_rows = (
                supabase.table("listings")
                .select("price")
                .eq("city", city)
                .eq("is_active", True)
                .not_.is_("price", "null")
                .limit(800)
                .execute()
            )
            rows = city_rows.data or []

        prices = sorted((r["price"] / 100.0) for r in rows if r.get("price") is not None)
        if not prices:
            return None

        mid = len(prices) // 2
        if len(prices) % 2 == 0:
            return (prices[mid - 1] + prices[mid]) / 2
        return prices[mid]
    except Exception:
        return None


async def scrape_kijiji(city: str, page_url: str) -> list[RawListing]:
    """Scrape Kijiji apartment listings for a given city."""
    listings = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (compatible; FlatFinderBot/2.0; +https://flatfinder.ca/bot)"
        })

        try:
            await page.goto(page_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(DELAY_MS / 1000)

            cards = await page.query_selector_all('[data-testid="listing-card"]')

            for card in cards[:MAX_LISTINGS]:
                try:
                    title_el = await card.query_selector("a[class*='title']")
                    price_el = await card.query_selector("[class*='price']")
                    location_el = await card.query_selector("[class*='location']")
                    href_el = await card.query_selector("a")

                    title = await title_el.inner_text() if title_el else "Untitled"
                    price_text = await price_el.inner_text() if price_el else ""
                    location = await location_el.inner_text() if location_el else ""
                    href = await href_el.get_attribute("href") if href_el else ""

                    price_num = None
                    if price_text:
                        nums = re.findall(r"[\d,]+", price_text.replace(",", ""))
                        if nums:
                            price_num = float(nums[0])

                    url = href if href.startswith("http") else f"https://www.kijiji.ca{href}"
                    external_id = f"kij-{city.lower()}-{abs(hash(url))}"

                    listings.append(RawListing(
                        external_id=external_id,
                        source="kijiji",
                        title=title.strip(),
                        city=city,
                        url=url,
                        price_local=price_num,
                        currency=CITIES[city]["currency"],
                        neighborhood=location.strip() or None,
                    ))
                except Exception:
                    continue

        finally:
            await browser.close()

    return listings


async def scrape_craigslist(city: str, page_url: str) -> list[RawListing]:
    """Scrape Craigslist apartment listings."""
    listings = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (compatible; FlatFinderBot/2.0; +https://flatfinder.ca/bot)"
        })

        try:
            await page.goto(page_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(DELAY_MS / 1000)

            items = await page.query_selector_all(".result-row")

            for item in items[:MAX_LISTINGS]:
                try:
                    title_el = await item.query_selector(".result-title")
                    price_el = await item.query_selector(".result-price")
                    hood_el = await item.query_selector(".result-hood")

                    title = await title_el.inner_text() if title_el else "Untitled"
                    href = await title_el.get_attribute("href") if title_el else ""
                    price_text = await price_el.inner_text() if price_el else ""
                    hood = await hood_el.inner_text() if hood_el else ""

                    price_num = None
                    if price_text:
                        nums = re.findall(r"\d+", price_text.replace(",", ""))
                        if nums:
                            price_num = float(nums[0])

                    external_id = f"cl-{city.lower()}-{abs(hash(href))}"

                    listings.append(RawListing(
                        external_id=external_id,
                        source="craigslist",
                        title=title.strip(),
                        city=city,
                        url=href,
                        price_local=price_num,
                        currency=CITIES[city]["currency"],
                        neighborhood=hood.strip("() ") or None,
                    ))
                except Exception:
                    continue

        finally:
            await browser.close()

    return listings


async def run_browser_use_fallback(source: str, city: str, page_url: str) -> list[RawListing]:
    """Fallback browser-use collection for dynamic pages."""
    agent = BrowserUseFallbackAgent(delay_ms=DELAY_MS, max_listings=min(MAX_LISTINGS, 50))
    collected = await agent.collect(source=source, city=city, page_url=page_url)
    return [
        RawListing(
            external_id=i.external_id,
            source=i.source,
            title=i.title,
            city=i.city,
            url=i.url,
            price_local=i.price_local,
            currency=CITIES.get(city, {}).get("currency", "CAD"),
            description=i.description,
            neighborhood=i.neighborhood,
        )
        for i in collected
    ]


async def upsert_listings(listings: list[RawListing]) -> int:
    """Upsert scraped listings to Supabase. Returns count of upserted."""
    if not listings:
        return 0

    evaluated = []
    rows = []

    for raw in listings:
        market_median = get_market_median_price(raw.city, raw.source)
        decision = evaluate_listing(
            ListingCandidate(
                external_id=raw.external_id,
                source=raw.source,
                title=raw.title,
                city=raw.city,
                url=raw.url,
                price_local=raw.price_local,
                bedrooms=raw.bedrooms,
                description=raw.description,
                address=raw.address,
            ),
            market_median_price=market_median,
        )
        evaluated.append((raw, decision, market_median))

        rows.append({
            "external_id": raw.external_id,
            "source": raw.source,
            "title": raw.title,
            "city": raw.city,
            "country": CITIES.get(raw.city, {}).get("country", "CA"),
            "url": raw.url,
            "price": normalize_price_to_cents(raw.price_local),
            "currency": raw.currency,
            "bedrooms": raw.bedrooms,
            "bathrooms": raw.bathrooms,
            "sqft": raw.sqft,
            "address": raw.address,
            "neighborhood": raw.neighborhood,
            "description": raw.description,
            "images": raw.images,
            "is_active": decision.decision == "pass",
            "is_flagged": decision.decision == "quarantine",
            "is_scam": decision.decision == "block",
            "flag_reason": decision.decision_reason,
            "raw_data": {
                "scraped_at": raw.scraped_at,
                "vertical_stack": {
                    "decision": decision.decision,
                    "decision_reason": decision.decision_reason,
                    "layer_results": decision.layer_results,
                    "listing_fingerprint": decision.listing_fingerprint,
                    "confidence_summary": decision.confidence_summary,
                    "market_median_price": market_median,
                },
            },
        })

    result = supabase.table("listings").upsert(
        rows,
        on_conflict="external_id,source"
    ).execute()

    if result.data:
        from stack_persist import record_vertical_stack_decisions

        record_vertical_stack_decisions(supabase, evaluated, result.data)

    return len(result.data) if result.data else 0


async def run_city(city: str):
    """Run all scrapers for a given city."""
    config = CITIES.get(city)
    if not config:
        print(f"Unknown city: {city}")
        return

    all_listings = []
    print(f"🐱 Scraping {city}...")

    if "kijiji_url" in config:
        kij = await scrape_kijiji(city, config["kijiji_url"])
        if not kij and ENABLE_BROWSER_USE_FALLBACK:
            kij = await run_browser_use_fallback("kijiji", city, config["kijiji_url"])
        print(f"  Kijiji {city}: {len(kij)} listings")
        all_listings.extend(kij)

    if "craigslist_url" in config:
        cl = await scrape_craigslist(city, config["craigslist_url"])
        if not cl and ENABLE_BROWSER_USE_FALLBACK:
            cl = await run_browser_use_fallback("craigslist", city, config["craigslist_url"])
        print(f"  Craigslist {city}: {len(cl)} listings")
        all_listings.extend(cl)

    upserted = await upsert_listings(all_listings)
    print(f"  ✓ {city}: {upserted} listings saved to Supabase")


async def run_all():
    """Run scrapers for all cities."""
    for city in CITIES:
        await run_city(city)
        await asyncio.sleep(5)  # be respectful between cities


if __name__ == "__main__":
    import sys

    city_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if city_arg:
        asyncio.run(run_city(city_arg))
    else:
        asyncio.run(run_all())
