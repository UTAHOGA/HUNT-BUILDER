#!/usr/bin/env python3
"""Build the public 2026 hunt-season calendar from the official DWR Hunt Planner snapshot."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

MONTH_PATTERN = r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
DATE_TOKEN = rf"(?:{MONTH_PATTERN})\.?\s*\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*(?:20\d{{2}})?"
DATE_RE = re.compile(
    rf"(?P<month>{MONTH_PATTERN})\.?\s*(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(?P<year>20\d{{2}})?",
    re.IGNORECASE,
)
RANGE_RE = re.compile(rf"(?P<start>{DATE_TOKEN})\s*[-\u2013\u2014]\s*(?P<end>{DATE_TOKEN})", re.IGNORECASE)


def parse_date(parts: dict[str, str], fallback_year: int) -> date:
    month_key = re.sub(r"[^a-z]", "", parts["month"].lower())
    return date(int(parts.get("year") or fallback_year), MONTHS[month_key], int(parts["day"]))


def range_label(text: str, start_index: int) -> str:
    prefix = text[:start_index].split("|")[-1].split("&")[-1].strip(" ,;-")
    if ":" in prefix:
        prefix = prefix.rsplit(":", 1)[0].strip()
    if len(prefix) > 42:
        prefix = ""
    return prefix or "Published season"


def parse_ranges(text: str, default_year: int = 2026) -> list[dict[str, str]]:
    ranges: list[dict[str, str]] = []
    for match in RANGE_RE.finditer(text or ""):
        date_matches = list(DATE_RE.finditer(match.group(0)))
        if len(date_matches) != 2:
            continue
        start_groups = date_matches[0].groupdict()
        end_groups = date_matches[1].groupdict()
        explicit_end_year = int(end_groups.get("year") or default_year)
        explicit_start_year = int(start_groups.get("year") or explicit_end_year)
        start = parse_date(start_groups, explicit_start_year)
        end = parse_date(end_groups, explicit_end_year)
        if end < start and not end_groups.get("year"):
            end = date(start.year + 1, end.month, end.day)
        if start.year < 2026 or start.year > 2027 or end.year < 2026 or end.year > 2027:
            continue
        ranges.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "label": range_label(text, match.start()),
                "rangeText": match.group(0).strip(),
            }
        )
    return ranges


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("public/data/hunt-season-calendar-2026.json"),
    )
    args = parser.parse_args()

    with args.source.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    events: list[dict[str, object]] = []
    excluded = Counter()
    exact_hunt_codes: set[str] = set()
    seen: set[tuple[str, str, str, str]] = set()

    for row in rows:
        hunt_code = (row.get("hunt_code") or "").strip()
        season_text = (row.get("season_date_text") or "").strip()
        parsed = parse_ranges(season_text)
        if not parsed:
            lower = season_text.lower()
            if "contact operator" in lower:
                excluded["operator_assigned_dates"] += 1
            elif not season_text:
                excluded["blank_dates"] += 1
            else:
                excluded["non_exact_or_reference_text"] += 1
            continue

        exact_hunt_codes.add(hunt_code)
        for item in parsed:
            key = (hunt_code, item["start"], item["end"], item["label"])
            if key in seen:
                continue
            seen.add(key)
            events.append(
                {
                    "huntCode": hunt_code,
                    "huntName": (row.get("dwr_hunt_name") or row.get("database_hunt_name") or "").strip(),
                    "species": (row.get("dwr_species") or row.get("database_species") or "").strip(),
                    "sexType": (row.get("dwr_sex_type") or row.get("database_sex_type") or "").strip(),
                    "weapon": (row.get("dwr_weapon") or row.get("database_weapon") or "").strip(),
                    "huntType": (row.get("dwr_hunt_type") or row.get("database_hunt_type") or "").strip(),
                    "seasonType": (row.get("dwr_season_type") or "").strip(),
                    "start": item["start"],
                    "end": item["end"],
                    "label": item["label"],
                    "rangeText": item["rangeText"],
                    "seasonDateText": season_text,
                    "sourceUrl": (row.get("source_url") or "").strip(),
                }
            )

    events.sort(key=lambda item: (item["start"], item["end"], item["species"], item["huntCode"], item["label"]))
    species_counts = Counter(str(item["species"] or "Other") for item in events)
    payload = {
        "meta": {
            "title": "Utah DWR 2026 Hunt Season Start and End Dates",
            "huntYear": 2026,
            "source": "Official Utah DWR Hunt Planner HaNumber snapshot",
            "sourcePage": "https://dwrapps.utah.gov/huntboundary/huntplanner/index.html",
            "sourceRetrievedAt": "2026-08-27T02:55:30.761Z",
            "sourceRows": len(rows),
            "huntCodesWithExactDates": len(exact_hunt_codes),
            "seasonRanges": len(events),
            "excluded": dict(sorted(excluded.items())),
            "note": "CWMU operator-assigned dates and non-exact reference text are identified but are not invented as calendar dates.",
        },
        "speciesCounts": dict(sorted(species_counts.items())),
        "events": events,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(payload["meta"], indent=2))


if __name__ == "__main__":
    main()
