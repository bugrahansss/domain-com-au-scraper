"""Command line entry point.

    domain-scraper "Bondi Beach NSW 2026" --mode sold --pages 3 -f csv -o bondi_sold.csv
    domain-scraper "Sydney NSW 2000" --details --limit 20 -o sydney.json
    domain-scraper https://www.domain.com.au/2702-91-liverpool-street-sydney-nsw-2000-2020997448
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import Any, List, Optional

from . import __version__
from .client import TOKEN_ENV, DomainScraper, ScrapeError
from .parser import DETAIL_FIELDS, LISTING_FIELDS, is_listing_url


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="domain-scraper", description="Scrape Domain.com.au listings: for sale, for rent and sold.")
    p.add_argument("targets", nargs="+", help='Suburbs ("Bondi Beach NSW 2026" or bondi-beach-nsw-2026) or listing URLs')
    p.add_argument("--mode", choices=("sale", "rent", "sold"), default="sale", help="Search type (default: sale)")
    p.add_argument("--pages", type=int, default=1, help="Result pages per suburb, about 20 listings each (max 50)")
    p.add_argument("--details", action="store_true", help="Open every listing page (10 credits each)")
    p.add_argument("--limit", type=int, default=0, help="Stop after this many listings")
    p.add_argument("-t", "--token", help=f"Scrape.do API token (default: ${TOKEN_ENV})")
    p.add_argument("-f", "--format", choices=("json", "csv"), default="json")
    p.add_argument("-o", "--output", help="Write to this file instead of stdout")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dm = DomainScraper(token=args.token)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    items: List[Any] = []
    failures = 0
    for target in args.targets:
        if args.limit and len(items) >= args.limit:
            break
        try:
            if is_listing_url(target):
                items.append(dm.get_listing(target))
                continue
            found = 0
            for listing in dm.search(target, args.mode, args.pages):
                if args.limit and len(items) >= args.limit:
                    break
                items.append(dm.get_listing(listing.url) if args.details else listing)
                found += 1
            print(f"{target}: {found} listings", file=sys.stderr)
        except (ScrapeError, ValueError) as exc:
            failures += 1
            print(f"fail  {target}: {exc}", file=sys.stderr)

    stream = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        if args.format == "csv":
            fields = DETAIL_FIELDS if items and hasattr(items[0], "headline") else LISTING_FIELDS + ["address"]
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(i.to_row() for i in items)
        else:
            json.dump([i.to_dict() for i in items], stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    finally:
        if args.output:
            stream.close()
            print(f"Saved {len(items)} items to {args.output} ({dm.credits_used} credits)", file=sys.stderr)
    return 1 if failures and not items else 0


if __name__ == "__main__":
    raise SystemExit(main())
