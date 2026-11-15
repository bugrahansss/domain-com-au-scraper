"""Parse Domain.com.au pages.

Domain is a Next.js site: every search page and every listing page carries its
data in the ``__NEXT_DATA__`` script, so there is no HTML to pick apart.

* A **search page** (``/sale/<suburb-state-postcode>/``, ``/rent/...``,
  ``/sold-listings/...``) has ``componentProps.listingsMap``: about 20 listings
  per page with price text, beds, baths, parking, land size, property type,
  address with latitude/longitude, sale tags ("Sold by private treaty 26 Oct
  2026"), auction and inspection times, agency and agents. ``totalListings``
  and ``totalPages`` give the size of the result (Domain stops at 50 pages).
  Projects (new developments) sit in the same map and are skipped.
* A **listing page** (``/<address-slug>-<listingId>``) adds the description,
  structured features, the price guide with agents' phone numbers, the dates
  the listing was created and modified, the gallery, and Domain's suburb
  insights (median sale and rent prices, days on market, auction clearance).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

BASE_URL = "https://www.domain.com.au"
NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
LISTING_URL_RE = re.compile(r"^(?:https?://(?:www\.)?domain\.com\.au)?/([a-z0-9-]+-(\d{6,}))/?(?:[?#].*)?$")
SLUG_RE = re.compile(r"^[a-z0-9-]+-(?:nsw|vic|qld|wa|sa|tas|act|nt)-\d{4}$")
MODES = {"sale": "sale", "buy": "sale", "rent": "rent", "sold": "sold-listings", "sold-listings": "sold-listings"}


def next_data(html: str) -> Dict[str, Any]:
    """The ``__NEXT_DATA__`` JSON of a Domain page."""
    match = NEXT_RE.search(html or "")
    if not match:
        raise ValueError("No __NEXT_DATA__ on this page (blocked or not a Domain page)")
    return json.loads(match.group(1))


def _props(html: str) -> Dict[str, Any]:
    return next_data(html).get("props", {}).get("pageProps", {}).get("componentProps", {}) or {}


def suburb_slug(location: str) -> str:
    """``Bondi Beach NSW 2026`` or ``bondi-beach-nsw-2026`` -> ``bondi-beach-nsw-2026``."""
    slug = re.sub(r"[^a-z0-9]+", "-", (location or "").strip().lower()).strip("-")
    if not SLUG_RE.match(slug):
        raise ValueError(f"Use a suburb with state and postcode, e.g. 'Bondi Beach NSW 2026' (got {location!r})")
    return slug


def search_url(location: str, mode: str = "sale", page: int = 1) -> str:
    """Search URL for a suburb: ``mode`` is ``sale``, ``rent`` or ``sold``."""
    path = MODES.get((mode or "sale").lower())
    if not path:
        raise ValueError("mode must be 'sale', 'rent' or 'sold'")
    url = f"{BASE_URL}/{path}/{suburb_slug(location)}/"
    return url + (f"?page={page}" if page > 1 else "")


def listing_url(value: str) -> str:
    match = LISTING_URL_RE.match((value or "").strip())
    if not match:
        raise ValueError(f"Not a Domain listing URL: {value}")
    return f"{BASE_URL}/{match.group(1)}"


def is_listing_url(value: str) -> bool:
    return bool(LISTING_URL_RE.match((value or "").strip()))


def parse_price(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Numbers in a price text: ``$675,000 to $725,000`` -> (675000, 725000); ``$1,100,000`` -> (1100000, 1100000)."""
    nums = []
    for raw, suffix in re.findall(r"\$\s?([\d,]+(?:\.\d+)?)\s*([mk])?\b", text or "", re.I):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        value *= {"m": 1_000_000, "k": 1_000}.get(suffix.lower(), 1) if suffix else 1
        nums.append(int(value))
    if not nums:
        return None, None
    return min(nums), max(nums)


@dataclass
class Listing:
    """One listing from a search page (and, after ``get_listing``, its page)."""

    listing_id: int = 0
    url: str = ""
    price_text: str = ""
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    status: str = ""
    property_type: str = ""
    beds: Optional[int] = None
    baths: Optional[int] = None
    parking: Optional[int] = None
    land_size: Optional[float] = None
    land_unit: str = ""
    street: str = ""
    suburb: str = ""
    state: str = ""
    postcode: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    agency: str = ""
    agency_id: Optional[int] = None
    agents: List[str] = field(default_factory=list)
    auction: str = ""
    inspection_open: str = ""
    inspection_close: str = ""
    images: List[str] = field(default_factory=list)
    promo_type: str = ""

    @property
    def address(self) -> str:
        parts = [self.street, self.suburb, f"{self.state} {self.postcode}".strip()]
        return ", ".join(p for p in parts if p)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["address"] = self.address
        return out

    def to_row(self) -> Dict[str, Any]:
        row = self.to_dict()
        row["agents"] = " | ".join(self.agents)
        row["images"] = len(self.images)
        return row


@dataclass
class SearchPage:
    listings: List[Listing]
    total_listings: int = 0
    total_pages: int = 0
    current_page: int = 1


def _int(value: Any) -> Optional[int]:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _listing_id(url: str) -> int:
    match = re.search(r"-(\d{6,})/?$", url or "")
    return int(match.group(1)) if match else 0


def listing_from_model(model: Dict[str, Any]) -> Listing:
    features = model.get("features") or {}
    address = model.get("address") or {}
    branding = model.get("branding") or {}
    inspection = model.get("inspection") or {}
    tags = model.get("tags") or {}
    url = model.get("url") or ""
    listing = Listing(
        listing_id=_listing_id(url),
        url=BASE_URL + url if url.startswith("/") else url,
        price_text=(model.get("price") or "").strip(),
        status=(tags.get("tagText") or "").strip(),
        property_type=features.get("propertyTypeFormatted") or features.get("propertyType") or "",
        beds=_int(features.get("beds")),
        baths=_int(features.get("baths")),
        parking=_int(features.get("parking")),
        land_size=features.get("landSize") or None,
        land_unit=features.get("landUnit") or "" if features.get("landSize") else "",
        street=address.get("street") or "",
        suburb=address.get("suburb") or "",
        state=address.get("state") or "",
        postcode=str(address.get("postcode") or ""),
        latitude=address.get("lat"),
        longitude=address.get("lng"),
        agency=branding.get("brandName") or "",
        agency_id=_int(branding.get("agencyId")),
        agents=[a.get("agentName", "") for a in branding.get("agents") or [] if a.get("agentName")],
        auction=model.get("auction") or "",
        inspection_open=inspection.get("openTime") or "",
        inspection_close=inspection.get("closeTime") or "",
        images=list(model.get("images") or []),
        promo_type=model.get("promoType") or "",
    )
    listing.price_min, listing.price_max = parse_price(listing.price_text)
    return listing


def parse_search(html: str) -> SearchPage:
    """Listings on a search page, in the order Domain shows them (projects skipped)."""
    props = _props(html)
    listings_map = props.get("listingsMap") or {}
    order = [str(i) for i in props.get("listingSearchResultIds") or []] or list(listings_map)
    listings = []
    for key in order:
        item = listings_map.get(key) or listings_map.get(_int(key))
        if not item or item.get("listingType") != "listing":
            continue
        listings.append(listing_from_model(item.get("listingModel") or {}))
    return SearchPage(
        listings=listings,
        total_listings=_int(props.get("totalListings")) or 0,
        total_pages=_int(props.get("totalPages")) or 0,
        current_page=_int(props.get("currentPage")) or 1,
    )


@dataclass
class Agent:
    name: str = ""
    phone: str = ""
    mobile: str = ""
    profile_url: str = ""


@dataclass
class ListingDetail:
    """Everything on a listing page."""

    listing_id: int = 0
    url: str = ""
    title: str = ""
    headline: str = ""
    listing_type: str = ""
    status: str = ""
    method: str = ""
    property_type: str = ""
    beds: Optional[int] = None
    baths: Optional[int] = None
    parking: Optional[int] = None
    land_area: Optional[float] = None
    address: str = ""
    unit_number: str = ""
    street_number: str = ""
    street: str = ""
    suburb: str = ""
    state: str = ""
    postcode: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: str = ""
    features: List[str] = field(default_factory=list)
    agency: str = ""
    agents: List[Agent] = field(default_factory=list)
    inspection: str = ""
    created_on: str = ""
    modified_on: str = ""
    images: List[str] = field(default_factory=list)
    suburb_median_price: Optional[int] = None
    suburb_median_rent: Optional[int] = None
    suburb_days_on_market: Optional[int] = None
    suburb_auction_clearance: Optional[int] = None
    suburb_sold_this_year: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_row(self) -> Dict[str, Any]:
        row = self.to_dict()
        row["features"] = " | ".join(self.features)
        row["agents"] = " | ".join(a.name for a in self.agents)
        row["images"] = len(self.images)
        return row


def parse_listing(html: str, url: str = "") -> ListingDetail:
    """Parse a listing page."""
    cp = _props(html)
    if not cp.get("listingId"):
        raise ValueError("No listing on this page")
    summary = cp.get("listingSummary") or {}
    insights = cp.get("suburbInsights") or {}
    mapdata = cp.get("map") or {}
    inspection = cp.get("inspection") or {}
    stats = {s.get("key"): s.get("value") for s in summary.get("stats") or [] if isinstance(s, dict)}
    description = cp.get("description") or ""
    if isinstance(description, list):
        description = "\n".join(p for p in description if p)
    images = []
    for slide in (cp.get("gallery") or {}).get("slides") or []:
        original = (slide.get("images") or {}).get("original") or {}
        src = original.get("url") if isinstance(original, dict) else original
        if src and slide.get("mediaType", "image") == "image":
            images.append(src)
    features = [f.get("name") for f in cp.get("structuredFeatures") or [] if f.get("name")] or list(cp.get("features") or [])
    agents = []
    for a in (cp.get("priceGuide") or {}).get("agents") or cp.get("agents") or []:
        agents.append(Agent(name=a.get("name", ""), phone=a.get("phone") or "", mobile=a.get("mobile") or "",
                            profile_url=a.get("agentProfileUrl") or ""))
    return ListingDetail(
        listing_id=_int(cp.get("listingId")) or 0,
        url=url or cp.get("listingUrl") or "",
        title=(summary.get("title") or "").strip(),
        headline=(cp.get("headline") or "").strip(),
        listing_type={"buy": "sale"}.get(summary.get("mode") or "", summary.get("mode") or ""),
        status=summary.get("status") or "",
        method=summary.get("method") or "",
        property_type=summary.get("propertyType") or cp.get("propertyType") or "",
        beds=_int(summary.get("beds")),
        baths=_int(summary.get("baths")),
        parking=_int(summary.get("parking")),
        land_area=stats.get("landArea"),
        address=summary.get("address") or cp.get("address") or "",
        unit_number=str(cp.get("unitNumber") or ""),
        street_number=str(cp.get("streetNumber") or ""),
        street=cp.get("street") or "",
        suburb=cp.get("suburb") or "",
        state=(cp.get("stateAbbreviation") or "").upper(),
        postcode=str(cp.get("postcode") or ""),
        latitude=mapdata.get("latitude"),
        longitude=mapdata.get("longitude"),
        description=description.strip(),
        features=features,
        agency=(cp.get("priceGuide") or {}).get("agencyName") or cp.get("agencyName") or "",
        agents=agents,
        inspection=(inspection.get("inspectionText") or "").strip(),
        created_on=cp.get("createdOn") or "",
        modified_on=cp.get("modifiedOn") or "",
        images=images,
        suburb_median_price=_int(insights.get("medianPrice")),
        suburb_median_rent=_int(insights.get("medianRentPrice")),
        suburb_days_on_market=_int(insights.get("avgDaysOnMarket")),
        suburb_auction_clearance=_int(insights.get("auctionClearance")),
        suburb_sold_this_year=_int(insights.get("nrSoldThisYear")),
    )


LISTING_FIELDS = list(Listing().to_dict().keys())
DETAIL_FIELDS = list(ListingDetail().to_dict().keys())
