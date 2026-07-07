# 2017 Draw-Result Naming And Collision Policy

This policy governs all 2017 draw-result source files, their extracted helpers, and
the alias-manifest rows that map them into the scoring engine.

The goal is simple:

- one filename standard
- one collision rule
- one source-of-truth layer
- no silent renames or overwrites

## Scope

This policy applies to:

- raw 2017 draw-result PDFs
- extracted CSV/XLSX helpers derived from those PDFs
- `data_truth/draw_results_truth/source_file_aliases/2017_PERMITS=2018_MODEL_source_alias_manifest.csv`
- any 2017 source promotion into the prediction engine

It does not change the underlying historical truth. It only standardizes how the
repo names, stores, and promotes those files.

## Source Identity

The filename is not the identity.

The authoritative identity is the combination of:

- `source_year`
- `target_year`
- `canonical_source_value`
- `source_family`
- `source_role`
- `sha256`

If those disagree with the on-disk filename, the manifest wins.

## Canonical 2017 Filename Standard

All new standardized 2017 draw-result PDFs must use:

```text
2017_PERMITS=2018_MODEL__NORMALIZED_TITLE.pdf
```

Normalization rules for `NORMALIZED_TITLE`:

- uppercase everything
- convert spaces, slashes, and hyphens to single underscores
- strip punctuation where possible
- keep official abbreviations when they are part of the published title or are
  required for clarity, especially `L.E.`, `O.I.L.`, `D.H.`, and `G.S.`
- collapse repeated underscores
- do not guess alternate family names
- do not invent a cleaner title than the published one unless the source itself
  is already an extracted helper or a clearly derived subset

Examples:

- `2017_PERMITS=2018_MODEL__TURKEY_DRAW_RESULTS.pdf`
- `2017_PERMITS=2018_MODEL__SPORTSMAN_DRAW_RESULTS.pdf`
- `2017_PERMITS=2018_MODEL__G.S._BUCK_DEER_DRAW_RESULTS.pdf`
- `2017_PERMITS=2018_MODEL__L.E._DEER_DRAW_RESULTS.pdf`

If a file already exists under a legacy name, keep the legacy file only until the
alias manifest and standardized path are aligned. Do not create a second silent
identity for the same source.

## Folder Roles

Use folder structure to separate source roles:

- canonical active sources: `raw_pdfs/2017_PERMITS=2018_MODEL/`
- parent/master files: `raw_pdfs/2017_PERMITS=2018_MODEL/Parent Files/`
- derived subfiles: `raw_pdfs/2017_PERMITS=2018_MODEL/Derived/`
- duplicate or retired copies: `raw_pdfs/2017_PERMITS=2018_MODEL/_duplicate_archive/`

The folder role is part of the hygiene story, but not part of the truth key.

## Collision Policy

When two files want the same standardized name:

1. Compare `sha256`.
2. If the hash matches, keep one active copy and archive the rest as duplicates.
3. If the hash differs, do not overwrite either file.
4. Choose the active file by source hierarchy:
   - official truth-source PDF
   - verified extracted subset from the official PDF
   - derived helper file
   - duplicate/archive copy
5. Record both files in the alias manifest if both are meaningful.
6. If only one file is meant to score, set `active_for_scoring = True` only on
   that row.
7. If a file is only a supporting parent or a display helper, keep it out of the
   scoring lane even if it shares the family name.

If two files have the same title but different content and the repo cannot prove
which one is authoritative, the safe state is:

- preserve both files
- mark the ambiguous one `review_required`
- do not promote either one as a clean scoring source until reviewed

## Promotion Rule

A 2017 file may be promoted toward runtime only when all of the following are true:

- it has a validated standardized path
- it has a matching alias-manifest row
- the row has the correct `source_family`
- the row has the correct `source_role`
- the row is marked `active_for_scoring = True`
- the row has a validated `sha256`
- the file is a real published source or a faithful extracted subset

Promotion must never invent a source that was not actually published.

In particular:

- if 2017 only published a bonus turkey draw-results source, do not fabricate a
  separate `youth_turkey` source file
- if a family is absorbed into another published row set, keep the family map in
  the manifest rather than making up a new on-disk file

## 2017 Family Examples

Historical-source-backed families that should remain manifest-driven:

- `preference_general_deer`
- `dedicated_hunter`
- `preference_antlerless_deer`
- `preference_antlerless_elk`
- `preference_doe_pronghorn`
- `sportsman`
- `bonus_bear`
- `bonus_turkey`
- `youth_draw`
- `cougar`

Special handling:

- `sportsman` is random-only and must not be given point-ladder semantics
- `bonus_turkey` stays tied to the published 2017 turkey draw-results source
- `youth_turkey` must not be synthesized unless a separate 2017 source file is
  actually found

## Manifest Rule

The alias manifest is the operational truth layer for file routing.

Required columns:

- `source_year`
- `target_year`
- `canonical_source_value`
- `standardized_raw_pdf_relative_path`
- `source_family`
- `source_role`
- `active_for_scoring`
- `sha256`

If a standardized path changes, update the manifest first and keep a backup if a
truth file is being rewritten.

## Reconciliation Checklist

Before calling a 2017 file set clean, verify:

- every active source has exactly one manifest row
- every duplicate has a known archive or derived role
- no two active rows point to the same unnamed collision target
- no file was promoted only because its filename looked convenient
- no missing family was filled by invention instead of source evidence
- the scoring engine uses the manifest and source role, not filename luck

## Non-Negotiables

- Do not overwrite a source file just because the normalized name collides.
- Do not create a second canonical identity for the same source.
- Do not promote a family without a real source document.
- Do not let derived helpers masquerade as published truth.
- Do not use filename cleanliness as a substitute for source evidence.

