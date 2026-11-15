"""Fetch Domain.com.au pages through the Scrape.do API.

Domain sits behind Akamai: a plain ``requests.get`` from a script gets
``403 Access Denied`` before any HTML. Sending the request through Scrape.do
with ``super=true`` (residential proxies) returns the real page with its
``__NEXT_DATA__``. Each page costs 10 Scrape.do credits.
"""

from __future__ import annotations

import os
import time
from typing import Iterator, List, Optional

import requests

from .parser import (
    ListingDetail,
    Listing,
    listing_url,
    parse_listing,
    parse_search,
    search_url,
)

API_URL = "https://api.scrape.do/"
TOKEN_ENV = "SCRAPEDO_TOKEN"
MAX_PAGES = 50  # Domain stops at page 50


class ScrapeError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class DomainScraper:
    """Search Domain.com.au by suburb (for sale, for rent, sold) and read listing pages.

    >>> dm = DomainScraper(token="YOUR_SCRAPEDO_TOKEN")
    >>> for listing in dm.search("Bondi Beach NSW 2026", mode="sold", pages=2):
    ...     print(listing.price_text, listing.status, listing.address)
    >>> detail = dm.get_listing(listing.url)
    """

    def __init__(self, token: Optional[str] = None, timeout: float = 90.0, retries: int = 2,
                 geo_code: str = "", session: Optional[requests.Session] = None):
        self.token = token or os.environ.get(TOKEN_ENV, "")
        if not self.token:
            raise ValueError(f"A Scrape.do API token is required. Pass token=... or set {TOKEN_ENV}.")
        self.timeout = timeout
        self.retries = max(0, retries)
        self.geo_code = geo_code
        self.session = session or requests.Session()
        self.requests_made = 0

    def fetch(self, url: str) -> str:
        params = {"token": self.token, "url": url, "super": "true"}
        if self.geo_code:
            params["geoCode"] = self.geo_code
        last: Optional[ScrapeError] = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(API_URL, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                last = ScrapeError(f"Request failed: {exc}")
            else:
                if response.status_code == 200 and "__NEXT_DATA__" in response.text:
                    self.requests_made += 1
                    return response.text
                if response.status_code == 200:
                    self.requests_made += 1
                    last = ScrapeError(f"Blocked page for {url} (no __NEXT_DATA__)", 200)
                else:
                    last = ScrapeError(f"Request for {url} failed with status {response.status_code}",
                                       response.status_code)
                    if response.status_code in (400, 401, 404, 410):
                        break
            if attempt < self.retries:
                time.sleep(2 * (attempt + 1))
        assert last is not None
        raise last

    def search(self, location: str, mode: str = "sale", pages: int = 1) -> Iterator[Listing]:
        """Listings for a suburb (``"Bondi Beach NSW 2026"``), ``mode`` = ``sale``, ``rent`` or ``sold``."""
        seen = set()
        last_page = None
        for page in range(1, min(max(1, pages), MAX_PAGES) + 1):
            if last_page is not None and page > last_page:
                break
            result = parse_search(self.fetch(search_url(location, mode, page)))
            last_page = result.total_pages or page
            fresh = [l for l in result.listings if l.listing_id not in seen]
            if not fresh:
                break
            for listing in fresh:
                seen.add(listing.listing_id)
                yield listing

    def get_listing(self, url: str) -> ListingDetail:
        url = listing_url(url)
        return parse_listing(self.fetch(url), url=url)

    @property
    def credits_used(self) -> int:
        return self.requests_made * 10
