import csv
import json
import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OutfitterDirectoryPromotionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        local_dir = ROOT / "local_data" / "outfitters"
        cls.master_path = local_dir / "outfitters-master.internal.json"
        cls.evidence_path = local_dir / "outfitter-federal-service-area-evidence.internal.json"
        cls.coverage_path = local_dir / "outfitter-federal-unit-coverage-review.internal.json"
        cls.master = json.loads(cls.master_path.read_text(encoding="utf-8")) if cls.master_path.exists() else None
        cls.evidence = json.loads(cls.evidence_path.read_text(encoding="utf-8")) if cls.evidence_path.exists() else None
        cls.coverage = json.loads(cls.coverage_path.read_text(encoding="utf-8")) if cls.coverage_path.exists() else None
        cls.public_coverage = json.loads(
            (ROOT / "processed_data" / "outfitter-federal-unit-coverage-review.json").read_text(
                encoding="utf-8"
            )
        )
        cls.manifest = json.loads(
            (ROOT / "data" / "outfitter-internal-master-manifest.json").read_text(encoding="utf-8")
        )
        cls.manti_lasal_authority = json.loads(
            (
                ROOT
                / "data"
                / "source-evidence"
                / "manti-la-sal-permitted-hunting-outfitters-2026.json"
            ).read_text(encoding="utf-8")
        )
        cls.fishlake_authority = json.loads(
            (
                ROOT
                / "data"
                / "source-evidence"
                / "fishlake-permitted-hunting-outfitters-2025.json"
            ).read_text(encoding="utf-8")
        )
        cls.public = json.loads((ROOT / "data" / "outfitters-public.json").read_text(encoding="utf-8"))
        cls.versioned_master = json.loads(
            (ROOT / "data" / "outfitters-master.json").read_text(encoding="utf-8")
        )
        cls.root_canonical = json.loads(
            (ROOT / "hunt-master-canonical-2026.json").read_text(encoding="utf-8")
        )
        cls.logo_sources = json.loads(
            (ROOT / "data" / "logo-sourcing-approved.json").read_text(encoding="utf-8")
        )

    def test_internal_master_contains_only_named_hunting_businesses(self):
        if self.master is None:
            self.skipTest("local ignored internal master is not present")
        self.assertEqual(len(self.master), 138)
        self.assertEqual(len({row["id"] for row in self.master}), 138)
        self.assertTrue(all(row["displayName"] for row in self.master))
        self.assertTrue(all(row["services"]["guidedHunts"] for row in self.master))

    def test_review_status_is_preserved_separately(self):
        if self.master is None:
            self.skipTest("local ignored internal master is not present")
        self.assertEqual(
            Counter(row["reviewStatus"] for row in self.master),
            Counter({"Spreadsheet Only": 72, "Needs Verification": 59, "Confirmed": 7}),
        )
        self.assertTrue(all(row["reviewStatus"] == row["internal"]["spreadsheetReviewStatus"] for row in self.master))
        self.assertTrue(any(row["reviewStatus"] == "Confirmed" and row["verificationStatus"] == "Vetted" for row in self.master))
        self.assertTrue(any(row["reviewStatus"] == "Needs Verification" and row["verificationStatus"] == "Vetted" for row in self.master))

    def test_unit_eligibility_requires_confirmed_permit_area_intersection(self):
        if self.master is None or self.evidence is None:
            self.skipTest("local ignored internal outfitter artifacts are not present")
        qualifying = [row for row in self.master if row["serviceArea"]["unitsServed"]]
        self.assertEqual(len(qualifying), 70)
        self.assertTrue(
            all(
                row["internal"]["federalPermitEvidenceStatus"] == "Confirmed"
                and all(
                    item["status"]
                    in {
                        "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT",
                        "CONFIRMED_OUTFITTER_SERVICE_CLAIM",
                    }
                    for item in row["internal"]["unitServiceEligibility"]
                )
                for row in qualifying
            )
        )
        self.assertEqual(
            sum(len(row["internal"]["unitServiceEligibility"]) for row in self.master),
            7639,
        )
        self.assertEqual(
            sum(
                item["status"] == "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
                for row in qualifying
                for item in row["internal"]["unitServiceEligibility"]
            ),
            6,
        )
        self.assertEqual(self.evidence["metadata"]["spreadsheetFederalEvidenceRecords"], 79)
        self.assertEqual(self.evidence["metadata"]["authoritativePermitEvidenceRecords"], 60)
        self.assertEqual(len(self.evidence["records"]), 80)
        self.assertEqual(
            Counter(row["unitServiceClaimStatus"] for row in self.evidence["records"]),
            Counter(
                {
                    "NO_FEDERAL_PERMIT_AREA_INTERSECTION": 10,
                    "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT": 69,
                    "CONFIRMED_OUTFITTER_SERVICE_CLAIM": 1,
                }
            ),
        )

    def test_manti_lasal_authority_augments_service_area_without_reclassifying_contacts(self):
        if self.master is None:
            self.skipTest("local ignored internal master is not present")
        authority_records = self.manti_lasal_authority["records"]
        self.assertEqual(len(authority_records), 19)
        self.assertEqual(len(self.manti_lasal_authority["unresolved"]), 2)
        master_by_id = {row["id"]: row for row in self.master}
        for authority in authority_records:
            record = master_by_id[authority["outfitterId"]]
            expected_district = (
                "manti-la-sal-north-zone"
                if authority["zone"] == "North Zone"
                else "manti-la-sal-south-zone"
            )
            self.assertIn(expected_district, record["serviceArea"]["usfsDistrictIds"])
            self.assertNotIn("manti-la-sal", record["serviceArea"]["usfsForestIds"])
            self.assertEqual(record["reviewStatus"], record["internal"]["spreadsheetReviewStatus"])
            self.assertEqual(
                record["internal"]["authoritativeFederalPermitEvidence"][0]["claim"],
                "CURRENT_FOREST_SERVICE_PERMIT_HOLDER",
            )

    def test_fishlake_authority_uses_name_matches_and_whole_forest_scope(self):
        if self.master is None:
            self.skipTest("local ignored internal master is not present")
        authority_records = self.fishlake_authority["records"]
        self.assertEqual(len(authority_records), 41)
        self.assertEqual(len(self.fishlake_authority["unresolved"]), 1)
        master_by_id = {row["id"]: row for row in self.master}
        for authority in authority_records:
            record = master_by_id[authority["outfitterId"]]
            self.assertIn("fishlake", record["serviceArea"]["usfsForestIds"])
            self.assertEqual(record["reviewStatus"], record["internal"]["spreadsheetReviewStatus"])
            source_ids = {
                item["sourceId"]
                for item in record["internal"]["authoritativeFederalPermitEvidence"]
            }
            self.assertIn("fishlake-permitted-hunting-outfitters-2025", source_ids)
        self.assertEqual(
            {
                row["officialPermitHolderName"]
                for row in self.fishlake_authority["unresolved"]
            },
            {"Chunky Trout Outfitter"},
        )

    def test_crosswalk_records_measured_geometric_coverage(self):
        if self.coverage is None:
            self.skipTest("local ignored coverage artifact is not present")
        self.assertEqual(len(self.coverage), 761)
        self.assertTrue(
            all(row["CoverageRelationship"] == "FEDERAL_PERMIT_AREA_GEOMETRIC_OVERLAP" for row in self.coverage)
        )
        self.assertEqual(
            Counter(row["UnitServiceClaimStatus"] for row in self.coverage),
            Counter(
                {
                    "INELIGIBLE_EXISTING_CROSSWALK_RULE": 284,
                    "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT": 348,
                    "NO_FEDERAL_PERMIT_AREA_INTERSECTION": 110,
                    "NOT_CALCULATED_NO_EXACT_DWR_BOUNDARY_MATCH": 13,
                    "CONFIRMED_OUTFITTER_SERVICE_CLAIM": 6,
                }
            ),
        )
        self.assertEqual(
            sum(row["UnitBoundaryMatchStatus"] == "MATCHED_EXACT_NAME_OR_HUNT_CODE" for row in self.coverage),
            464,
        )
        for row in self.coverage:
            for detail in row["FederalPermitCoverageDetails"]:
                if detail["authorizedByFederalPermitAreaOverlap"]:
                    self.assertGreaterEqual(detail["coveredUnitAreaAcres"], 0.1)
                    self.assertEqual(detail["permitEvidenceReviewStatus"], "Confirmed")
        self.assertTrue(all("only on the permitted federal land" in row["Notes"] for row in self.coverage))

    def test_public_feed_keeps_vetted_contacts_and_name_only_permit_profiles(self):
        self.assertEqual(len(self.public), 74)
        self.assertEqual(
            Counter(row["verificationStatus"] for row in self.public),
            Counter({"Vetted": 11, "Permit Confirmed": 63}),
        )
        permit_only = [row for row in self.public if row["verificationStatus"] == "Permit Confirmed"]
        self.assertTrue(
            all(
                not row["website"]
                and not row["phone"]
                and not row["email"]
                and not row["city"]
                and not row["ownerName"]
                for row in permit_only
            )
        )
        public_names = {row["listingName"] for row in self.public}
        coverage_names = {
            name
            for row in self.public_coverage
            for name in row["FederalPermitMatchedOutfitters"]
        }
        self.assertEqual(len(self.public_coverage), 354)
        self.assertEqual(
            sum(row["FederalPermitMatchedOutfitterCount"] for row in self.public_coverage),
            7639,
        )
        self.assertEqual(len(coverage_names), 70)
        self.assertTrue(coverage_names.issubset(public_names))

    def test_runtime_coverage_lookup_uses_unit_name_fallback(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("if (!hunt || isPrivateLandOnlyRecord(hunt)) return null;", app)
        self.assertIn("const unitCandidates = [getUnitCode(hunt), ...getBoundaryNamesForHunt(hunt)];", app)
        self.assertIn("speciesCandidates.push('Bighorn Sheep')", app)

        coverage = next(
            row
            for row in self.public_coverage
            if row["Species"] == "Elk" and row["UnitName"] == "Manti"
        )
        with (ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            hunt = next(row for row in csv.DictReader(handle) if row["hunt_code"] == "EB3006")

        normalize = lambda value: re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
        self.assertNotEqual(normalize(hunt["boundary_id"]), normalize(coverage["UnitCode"]))
        self.assertEqual(normalize(hunt["hunt_name"]), normalize(coverage["UnitName"]))

    def test_public_repository_master_is_vetted_hunting_only(self):
        for records in (self.versioned_master, self.root_canonical["outfitters"]):
            self.assertEqual(len(records), 9)
            self.assertTrue(all(row["verificationStatus"] == "Vetted" for row in records))
            self.assertTrue(all(row["services"]["guidedHunts"] for row in records))
            self.assertTrue(all(row["headquarters"]["mailingAddress"] == "" for row in records))
            self.assertTrue(all("internal" not in row for row in records))

        fishing_ids = {
            "outfitter-all-seasons-adventures",
            "outfitter-fried-feathers",
            "outfitter-trout-creek-flies",
            "outfitter-utah-s-best-guides",
            "outfitter-wasatch-adventure-guides-llc",
            "outfitter-wasatch-guide-service",
        }
        self.assertTrue(fishing_ids.isdisjoint(row["id"] for row in self.logo_sources))

    def test_versioned_manifest_records_internal_promotion_without_private_rows(self):
        self.assertEqual(self.manifest["counts"]["promotedHuntingBusinesses"], 138)
        self.assertEqual(
            self.manifest["counts"]["reviewStatus"],
            {"Confirmed": 7, "Needs Verification": 59, "Spreadsheet Only": 72},
        )
        self.assertEqual(self.manifest["counts"]["coverageRows"], 761)
        self.assertEqual(self.manifest["counts"]["exactBoundaryRows"], 464)
        self.assertEqual(self.manifest["counts"]["authorizedCoverageRows"], 354)
        self.assertEqual(self.manifest["counts"]["authorizedOutfitters"], 70)
        self.assertEqual(self.manifest["counts"]["effectiveOutfitterUnitSpeciesAssociations"], 7639)
        self.assertEqual(self.manifest["counts"]["legacy75PercentCoverageRows"], 26)
        self.assertEqual(self.manifest["counts"]["publicCoverageRows"], 354)
        self.assertEqual(self.manifest["counts"]["publicCoverageOutfitters"], 70)
        self.assertEqual(self.manifest["counts"]["publicRepositoryMasterBusinesses"], 9)
        self.assertIn("Git-ignored", self.manifest["metadata"]["privacyBoundary"])
        self.assertIn("/local_data/outfitters/*", (ROOT / ".gitignore").read_text(encoding="utf-8"))

    def test_spatial_builder_reuses_the_entry_map_sources(self):
        script = (ROOT / "scripts" / "build_outfitter_unit_service_eligibility.py").read_text(encoding="utf-8")
        config = (ROOT / "config.js").read_text(encoding="utf-8")
        for service in (
            "EDW_ForestSystemBoundaries_01/MapServer/0",
            "BLM_UT_ADMU/FeatureServer/0",
            "BLM_UT_SMA/FeatureServer/0",
        ):
            self.assertIn(service, script)
            self.assertIn(service, config)
        self.assertIn("EDW_RangerDistricts_01/MapServer/0", script)


if __name__ == "__main__":
    unittest.main()
