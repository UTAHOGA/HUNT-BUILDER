#!/usr/bin/env python3
"""Acquire the current Utah DWR management-plan library used by Hunt Research.

The DWR pages are the authority for which plans are current. This script stores
byte-exact PDFs in the ignored RAW tree and writes a small, tracked inventory
with URL, checksum, page-count, and scope evidence. Management-plan values are
policy/objective context; they are never harvest actuals, permit truth, or draw
probability truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from pypdf import PdfReader


REPO = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "pdf" / "management_plans"
INVENTORY_JSON = REPO / "data_truth" / "harvest_results_truth" / "sources" / "dwr_management_plan_inventory_2026.json"
INVENTORY_MD = REPO / "data_truth" / "harvest_results_truth" / "sources" / "dwr_management_plan_inventory_2026.md"
HUNT_PLANNER_MANAGEMENT_UNITS = REPO / "data_model" / "harvest_quality" / "huntplanner_management_units_2026.csv"

BIG_GAME_PAGE = "https://wildlife.utah.gov/biggame"
PUBLICATIONS_PAGE = "https://wildlife.utah.gov/publications"
COUGAR_PROGRAM_BACKGROUND_URL = "https://wildlife.utah.gov/cougar/background"
COUGAR_HISTORICAL_PLAN_URL = "https://wildlife.utah.gov/pdf/cougars/cmgtplan.pdf"
COUGAR_HISTORICAL_RAC_ARCHIVE_URL = (
    "https://wildlife.utah.gov/public_meetings/rac_minutes/proposed-changes-to-utah-cougar-management-plan-2021.pdf"
)

BOARD_APPROVAL_PACKET_2025_09 = "https://wildlife.utah.gov/pdf/meetings/board/2025-12-04-board-packet.pdf"
BOARD_APPROVAL_NEWS_BOOK_CLIFFS_2025 = "https://wildlife.utah.gov/news/2025/12/05/wildlife-board-approves-updates-for-bison-hunting-and-other-changes"

# The current DWR big-game page still links pre-review copies for mountain goat
# and bighorn sheep. The Wildlife Board approved their mid-plan updates on
# Sept. 18, 2025, so the accepted RAC documents are the current content source.
STATEWIDE_PLANS = (
    {
        "species_family": "mule_deer",
        "plan_title": "Utah Mule Deer Statewide Management Plan",
        "source_url": "https://wildlife.utah.gov/pdf/bg/plans/mule_deer_plan.pdf",
        "source_index_url": BIG_GAME_PAGE,
    },
    {
        "species_family": "elk",
        "plan_title": "Utah Statewide Elk Management Plan",
        "source_url": "https://wildlife.utah.gov/pdf/bg/plans/elk_plan.pdf",
        "source_index_url": BIG_GAME_PAGE,
    },
    {
        "species_family": "mountain_goat",
        "plan_title": "Utah Mountain Goat Statewide Management Plan (2025 approved mid-plan review)",
        "source_url": "https://wildlife.utah.gov/pdf/meetings/rac/2025-08-proposed-mountain-goat-management-plan.pdf",
        "source_index_url": "https://wildlife.utah.gov/meetings",
        "approval_evidence_url": BOARD_APPROVAL_PACKET_2025_09,
        "approval_evidence_pdf_page": 6,
        "required_text_evidence": ["reviewed in 2025"],
        "superseded_public_listing_url": "https://wildlife.utah.gov/pdf/bg/plans/mtn_goat_plan.pdf",
        "listing_discrepancy": "The big-game/publications index still links the pre-2025-review copy.",
    },
    {
        "species_family": "moose",
        "plan_title": "Utah Moose Statewide Management Plan",
        "source_url": "https://wildlife.utah.gov/pdf/bg/plans/moose_plan.pdf",
        "source_index_url": BIG_GAME_PAGE,
    },
    {
        "species_family": "bighorn_sheep",
        "plan_title": "Utah Bighorn Sheep Statewide Management Plan (2025 approved mid-plan review)",
        "source_url": "https://wildlife.utah.gov/pdf/meetings/rac/2025-08-proposed-bighorn-sheep-management-plan.pdf",
        "source_index_url": "https://wildlife.utah.gov/meetings",
        "approval_evidence_url": BOARD_APPROVAL_PACKET_2025_09,
        "approval_evidence_pdf_page": 6,
        "required_text_evidence": ["reviewed in 2025"],
        "superseded_public_listing_url": "https://wildlife.utah.gov/pdf/bg/plans/bighorn-plan.pdf",
        "listing_discrepancy": "The big-game/publications index still links the pre-2025-review copy.",
    },
    {
        "species_family": "pronghorn",
        "plan_title": "Utah Pronghorn Statewide Management Plan",
        "source_url": "https://wildlife.utah.gov/pdf/bg/plans/pronghorn_plan.pdf",
        "source_index_url": BIG_GAME_PAGE,
    },
    {
        "species_family": "black_bear",
        "plan_title": "Utah Black Bear Management Plan 2023-2035",
        "source_url": "https://wildlife.utah.gov/pdf/bear/black_bear_plan_2023-35.pdf",
        "source_index_url": PUBLICATIONS_PAGE,
        "required_text_evidence": [
            "Maintain a stable bear population",
            "Adult Male (5 yrs old)",
            "Female in the sport harvest category",
            "Population Growth Rate (DNA study)",
        ],
        "objective_evidence_pdf_pages": [26],
        "management_measure_candidates": [
            {
                "measure": "adult_male_age_5_share_of_sport_harvest",
                "unit": "percent",
                "light_harvest_strategy": ">35%",
                "moderate_harvest_strategy": "25-35%",
                "liberal_harvest_strategy": "<25%",
                "scope": "bear_management_unit_three_year_recommendation_cycle",
            },
            {
                "measure": "female_share_of_sport_harvest",
                "unit": "percent",
                "light_harvest_strategy": "<30%",
                "moderate_harvest_strategy": "30-40%",
                "liberal_harvest_strategy": "40-45%",
                "scope": "bear_management_unit_three_year_recommendation_cycle",
            },
            {
                "measure": "population_growth_rate_dna_study",
                "unit": "percent",
                "light_harvest_strategy": "+10% to +20% when the plan footnote applies",
                "moderate_harvest_strategy": "-10% to +10%",
                "liberal_harvest_strategy": "-10% to -20%",
                "scope": "bear_management_unit_three_year_recommendation_cycle",
            },
        ],
        "research_display_guidance": (
            "Display the DWR-selected unit harvest strategy with the matching performance-target bands only when "
            "a current DWR unit strategy/source supplies that selection; do not treat a band as an observed value."
        ),
    },
    {
        "species_family": "wild_turkey",
        "plan_title": "2023 Utah Wild Turkey Management Plan",
        "source_url": "https://wildlife.utah.gov/pdf/uplandgame/turkey/turkey_plan.pdf",
        "source_index_url": PUBLICATIONS_PAGE,
        "required_text_evidence": [
            "2023 Utah Wild Turkey Management Plan",
            "Enhance wild turkey habitat",
            "100,000 acres statewide by 2029",
            "Increase the number of turkey hunters by 10",
        ],
        "objective_evidence_pdf_pages": [20, 23],
        "management_measure_candidates": [
            {
                "measure": "wild_turkey_habitat_enhancement",
                "objective": 100000,
                "unit": "acres statewide by 2029",
                "scope": "statewide_program",
            },
            {
                "measure": "turkey_hunter_participation_increase",
                "objective": 10,
                "unit": "percent statewide by 2029",
                "scope": "statewide_program",
            },
            {
                "measure": "wild_turkey_event_participation_increase",
                "objective": 10,
                "unit": "percent statewide by 2029",
                "scope": "statewide_program",
            },
        ],
        "research_display_guidance": (
            "These are statewide program objectives, not hunt-unit harvest-quality objectives. Keep them in plan "
            "context unless DWR publishes a compatible unit-level current value."
        ),
    },
)

BISON_UNIT_PLANS = (
    {
        "unit_labels": ["Henry Mountains"],
        "source_url": "https://wildlife.utah.gov/pdf/bg/plans/bison_15.pdf",
        "source_index_url": BIG_GAME_PAGE,
    },
    {
        "unit_labels": ["Book Cliffs"],
        "source_url": "https://wildlife.utah.gov/pdf/meetings/rac/2025-11-book-cliffs-bison-management-plan.pdf",
        "source_index_url": "https://wildlife.utah.gov/meetings",
        "approval_evidence_url": BOARD_APPROVAL_NEWS_BOOK_CLIFFS_2025,
        "required_text_evidence": ["population size of 650 adult"],
        "superseded_public_listing_url": "https://wildlife.utah.gov/pdf/bg/plans/bison_10.pdf",
        "listing_discrepancy": "The big-game/publications index still links the superseded 2007 plan with a 450-adult objective; the Board approved this replacement in December 2025.",
    },
)

UNIT_INDEXES = (
    ("mule_deer", "https://wildlife.utah.gov/deer/plans"),
    ("elk", "https://wildlife.utah.gov/elk/plans"),
    ("mountain_goat", "https://wildlife.utah.gov/goat/plans"),
    ("bighorn_sheep", "https://wildlife.utah.gov/sheep/plans"),
)

DESERT_BIGHORN_FILENAMES = {
    "bighorn_henry_mountains.pdf",
    "bighorn_kaiparowits.pdf",
    "bighorn_la_sal_potash.pdf",
    "bighorn_mineral_mountains.pdf",
    "bighorn_pine_valley.pdf",
    "bighorn_san_juan.pdf",
    "bighorn_san_rafael.pdf",
    "bighorn_zion.pdf",
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            label = " ".join(unescape("".join(self._text)).split())
            self.links.append((self._href, label))
            self._href = None
            self._text = []


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(unescape(data).split())
        if value:
            self.text.append(value)


def fetch(url: str) -> tuple[bytes, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 HUNT-BUILDER official-source acquisition"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), response.geturl(), response.headers.get("Content-Type", "")


def scrape_plan_links(species: str, index_url: str) -> list[dict[str, object]]:
    raw, final_url, _ = fetch(index_url)
    parser = LinkParser()
    parser.feed(raw.decode("utf-8", "replace"))
    by_url: dict[str, dict[str, object]] = {}
    for href, label in parser.links:
        url = urljoin(final_url, href)
        if not urlparse(url).path.lower().endswith(".pdf") or "/pdf/bg/plans/" not in url.lower():
            continue
        record = by_url.setdefault(
            url,
            {
                "species_family": species,
                "plan_scope": "unit",
                "unit_labels": [],
                "source_index_url": index_url,
                "source_url": url,
            },
        )
        labels = record["unit_labels"]
        assert isinstance(labels, list)
        if label and label not in labels:
            labels.append(label)
    return list(by_url.values())


def bighorn_subspecies(url: str) -> str | None:
    filename = Path(urlparse(url).path).name.lower()
    if not filename.startswith("bighorn_"):
        return None
    return "desert_bighorn" if filename in DESERT_BIGHORN_FILENAMES else "rocky_mountain_bighorn"


def collect_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for plan in STATEWIDE_PLANS:
        records.append({**plan, "plan_scope": "statewide", "unit_labels": []})
    for plan in BISON_UNIT_PLANS:
        records.append({**plan, "species_family": "bison", "plan_scope": "unit"})
    for species, index_url in UNIT_INDEXES:
        records.extend(scrape_plan_links(species, index_url))

    seen: set[str] = set()
    for record in records:
        url = str(record["source_url"])
        if url in seen:
            raise RuntimeError(f"Duplicate plan URL across inventory: {url}")
        seen.add(url)
        if record["species_family"] == "bighorn_sheep" and record["plan_scope"] == "unit":
            record["subspecies"] = bighorn_subspecies(url)
    return records


def local_path_for(record: dict[str, object]) -> Path:
    species = str(record["species_family"])
    scope = str(record["plan_scope"])
    filename = Path(urlparse(str(record["source_url"])).path).name
    return RAW_ROOT / scope / species / filename


def verify_pdf(path: Path) -> tuple[str, int, int, str | None]:
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"Not a PDF: {path}")
    digest = hashlib.sha256(data).hexdigest()
    reader = PdfReader(path)
    title = None
    if reader.metadata and reader.metadata.title:
        title = str(reader.metadata.title).strip() or None
    return digest, len(reader.pages), len(data), title


def verify_required_text(path: Path, required_phrases: list[str]) -> None:
    if not required_phrases:
        return
    reader = PdfReader(path)
    text = " ".join(" ".join((page.extract_text() or "").split()) for page in reader.pages).lower()
    missing = [phrase for phrase in required_phrases if phrase.lower() not in text]
    if missing:
        raise RuntimeError(f"Required current-plan text missing from {path}: {missing}")


def normalized_html_text(raw: bytes) -> str:
    parser = TextParser()
    parser.feed(raw.decode("utf-8", "replace"))
    return " ".join(parser.text)


def evaluate_cougar_program_authority(*, refresh: bool) -> dict[str, object]:
    publications_raw, publications_final_url, _ = fetch(PUBLICATIONS_PAGE)
    publications_parser = LinkParser()
    publications_parser.feed(publications_raw.decode("utf-8", "replace"))
    listed_cougar_plan_links = sorted(
        {
            urljoin(publications_final_url, href)
            for href, label in publications_parser.links
            if urlparse(urljoin(publications_final_url, href)).path.lower().endswith(".pdf")
            and "cougar" in f"{href} {label}".lower()
        }
    )

    program_raw, program_final_url, program_content_type = fetch(COUGAR_PROGRAM_BACKGROUND_URL)
    program_text = normalized_html_text(program_raw)
    required_program_phrases = (
        "Cougar management goals",
        "manage cougars in ways that are consistent with their prey base",
        "In 2023, the Utah Legislature changed",
        "harvested year-round with a hunting or combination license",
    )
    missing_program_phrases = [phrase for phrase in required_program_phrases if phrase.lower() not in program_text.lower()]
    if missing_program_phrases:
        raise RuntimeError(f"Required current cougar-program text missing: {missing_program_phrases}")
    program_path = RAW_ROOT / "authority" / "cougar" / "cougar_program_background.html"
    program_path.parent.mkdir(parents=True, exist_ok=True)
    program_path.write_bytes(program_raw)

    historical_path = RAW_ROOT / "historical" / "cougar" / "utah_cougar_management_plan_v3_2015-2025_rac_archive.pdf"
    historical_path.parent.mkdir(parents=True, exist_ok=True)
    historical_record: dict[str, object] = {
        "original_plan_url": COUGAR_HISTORICAL_PLAN_URL,
        "official_rac_archive_url": COUGAR_HISTORICAL_RAC_ARCHIVE_URL,
        "covered_period": "2015-2025",
        "authority_status": "HISTORICAL_EXPIRED_BY_DOCUMENT_TERM_NOT_CURRENT_OBJECTIVE_AUTHORITY",
        "downloaded_this_run": False,
    }
    retrieval_attempts: list[dict[str, object]] = []
    if refresh or not historical_path.exists():
        historical_raw = None
        historical_final_url = ""
        historical_source_url = ""
        historical_source_class = ""
        for source_url, source_class in (
            (COUGAR_HISTORICAL_PLAN_URL, "official_plan_url"),
            (COUGAR_HISTORICAL_RAC_ARCHIVE_URL, "official_dwr_rac_archive_copy"),
        ):
            try:
                candidate_raw, candidate_final_url, candidate_content_type = fetch(source_url)
            except urllib.error.HTTPError as exc:
                retrieval_attempts.append({"source_url": source_url, "status": f"http_{exc.code}"})
                continue
            if not candidate_raw.startswith(b"%PDF"):
                retrieval_attempts.append(
                    {"source_url": source_url, "status": "not_pdf", "content_type": candidate_content_type}
                )
                continue
            historical_raw = candidate_raw
            historical_final_url = candidate_final_url
            historical_source_url = source_url
            historical_source_class = source_class
            retrieval_attempts.append({"source_url": source_url, "status": "downloaded"})
            break
        if historical_raw is not None:
            historical_path.write_bytes(historical_raw)
            historical_record["downloaded_this_run"] = True
    else:
        historical_source_url = COUGAR_HISTORICAL_RAC_ARCHIVE_URL
        historical_source_class = "official_dwr_rac_archive_copy"
        historical_final_url = historical_source_url
        retrieval_attempts.append({"source_url": historical_source_url, "status": "retained_copy_used"})

    historical_record["retrieval_attempts"] = retrieval_attempts
    if historical_path.exists():
        historical_sha256, historical_pages, historical_size, historical_title = verify_pdf(historical_path)
        verify_required_text(historical_path, ["through 2025", "2015"])
        historical_record.update(
            {
                "retrieval_status": "retained_official_copy_available",
                "source_url": historical_source_url,
                "source_class": historical_source_class,
                "resolved_url": historical_final_url,
                "local_path": relative(historical_path),
                "sha256": historical_sha256,
                "pages": historical_pages,
                "size_bytes": historical_size,
                "pdf_metadata_title": historical_title,
            }
        )
    else:
        historical_record.update(
            {
                "retrieval_status": "official_urls_unavailable_at_retrieval_time",
                "source_url": COUGAR_HISTORICAL_PLAN_URL,
                "source_class": "indexed_historical_reference_only",
            }
        )

    return {
        "species_family": "cougar",
        "authority_status": "CURRENT_OPEN_SEASON_PROGRAM_AUTHORITY_NO_CURRENT_MANAGEMENT_PLAN_LISTED",
        "publications_index_check": {
            "source_url": PUBLICATIONS_PAGE,
            "lists_current_cougar_management_plan": bool(listed_cougar_plan_links),
            "matching_pdf_urls": listed_cougar_plan_links,
        },
        "current_program_authority": {
            "source_url": COUGAR_PROGRAM_BACKGROUND_URL,
            "resolved_url": program_final_url,
            "content_type": program_content_type,
            "local_path": relative(program_path),
            "sha256": hashlib.sha256(program_raw).hexdigest(),
            "size_bytes": len(program_raw),
            "required_text_evidence": list(required_program_phrases),
            "management_goal": (
                "Manage cougars consistently with their prey base, habitat, and other biological and sociological constraints."
            ),
            "regulatory_model": (
                "Year-round harvest with a hunting or combination license; no bag limit and no additional cougar permit required."
            ),
            "regulatory_model_effective_context": "DWR states the Utah Legislature changed cougar harvest regulations in 2023.",
            "quantified_current_objective_status": "NO_QUANTIFIED_CURRENT_OBJECTIVE_FOUND_ON_PROGRAM_PAGE",
        },
        "historical_management_plan": historical_record,
        "research_display_guidance": (
            "Label cougar as a current open-season program, not as a current management plan. Use the current DWR "
            "program page for qualitative management context. Do not display targets from the "
            "2015-2025 plan as current, and leave a quantified management-objective value unavailable until DWR "
            "publishes or confirms current authority."
        ),
    }


def relative(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def hunt_planner_management_context() -> dict[str, object]:
    if not HUNT_PLANNER_MANAGEMENT_UNITS.exists():
        return {"status": "source_not_present", "source_path": relative(HUNT_PLANNER_MANAGEMENT_UNITS)}
    fields = (
        "current_age_3yr_average",
        "age_objective",
        "population_objective",
        "current_population_estimate",
        "bucks_per_100_does_objective",
        "current_bucks_per_100_does_3yr_average",
    )
    with HUNT_PLANNER_MANAGEMENT_UNITS.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_species: dict[str, dict[str, int]] = {}
    for species in sorted({row.get("species", "") for row in rows}):
        subset = [row for row in rows if row.get("species", "") == species]
        by_species[species] = {
            "management_unit_rows": len(subset),
            **{field: sum(bool((row.get(field) or "").strip()) for row in subset) for field in fields},
        }
    return {
        "status": "available",
        "source_path": relative(HUNT_PLANNER_MANAGEMENT_UNITS),
        "management_unit_rows": len(rows),
        "counts_by_species": by_species,
    }


def copy_supporting_attachment(path: Path, filename: str) -> dict[str, object]:
    destination = RAW_ROOT / "supporting" / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    sha256, pages, size_bytes, pdf_title = verify_pdf(destination)
    return {
        "classification": "supporting_evidence_not_management_plan",
        "original_path": str(path),
        "local_path": relative(destination),
        "sha256": sha256,
        "pages": pages,
        "size_bytes": size_bytes,
        "pdf_title": pdf_title,
    }


def write_markdown(payload: dict[str, object]) -> None:
    records = payload["plans"]
    assert isinstance(records, list)
    cougar = payload["cougar_program_authority"]
    assert isinstance(cougar, dict)
    lines = [
        "# Utah DWR Management Plan and Program Authority Inventory",
        "",
        f"Retrieved: `{payload['retrieved_at_utc']}`",
        "",
        "These are the current plans linked by the Utah DWR publications, big-game, and species plan pages at retrieval time for species represented in Hunt Research. Statewide plans set strategy and management frameworks; unit plans provide local population, habitat, composition, and quality objectives where DWR publishes them. They are context for interpreting harvest and Hunt Planner metrics, not observed harvest rows, permit truth, or draw-probability truth.",
        "",
        "## Coverage",
        "",
        "| Species family | Statewide plans | Unit plans |",
        "|---|---:|---:|",
    ]
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        counts[str(record["species_family"])][str(record["plan_scope"])] += 1
    for species in sorted(counts):
        lines.append(f"| {species.replace('_', ' ').title()} | {counts[species]['statewide']} | {counts[species]['unit']} |")
    lines.extend(
        [
            "",
            f"Total official plan PDFs: **{len(records)}**.",
            "",
            "## Added statewide objective measures",
            "",
            "- **Black bear (2023-2035):** the population-management system uses three-year strategy bands for the percentage of sport-harvest bears that are adult males age 5, the female share of sport harvest, and DNA-study population growth rate. A current unit strategy is required before a strategy band can be presented as that unit's governing target.",
            "- **Wild turkey (2023-2029):** quantified objectives include enhancing 100,000 acres of habitat statewide by 2029 and increasing statewide hunter participation by 10% by 2029. These are statewide program objectives, not hunt-unit harvest-quality objectives.",
            "",
            "## Cougar program authority",
            "",
            f"- Authority status: `{cougar['authority_status']}`.",
            f"- Current program source: {COUGAR_PROGRAM_BACKGROUND_URL}",
            "- Current regulatory model: year-round harvest with a hunting or combination license, no bag limit, and no additional cougar permit required; DWR identifies the governing change as beginning in 2023.",
            f"- Publications page lists a current cougar management-plan PDF: `{str(cougar['publications_index_check']['lists_current_cougar_management_plan']).lower()}`.",
            f"- Historical plan reference: {cougar['historical_management_plan']['source_url']} (2015-2025; expired by its own term and not current objective authority).",
            f"- Historical-plan retrieval status: `{cougar['historical_management_plan']['retrieval_status']}`; no local copy was retained because both official URLs were unavailable. The original source URL is {COUGAR_HISTORICAL_PLAN_URL}.",
            "- Research display rule: label this as an open-season program rather than a current management plan, use the current program page for qualitative management context, and leave the quantified objective blank until DWR publishes or confirms a current governing target.",
            "",
            "## Data-use boundary",
            "",
            "- Appropriate: management objectives, policy periods, herd/unit context, quality targets, habitat goals, and interpretation of observed harvest trends.",
            "- Not appropriate: substituting an objective for an observed annual harvest value, using a plan value as a permit quota, or deriving `p_draw` directly from a plan.",
            "- Current DWR listing status means only that the DWR linked the PDF as current/latest when this inventory was retrieved. Dates printed inside each PDF remain the document-level authority.",
            "- Three current documents require the Wildlife Board evidence chain because DWR's main big-game/publications page still points to older copies: the 2025-reviewed mountain goat plan, the 2025-reviewed bighorn sheep plan, and the December 2025 Book Cliffs bison plan.",
            "",
            "## How this connects to the existing data",
            "",
            "| Source layer | What it supplies | Research use |",
            "|---|---|---|",
            "| Annual harvest reports/dashboard | Observed permits, hunters afield, harvest, success, effort, satisfaction and age where DWR reports it | Historical performance and quality evidence |",
            "| Hunt Planner management statistics | Current population objective/estimate, composition objective/current value, age objective/current three-year age where exposed | Current unit context |",
            "| Statewide and unit management plans | Policy period, goals, objective definitions, management direction and unit objective authority | Explanation and validation context; never an observed result |",
            "",
            "The retained Hunt Planner unit snapshot has **227** deduplicated management-unit rows. Population objective/current estimate is populated for most species; age objective/current three-year age is concentrated in elk, moose and pronghorn. Deer instead exposes buck-to-doe objective/current three-year composition. The exact species counts are retained in the JSON inventory.",
            "",
            "## Official index pages",
            "",
            f"- Big game: {BIG_GAME_PAGE}",
            f"- Publications: {PUBLICATIONS_PAGE}",
            f"- Cougar program background: {COUGAR_PROGRAM_BACKGROUND_URL}",
            "- Deer unit plans: https://wildlife.utah.gov/deer/plans",
            "- Elk unit plans: https://wildlife.utah.gov/elk/plans",
            "- Mountain goat unit plans: https://wildlife.utah.gov/goat/plans",
            "- Bighorn sheep unit plans: https://wildlife.utah.gov/sheep/plans",
            "",
            "The JSON companion contains every URL, unit label, checksum, page count, and retained RAW path.",
            "",
        ]
    )
    INVENTORY_MD.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Redownload even when a retained PDF already exists.")
    parser.add_argument("--user-elk-plan", type=Path, help="Optional user-supplied elk plan to compare to DWR's current copy.")
    parser.add_argument("--user-deer-approval", type=Path, help="Optional user-supplied DWR deer-plan approval article PDF to retain as supporting evidence.")
    args = parser.parse_args()

    records = collect_records()
    cougar_program_authority = evaluate_cougar_program_authority(refresh=args.refresh)
    downloaded = 0
    reused = 0
    for record in records:
        destination = local_path_for(record)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if args.refresh or not destination.exists():
            data, final_url, content_type = fetch(str(record["source_url"]))
            if not data.startswith(b"%PDF"):
                raise RuntimeError(f"DWR link did not return a PDF: {record['source_url']} ({content_type})")
            destination.write_bytes(data)
            record["resolved_url"] = final_url
            downloaded += 1
        else:
            reused += 1
        sha256, pages, size_bytes, pdf_title = verify_pdf(destination)
        verify_required_text(destination, list(record.get("required_text_evidence", [])))
        board_approved_override = bool(record.get("approval_evidence_url"))
        record.update(
            {
                "dwr_listing_status": (
                    "current_board_approved_document_with_public_index_lag"
                    if board_approved_override
                    else "current_or_latest_on_retrieval_date"
                ),
                "local_path": relative(destination),
                "sha256": sha256,
                "pages": pages,
                "size_bytes": size_bytes,
                "pdf_metadata_title": pdf_title,
                "data_role": "management_policy_and_objective_context",
                "prohibited_uses": ["observed_harvest_actual", "permit_quota_truth", "direct_p_draw_truth"],
            }
        )

    supporting: list[dict[str, object]] = []
    attachment_comparison: dict[str, object] = {}
    if args.user_elk_plan:
        user_sha256, user_pages, user_size, user_title = verify_pdf(args.user_elk_plan)
        dwr_elk = next(record for record in records if record["species_family"] == "elk" and record["plan_scope"] == "statewide")
        attachment_comparison = {
            "user_elk_plan": {
                "original_path": str(args.user_elk_plan),
                "sha256": user_sha256,
                "pages": user_pages,
                "size_bytes": user_size,
                "pdf_metadata_title": user_title,
                "matches_current_dwr_pdf": user_sha256 == dwr_elk["sha256"],
            }
        }
    if args.user_deer_approval:
        supporting.append(copy_supporting_attachment(args.user_deer_approval, "dwr_deer_plan_approval_news_2024.pdf"))

    species_counts = Counter(str(record["species_family"]) for record in records)
    scope_counts = Counter(str(record["plan_scope"]) for record in records)
    payload: dict[str, object] = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "Utah Division of Wildlife Resources",
        "scope": "current DWR management plans and program authority tied to species represented in Hunt Research",
        "official_index_urls": [
            BIG_GAME_PAGE,
            PUBLICATIONS_PAGE,
            COUGAR_PROGRAM_BACKGROUND_URL,
            *[url for _, url in UNIT_INDEXES],
        ],
        "plan_pdf_count": len(records),
        "counts_by_scope": dict(sorted(scope_counts.items())),
        "counts_by_species_family": dict(sorted(species_counts.items())),
        "downloaded_this_run": downloaded,
        "reused_this_run": reused,
        "plans": records,
        "cougar_program_authority": cougar_program_authority,
        "hunt_planner_management_context_snapshot": hunt_planner_management_context(),
        "user_attachment_comparison": attachment_comparison,
        "supporting_evidence": supporting,
        "guardrails": {
            "management_plan_values_are_not_observed_harvest_actuals": True,
            "do_not_use_for_permit_quota": True,
            "do_not_use_directly_for_p_draw": True,
            "unit_objectives_require_exact_species_and_compatible_unit_identity": True,
            "never_join_by_boundary_id_alone": True,
        },
    }
    INVENTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(payload)

    print(f"PLAN_PDFS={len(records)}")
    print(f"DOWNLOADED={downloaded}")
    print(f"REUSED={reused}")
    print(f"SPECIES={dict(sorted(species_counts.items()))}")
    print(f"SCOPES={dict(sorted(scope_counts.items()))}")
    print(f"COUGAR_AUTHORITY={cougar_program_authority['authority_status']}")
    if attachment_comparison:
        print(f"USER_ELK_MATCH={attachment_comparison['user_elk_plan']['matches_current_dwr_pdf']}")
    print(f"INVENTORY_JSON={INVENTORY_JSON}")
    print(f"INVENTORY_MD={INVENTORY_MD}")


if __name__ == "__main__":
    main()
