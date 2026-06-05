from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_GITIGNORE_LINES = {
    "pipeline/RAW/**",
    "pipeline/INGEST/inbox/**",
    "pipeline/INGEST/archive/**",
    "pipeline/R2_OFFLOAD/incoming/**",
    "pipeline/R2_OFFLOAD/uploaded/**",
    "!pipeline/R2_OFFLOAD/manifests/**",
    "data_model/harvest_quality/**/*.csv",
    "data_model/runtime_drafts/**/*.json",
    "data_truth/comparison_outputs/**/*.csv",
    "*.zip",
    "*.pdf",
    "*.xlsx",
    "*.sqlite",
    "!processed_data/public_contracts/*.json",
    "!pages-dist/processed_data/public_contracts/*.json",
}

REQUIRED_FILES = {
    ".githooks/pre-commit",
    "tools/git_size_guard.py",
    "tools/install_repo_hygiene_hooks.ps1",
    "tools/upload_r2_incoming.ps1",
    "docs/repo_data_hygiene.md",
}


def main() -> int:
    gitignore_path = ROOT / ".gitignore"
    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    gitignore_lines = {line.strip() for line in gitignore_text.splitlines() if line.strip()}

    missing_lines = sorted(REQUIRED_GITIGNORE_LINES - gitignore_lines)
    missing_files = sorted(path for path in REQUIRED_FILES if not (ROOT / path).is_file())

    if missing_lines or missing_files:
        print("Repo hygiene check failed.")
        if missing_lines:
            print("\nMissing .gitignore rules:")
            for line in missing_lines:
                print(f"- {line}")
        if missing_files:
            print("\nMissing required files:")
            for path in missing_files:
                print(f"- {path}")
        return 1

    print("OK: repo hygiene rules and helper files are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
