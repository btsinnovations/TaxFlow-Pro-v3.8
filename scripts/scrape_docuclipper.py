"""Scrape DocuClipper's supported-banks list and normalize to JSON.

Usage:
    python scripts/scrape_docuclipper.py

Output:
    data/docuclipper-institutions.json

This script is idempotent: re-running overwrites the institution list and
deduplicates by normalized name.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import requests


def fetch_supported_banks() -> str:
    url = "https://www.docuclipper.com/docs/supported-banks/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def _clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name.strip())
    # Remove surrounding bullets or dashes
    name = re.sub(r"^[-•\*\s]+", "", name)
    name = re.sub(r"\s*\(.*\)$", "", name)
    return name.strip()


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def guess_family(name: str, country: str) -> str:
    lowered = name.lower()
    if any(kw in lowered for kw in ("credit card", "amex", "mastercard", "visa", "discover")):
        return "credit_card_pdf"
    if any(kw in lowered for kw in ("schwab", "fidelity", "ameritrade", "e*trade", "td ameritrade", "interactive brokers")):
        return "brokerage_pdf"
    if "hsbc" in lowered or "barclays" in lowered or "scotiabank" in lowered:
        return "pdf_table_multi"
    if "credit union" in lowered or "savings bank" in lowered or "federal savings" in lowered:
        return "pdf_table_simple"
    if "trust company" in lowered or "investment" in lowered or "wealth" in lowered:
        return "brokerage_pdf"
    if any(kw in lowered for kw in ("ally", "axos", "everbank", "bmo harris", "cit bank")):
        return "csv_standard"
    return "pdf_table_simple"


def parse_html(html: str) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    # Extract list items; fallback to lines that look like institution names
    list_items = re.findall(r"<li>(?:<p>)?([^\n<]+)(?:</p>)?</li>", html)
    if not list_items:
        # Some docs use paragraph blocks separated by blank lines
        list_items = [line.strip() for line in html.splitlines() if line.strip().startswith("- ")]
        list_items = [item.lstrip("- ").strip() for item in list_items]

    for raw in list_items:
        name = _clean_name(raw)
        if not name or len(name) < 3:
            continue
        norm = _normalize(name)
        if norm in seen:
            continue
        # Country detection from text headings is unreliable; default US, patch later
        country = "US"
        seen[norm] = {
            "name": name,
            "family": guess_family(name, country),
            "country": country,
        }
    return list(seen.values())


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / "data" / "docuclipper-institutions.json"

    html = fetch_supported_banks()
    institutions = parse_html(html)

    document = {
        "source": "https://www.docuclipper.com/docs/supported-banks/",
        "scraped_at": "2026-06-28",
        "note": (
            "DocuClipper supports any English-language PDF statement. "
            "This list is a 'we have seen this one' registry, not a hard whitelist."
        ),
        "institutions": sorted(institutions, key=lambda i: i["name"].lower()),
        "phase1_institutions": [
            "Ally", "Bank of America", "BECU", "Capital One", "Charles Schwab", "Chase",
            "Citibank", "Citizens", "Discover", "Huntington", "Marcus", "Navy Federal",
            "PenFed", "PNC", "SoFi", "Synchrony", "Truist", "U.S. Bank", "USAA", "Wells Fargo",
            "Cash App", "American Express",
        ],
        "families": {
            "csv_standard": "Generic CSV export with Date/Description/Amount/Balance columns",
            "ofx_qfx": "OFX/QFX Quicken/QuickBooks export format",
            "pdf_table_simple": "Single-page PDF transaction table (regex-based)",
            "pdf_table_multi": "Multi-page PDF transaction table",
            "credit_card_pdf": "Credit-card-specific PDF with posting dates and payment/credit logic",
            "brokerage_pdf": "Brokerage cash/money-market transactions only; holdings excluded",
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(institutions)} institutions to {output_path}")


if __name__ == "__main__":
    main()
