"""Retain only non-secret Pages deployment identity and exact asset manifest."""
import argparse
import json
import os
import tomllib
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-current-production", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite retained deployment evidence")
    auth_path = Path(os.environ["APPDATA"]) / "xdg.config/.wrangler/config/default.toml"
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or tomllib.loads(auth_path.read_text())["oauth_token"]
    if args.require_current_production or args.deployment == "current":
        project_url = "https://api.cloudflare.com/client/v4/accounts/cd6d0adbdac9690cdae5f1c6d52aaa9b/pages/projects/huntbuilder"
        project_request = urllib.request.Request(project_url, headers={"Authorization": f"Bearer {token}"})
        project = json.load(urllib.request.urlopen(project_request, timeout=30))
        current = project.get("result", {}).get("canonical_deployment", {}).get("id")
        if args.deployment == "current" and project.get("success") and current:
            args.deployment = current
        if not project.get("success") or current != args.deployment:
            raise SystemExit(f"Production deployment changed: expected {args.deployment}, current {current}")
    url = f"https://api.cloudflare.com/client/v4/accounts/cd6d0adbdac9690cdae5f1c6d52aaa9b/pages/projects/huntbuilder/deployments/{args.deployment}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    response = json.load(urllib.request.urlopen(request, timeout=30))
    if not response.get("success"):
        raise SystemExit("Cloudflare deployment read failed")
    result = response["result"]
    safe = {key: result.get(key) for key in ("id", "url", "environment", "created_on", "files", "uses_functions")}
    if safe["uses_functions"] or not isinstance(safe["files"], dict):
        raise SystemExit("Static-only release snapshot cannot preserve this deployment")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"id": safe["id"], "files": len(safe["files"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
