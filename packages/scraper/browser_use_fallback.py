from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from playwright.async_api import async_playwright


@dataclass
class BrowserUseListing:
    external_id: str
    source: str
    title: str
    city: str
    url: str
    price_local: Optional[float] = None
    neighborhood: Optional[str] = None
    description: Optional[str] = None
    scraped_at: str = datetime.utcnow().isoformat()


class BrowserUseFallbackAgent:
    """
    Browser-use fallback collector for hostile/dynamic pages where static selectors fail.
    Uses broader DOM heuristics after loading and scrolling.
    """

    def __init__(self, delay_ms: int = 2000, max_listings: int = 50):
        self.delay_ms = delay_ms
        self.max_listings = max_listings

    async def collect(self, source: str, city: str, page_url: str) -> List[BrowserUseListing]:
        listings: List[BrowserUseListing] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page()
            await page.set_extra_http_headers(
                {"User-Agent": "Mozilla/5.0 (compatible; FlatFinderBrowserUse/1.0)"}
            )

            try:
                await page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(self.delay_ms / 1000)

                # Basic interaction loop: scroll to trigger lazy-loaded cards.
                for _ in range(3):
                    await page.mouse.wheel(0, 3000)
                    await asyncio.sleep(0.7)

                anchors = await page.query_selector_all("a[href]")
                seen = set()

                for a in anchors:
                    if len(listings) >= self.max_listings:
                        break

                    href = await a.get_attribute("href")
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = page_url.rstrip("/") + href
                    if href in seen:
                        continue
                    seen.add(href)

                    title = (await a.inner_text() or "").strip()
                    if len(title) < 8:
                        continue

                    # Pull nearby text from parent container for light price parsing.
                    parent_text = ""
                    try:
                        parent = await a.evaluate_handle("node => node.closest('article, li, div')")
                        if parent:
                            parent_text = (await parent.evaluate("n => n.innerText") or "")[:500]
                    except Exception:
                        pass

                    price_local = self._extract_price(parent_text)
                    ext = f"bru-{city.lower()}-{abs(hash(href))}"
                    listings.append(
                        BrowserUseListing(
                            external_id=ext,
                            source=f"{source}_browser_use",
                            title=title,
                            city=city,
                            url=href,
                            price_local=price_local,
                            description=parent_text.strip() or None,
                        )
                    )
            finally:
                await browser.close()

        return listings

    @staticmethod
    def _extract_price(text: str) -> Optional[float]:
        if not text:
            return None
        match = re.search(r"(?:\$|CAD|USD|EUR|GBP)?\s*([0-9]{3,6}(?:,[0-9]{3})?)", text)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
