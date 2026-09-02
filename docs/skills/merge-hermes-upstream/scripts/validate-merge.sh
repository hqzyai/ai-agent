#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_URL="https://github.com/NousResearch/hermes-agent.git"
HERMES_VERSION="${1:?usage: validate-merge.sh HERMES_VERSION UPSTREAM_TAG CALVER}"
UPSTREAM_TAG="${2:?usage: validate-merge.sh HERMES_VERSION UPSTREAM_TAG CALVER}"
CALVER="${3:?usage: validate-merge.sh HERMES_VERSION UPSTREAM_TAG CALVER}"
EXPECTED_BRANCH="ai-agent/hermes-v${HERMES_VERSION}-${CALVER}"
BRANCH="$(git branch --show-current)"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SPEC_DIR="${SKILL_DIR}/references"

fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

[[ "$HERMES_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$ ]] || fail "invalid Hermes version"
[[ "$CALVER" =~ ^20[0-9]{2}\.(0[1-9]|1[0-2])\.([0-2][0-9]|3[01])$ ]] || fail "invalid CALVER"
[[ "$UPSTREAM_TAG" =~ ^v[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2}([.][0-9]+)?$ ]] || fail "invalid official release tag"

for spec in 00-README.md brand-profile.md 01-feature-inventory.md 02-auth-and-remote-gateway.md 03-chat-media-artifacts.md 04-cron-messaging-i18n-ui.md 05-offline-packaging-and-ci.md 06-ai-agent-migration-checklist.md spec-map.md; do
  test -s "${SPEC_DIR}/${spec}" || fail "bundled specification is missing: ${SPEC_DIR}/${spec}"
done
test "${BRANCH}" = "${EXPECTED_BRANCH}" || fail "current branch must be ${EXPECTED_BRANCH}, got ${BRANCH}"
test "$(git remote get-url hermes)" = "${UPSTREAM_URL}" || fail "hermes remote is not the official upstream"
git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1 && fail "merge is still active"
test -z "$(git diff --name-only --diff-filter=U)" || fail "unresolved merge paths remain"

git fetch --no-tags hermes "refs/tags/${UPSTREAM_TAG}:refs/tags/${UPSTREAM_TAG}" || fail "could not refresh official release tag"
UPSTREAM_SHA="$(git rev-parse "refs/tags/${UPSTREAM_TAG}^{}")"
git merge-base --is-ancestor "${UPSTREAM_SHA}" HEAD || fail "official ${UPSTREAM_TAG} commit is not an ancestor of HEAD"

git diff --check
bash "${SKILL_DIR}/scripts/audit-agentos-contracts.sh"
printf 'official Hermes %s merge validation passed on %s\n' "${UPSTREAM_TAG}" "${BRANCH}"
