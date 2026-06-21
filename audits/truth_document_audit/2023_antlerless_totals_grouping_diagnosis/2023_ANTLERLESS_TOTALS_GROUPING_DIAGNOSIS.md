# 2023 Antlerless Totals Grouping Diagnosis

The large 2023 antlerless mismatch is not primarily a PDF numeric extraction failure. It is a grouping-key failure introduced when computed totals were built from point rows using only `hunt_code + model_year + residency`.

Adult antlerless and youth antlerless reuse the same DA/EA/PD hunt codes. For example, `DA1001 Resident` adult PDF total is 87 applicants / 23 permits, but the computed total became 94 / 29 because youth DA1001 rows were added too.

Rows examined: 408

Issue counts: {'CHECK_PARSER_OR_SOURCE_MAPPING': 180, 'GROUPING_COLLAPSED_ADULT_AND_YOUTH_SHARED_HUNT_CODE': 228}

Adult-source-matches-PDF counts: {'TRUE': 408}

Collapsed-key-matches-PDF counts: {'TRUE': 180, 'FALSE': 228}

Required fix: totals restoration must group by `year + model_year + hunt_code + residency + source family/report family`, not just `hunt_code + model_year + residency`.
