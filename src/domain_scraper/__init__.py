"""Scrape Domain.com.au listings (for sale, for rent, sold) with Python."""

from .client import DomainScraper, ScrapeError
from .parser import (
    DETAIL_FIELDS,
    LISTING_FIELDS,
    Agent,
    Listing,
    ListingDetail,
    SearchPage,
    listing_url,
    next_data,
    parse_listing,
    parse_price,
    parse_search,
    search_url,
    suburb_slug,
)

__all__ = ["DETAIL_FIELDS", "LISTING_FIELDS", "Agent", "DomainScraper", "Listing", "ListingDetail", "ScrapeError",
           "SearchPage", "listing_url", "next_data", "parse_listing", "parse_price", "parse_search", "search_url",
           "suburb_slug"]
__version__ = "0.1.0"
