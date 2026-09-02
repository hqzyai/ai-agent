#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_REMOTE="hermes"
UPSTREAM_URL="https://github.com/NousResearch/hermes-agent.git"
HERMES_VERSION="${1:?usage: start-merge.sh HERMES_VERSION UPSTREAM_TAG CALVER [BASE_BRANCH]}"
UPSTREAM_TAG="${2:?usage: start-merge.sh HERMES_VERSION UPSTREAM_TAG CALVER [BASE_BRANCH]}"
CALVER="${3:?usage: start-merge.sh HERMES_VERSION UPSTREAM_TAG CALVER [BASE_BRANCH]}"
BASE_BRANCH="${4:-main}"
TARGET_BRANCH="ai-agent/hermes-v${HERMES_VERSION}-${CALVER}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SPEC_DIR="${SKILL_DIR}/references"

fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

[[ "$HERMES_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$ ]] || fail "invalid Hermes version: ${HERMES_VERSION}"
[[ "$CALVER" =~ ^20[0-9]{2}\.(0[1-9]|1[0-2])\.([0-2][0-9]|3[01])$ ]] || fail "CALVER must be YYYY.MM.DD"
[[ "$UPSTREAM_TAG" =~ ^v[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2}([.][0-9]+)?$ ]] || fail "invalid official release tag: ${UPSTREAM_TAG}"

git rev-parse --show-toplevel >/dev/null 2>&1 || fail "run this script inside the AgentOS source repository"
test "$(git rev-parse --is-shallow-repository)" = "false" || fail "shallow checkout is unsupported; fetch complete product history before syncing"
for spec in 00-README.md brand-profile.md 01-feature-inventory.md 02-auth-and-remote-gateway.md 03-chat-media-artifacts.md 04-cron-messaging-i18n-ui.md 05-offline-packaging-and-ci.md 06-ai-agent-migration-checklist.md spec-map.md; do
  test -s "${SPEC_DIR}/${spec}" || fail "bundled specification is missing: ${SPEC_DIR}/${spec}"
done
git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1 && fail "a merge is already active"
test -z "$(git status --porcelain)" || fail "worktree must be clean"
test -n "$(git branch --show-current)" || fail "detached HEAD is not a valid merge base"
git rev-parse --verify "${BASE_BRANCH}" >/dev/null 2>&1 || fail "base branch does not exist: ${BASE_BRANCH}"
git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}" && fail "target branch already exists: ${TARGET_BRANCH}"

if git remote get-url "${UPSTREAM_REMOTE}" >/dev/null 2>&1; then
  git remote set-url "${UPSTREAM_REMOTE}" "${UPSTREAM_URL}" || fail "could not pin official upstream remote"
else
  git remote add "${UPSTREAM_REMOTE}" "${UPSTREAM_URL}" || fail "could not add official upstream remote"
fi
test "$(git remote get-url "${UPSTREAM_REMOTE}")" = "${UPSTREAM_URL}" || fail "official upstream URL was not applied"

git fetch --no-tags "${UPSTREAM_REMOTE}" "refs/tags/${UPSTREAM_TAG}:refs/tags/${UPSTREAM_TAG}" || fail "official upstream tag fetch failed; no fallback is allowed"
TAG_OBJECT_SHA="$(git rev-parse "refs/tags/${UPSTREAM_TAG}")"
UPSTREAM_SHA="$(git rev-parse "refs/tags/${UPSTREAM_TAG}^{}")"

git switch "${BASE_BRANCH}"
git switch -c "${TARGET_BRANCH}" || fail "could not create ${TARGET_BRANCH}"
printf 'base_branch=%s\ntarget_branch=%s\nupstream_tag=%s\nupstream_tag_object_sha=%s\nupstream_commit_sha=%s\n' \
  "${BASE_BRANCH}" "${TARGET_BRANCH}" "${UPSTREAM_TAG}" "${TAG_OBJECT_SHA}" "${UPSTREAM_SHA}"

set +e
git merge --no-ff --no-commit "${UPSTREAM_SHA}"
merge_status=$?
set -e
if [[ ${merge_status} -eq 0 ]]; then
  printf 'merge staged without conflicts; audit AgentOS contracts before committing\n'
  exit 0
fi
if git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
  printf 'merge is active with conflicts; resolve them against the AgentOS specifications\n' >&2
  exit 2
fi
fail "merge failed before Git created a merge state"
