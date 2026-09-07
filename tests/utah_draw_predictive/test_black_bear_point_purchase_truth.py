from __future__ import annotations

import pytest

from scripts.extract_black_bear_point_purchase_truth import extract_year, parse_purchase_page


def test_parse_purchase_page_preserves_blank_dwr_cells_as_zero() -> None:
    rows, totals = parse_purchase_page(
        """Bonus Resident Nonresident
Points Applicants Applicants
3 12 2
2 9
1
0 25 4
Totals 46 Totals 6
"""
    )

    assert rows == {3: (12, 2), 2: (9, 0), 1: (0, 0), 0: (25, 4)}
    assert totals == (46, 6)


def test_parse_purchase_page_requires_published_totals() -> None:
    with pytest.raises(ValueError, match="Totals"):
        parse_purchase_page("0 5 1")


def test_parse_purchase_page_supports_older_repeated_point_layout() -> None:
    rows, totals = parse_purchase_page(
        """Total Total
Points Applicants Points Applicants
3 12 3 2
2 9 2
1 1
0 25 0 4
Totals 46 Totals 6
"""
    )

    assert rows == {3: (12, 2), 2: (9, 0), 1: (0, 0), 0: (25, 4)}
    assert totals == (46, 6)


@pytest.mark.parametrize(
    ("year", "page", "resident_total", "nonresident_total"),
    [
        (2018, 8, 4143, 478),
        (2025, 1, 4661, 453),
    ],
)
def test_retained_official_bear_purchase_pages_reconcile(
    year: int,
    page: int,
    resident_total: int,
    nonresident_total: int,
) -> None:
    records, summary = extract_year(year)

    assert summary["pdf_page"] == page
    assert summary["resident_total"] == resident_total
    assert summary["nonresident_total"] == nonresident_total
    assert sum(int(row["point_purchase_applicants"]) for row in records if row["residency"] == "Resident") == resident_total
    assert sum(int(row["point_purchase_applicants"]) for row in records if row["residency"] == "Nonresident") == nonresident_total
