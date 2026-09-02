#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

python3 scripts/validate_specs.py
python3 scripts/validate_brand_profile.py config/brand.env.example
python3 scripts/validate_bundled_plugins.py config/bundled-plugins.lock.json
for manifest in release-manifests/*.candidate.json; do
  python3 scripts/validate_release_manifest.py "$manifest"
done
python3 scripts/validate_workflows.py
python3 -m unittest -v \
  tests.test_governance \
  tests.test_contributor_skills \
  tests.test_bundled_plugins
git diff --check
git diff --cached --check

echo "repository checks passed"
