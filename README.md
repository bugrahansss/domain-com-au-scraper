# Domain.com.au Scraper

[![PyPI](https://img.shields.io/pypi/v/domain-com-au-scraper)](https://pypi.org/project/domain-com-au-scraper/)
[![Python](https://img.shields.io/pypi/pyversions/domain-com-au-scraper)](https://pypi.org/project/domain-com-au-scraper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Scrape [Domain.com.au](https://www.domain.com.au), one of Australia's two big property portals, into structured data. Search any suburb **for sale, for rent or sold** and get **price text and parsed price range, sale status and date, beds, baths, parking, land size, property type, address with coordinates, agency and agents, auction and inspection times**. Open a listing for its **description, features, agents' phone numbers, listing dates and Domain's suburb medians** (median sale and rent price, days on market, auction clearance). JSON or CSV.

```bash
pip install domain-com-au-scraper
export SCRAPEDO_TOKEN=your_token
domain-scraper "Bondi Beach NSW 2026" --mode sold --pages 3 -f csv -o bondi_sold.csv
domain-scraper "Sydney NSW 2000" --details --limit 20 -o sydney.json
```

## Why plain requests fail

```python
import requests

r = requests.get("https://www.domain.com.au/sale/sydney-nsw-2000/")
print(r.status_code)   # 403
print(r.text[:60])     # <HTML><HEAD><TITLE>Access Denied</TITLE>
```

Domain sits behind Akamai, which answers a script with `403 Access Denied` before any HTML. This package sends each request through [Scrape.do](https://scrape.do/?utm_source=github&utm_medium=readme&utm_campaign=domain-com-au-scraper) with `super=true` (residential proxies), which returns the real page. Each page costs 10 credits.

## Where the data is

Domain is a Next.js site, so every page carries its data in the `__NEXT_DATA__` script. No HTML parsing:

* **Search pages** (`/sale/<suburb>-<state>-<postcode>/`, `/rent/...`, `/sold-listings/...`, `?page=N`): `props.pageProps.componentProps.listingsMap` holds about 20 listings per page, plus `totalListings` and `totalPages`. New-development "projects" sit in the same map and are skipped. Domain stops at page 50.
* **Listing pages** (`/<address-slug>-<listingId>`): the same object holds the description, structured features, the price guide with agents, `createdOn`/`modifiedOn`, the gallery and `suburbInsights`.

In a live test: Sydney NSW 2000 had 934 listings for sale over 46 pages; Bondi Beach had 16,626 sold listings, 20 per page, each with its sale status and date ("Sold at auction 10 Nov 2026"). Many prices are text ("Price Withheld", "Contact Agent"); `price_min`/`price_max` are filled only when the text has a number.

## Python

```python
from domain_scraper import DomainScraper

dm = DomainScraper(token="YOUR_SCRAPEDO_TOKEN")   # or set SCRAPEDO_TOKEN

for l in dm.search("Bondi Beach NSW 2026", mode="sold", pages=2):
    print(l.status, l.price_text, l.beds, l.address, l.agency)

detail = dm.get_listing("https://www.domain.com.au/<address-slug>-<listingId>")
print(detail.description[:200], detail.features, detail.suburb_median_price)
print(dm.credits_used)
```

## Fields

**Search result:** `listing_id`, `url`, `price_text`, `price_min`, `price_max`, `status`, `property_type`, `beds`, `baths`, `parking`, `land_size`, `land_unit`, `street`, `suburb`, `state`, `postcode`, `latitude`, `longitude`, `agency`, `agency_id`, `agents`, `auction`, `inspection_open`, `inspection_close`, `images`, `promo_type`, `address`.

**Listing page:** `listing_id`, `url`, `title` (price text), `headline`, `listing_type`, `status`, `method`, `property_type`, `beds`, `baths`, `parking`, `land_area`, `address`, `unit_number`, `street_number`, `street`, `suburb`, `state`, `postcode`, `latitude`, `longitude`, `description`, `features`, `agency`, `agents` (name, phone, mobile, profile URL), `inspection`, `created_on`, `modified_on`, `images`, `suburb_median_price`, `suburb_median_rent`, `suburb_days_on_market`, `suburb_auction_clearance`, `suburb_sold_this_year`.

## Use it responsibly

Listings are public, but agents are real people: use their contact details only for legitimate purposes, respect the Australian Privacy Act and Spam Act, and Domain's terms. Don't republish listing photos or descriptions. This is not legal advice.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

The fixtures are fictional ("Example Realty", "Jane Doe", example.com).

## License

MIT
