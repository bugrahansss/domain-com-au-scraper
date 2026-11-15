"""Recent sales in a suburb to CSV: price, sale type and date, beds, address.

    export SCRAPEDO_TOKEN=your_token
    python examples/sold_prices.py "Bondi Beach NSW 2026" 3
"""

import csv
import sys

from domain_scraper import DomainScraper

suburb = sys.argv[1] if len(sys.argv) > 1 else "Bondi Beach NSW 2026"
pages = int(sys.argv[2]) if len(sys.argv) > 2 else 2

dm = DomainScraper()
with open("sold.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["status", "price_text", "price_min", "beds", "baths", "property_type", "address", "agency", "url"])
    for l in dm.search(suburb, mode="sold", pages=pages):
        writer.writerow([l.status, l.price_text, l.price_min, l.beds, l.baths, l.property_type, l.address, l.agency, l.url])
print(f"done, {dm.credits_used} credits")
