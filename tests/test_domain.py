import csv
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain_scraper import DomainScraper, ScrapeError, listing_url, parse_listing, parse_price, parse_search, search_url, suburb_slug  # noqa: E402
from domain_scraper import cli  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
SEARCH = (FIX / "search_bondi.html").read_text(encoding="utf-8")
LISTING = (FIX / "listing.html").read_text(encoding="utf-8")
BLOCKED = (FIX / "blocked.html").read_text(encoding="utf-8")
URL1 = "https://www.domain.com.au/1-example-street-bondi-beach-nsw-2026-2099000001"


class R:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        return self.responses.pop(0)


class UrlTests(unittest.TestCase):
    def test_slug_and_urls(self):
        self.assertEqual(suburb_slug("Bondi Beach NSW 2026"), "bondi-beach-nsw-2026")
        self.assertEqual(search_url("bondi-beach-nsw-2026", "sold", 2), "https://www.domain.com.au/sold-listings/bondi-beach-nsw-2026/?page=2")
        self.assertEqual(search_url("Sydney NSW 2000", "rent"), "https://www.domain.com.au/rent/sydney-nsw-2000/")
        with self.assertRaises(ValueError):
            suburb_slug("Bondi")
        with self.assertRaises(ValueError):
            search_url("Sydney NSW 2000", "lease")
        self.assertEqual(listing_url(URL1 + "/"), URL1)
        with self.assertRaises(ValueError):
            listing_url("https://example.com/x")

    def test_price(self):
        self.assertEqual(parse_price("$675,000 to $725,000"), (675000, 725000))
        self.assertEqual(parse_price("$1,100,000"), (1100000, 1100000))
        self.assertEqual(parse_price("$1700 per week"), (1700, 1700))
        self.assertEqual(parse_price("Auction guide $1.2m"), (1200000, 1200000))
        self.assertEqual(parse_price("Price Withheld"), (None, None))


class ParseTests(unittest.TestCase):
    def test_search(self):
        page = parse_search(SEARCH)
        self.assertEqual((page.total_listings, page.total_pages), (3, 1))
        self.assertEqual([l.listing_id for l in page.listings], [2099000002, 2099000001])
        l = page.listings[1]
        self.assertEqual((l.price_min, l.price_max), (1250000, 1350000))
        self.assertEqual(l.status, "Sold at auction 10 Nov 2026")
        self.assertEqual((l.beds, l.baths, l.parking), (2, 1, 1))
        self.assertEqual(l.address, "1/1 Example Street, Bondi Beach, NSW 2026")
        self.assertEqual((l.agency, l.agents), ("Example Realty", ["Jane Doe"]))
        self.assertEqual(l.url, URL1)
        self.assertEqual(page.listings[0].land_size, 450)
        self.assertIsNone(page.listings[0].price_min)

    def test_listing(self):
        d = parse_listing(LISTING)
        self.assertEqual(d.listing_id, 2099000001)
        self.assertEqual((d.title, d.listing_type, d.method), ("$1,250,000 - $1,350,000", "sale", "auction"))
        self.assertEqual(d.description, "First paragraph.\nSecond paragraph.")
        self.assertEqual(d.features, ["Balcony", "Air conditioning"])
        self.assertEqual(d.agents[0].mobile, "0400 000 000")
        self.assertEqual((d.state, d.land_area, d.images), ("NSW", 85, ["https://example.com/a.jpg"]))
        self.assertEqual((d.suburb_median_price, d.suburb_auction_clearance), (1500000, 70))
        with self.assertRaises(ValueError):
            parse_listing(BLOCKED)
        with self.assertRaises(ValueError):
            parse_listing(SEARCH)


class ClientTests(unittest.TestCase):
    def test_token_required(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                DomainScraper()

    def test_search_super(self):
        s = Session([R(200, SEARCH)])
        dm = DomainScraper(token="t", session=s)
        out = list(dm.search("Bondi Beach NSW 2026", "sold", pages=5))
        self.assertEqual(len(out), 2)
        self.assertEqual(len(s.calls), 1)  # total_pages = 1
        self.assertEqual(s.calls[0]["super"], "true")
        self.assertEqual(dm.credits_used, 10)

    @mock.patch("domain_scraper.client.time.sleep")
    def test_blocked_retried(self, _):
        s = Session([R(200, BLOCKED), R(403, "x"), R(200, LISTING)])
        d = DomainScraper(token="t", session=s).get_listing(URL1)
        self.assertEqual(d.agency, "Example Realty")
        self.assertEqual(len(s.calls), 3)

    def test_401_stops(self):
        s = Session([R(401)])
        with self.assertRaises(ScrapeError):
            DomainScraper(token="t", session=s, retries=3).get_listing(URL1)
        self.assertEqual(len(s.calls), 1)


class CliTests(unittest.TestCase):
    def run_cli(self, argv, responses):
        s = Session(responses)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("domain_scraper.client.requests.Session", return_value=s), \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = cli.main(argv + ["-t", "t"])
        return code, out.getvalue()

    def test_csv(self):
        code, out = self.run_cli(["Bondi Beach NSW 2026", "--mode", "sold", "-f", "csv"], [R(200, SEARCH)])
        rows = list(csv.DictReader(io.StringIO(out)))
        self.assertEqual(code, 0)
        self.assertEqual(rows[1]["agency"], "Example Realty")

    def test_details_limit(self):
        code, out = self.run_cli(["Bondi Beach NSW 2026", "--details", "--limit", "1"], [R(200, SEARCH), R(200, LISTING)])
        self.assertEqual(len(json.loads(out)), 1)

    def test_listing_url(self):
        code, out = self.run_cli([URL1], [R(200, LISTING)])
        self.assertEqual(json.loads(out)[0]["suburb"], "Bondi Beach")


if __name__ == "__main__":
    unittest.main()
