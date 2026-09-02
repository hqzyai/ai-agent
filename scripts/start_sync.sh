#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_URL="https://github.com/NousResearch/hermes-agent.git"
HERMES_VERSION="${1:?usage: start_sync.sh HERMES_VERSION UPSTREAM_TAG CALVER [BASE_BRANCH]}"
UPSTREAM_TAG="${2:?usage: start_sync.sh HERMES_VERSION UPSTREAM_TAG CALVER [BASE_BRANCH]}"
CALVER="${3:?usage: start_sync.sh HERMES_VERSION UPSTREAM_TAG CALVER [BASE_BRANCH]}"
BASE_BRANCH="${4:-main}"
TARGET_BRANCH="ai-agent/hermes-v${HERMES_VERSION}-${CALVER}"

[[ "$HERMES_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$ ]] || {
  echo "error: invalid Hermes version: $HERMES_VERSION" >&2
  exit 1
}
[[ "$CALVER" =~ ^20[0-9]{2}\.(0[1-9]|1[0-2])\.([0-2][0-9]|3[01])$ ]] || {
  echo "error: CALVER must be YYYY.MM.DD: $CALVER" >&2
  exit 1
}

git rev-parse --show-toplevel >/dev/null
test "$(git rev-parse --is-shallow-repository)" = "false" || {
  echo "error: shallow checkout is unsupported; fetch complete product history before syncing" >&2
  exit 1
}
test -z "$(git status --porcelain)" || { echo "error: worktree must be clean" >&2; exit 1; }
test -z "$(git branch --show-current)" && { echo "error: detached HEAD" >&2; exit 1; }
git rev-parse --verify "$BASE_BRANCH" >/dev/null

if git remote get-url hermes >/dev/null 2>&1; then
  git remote set-url hermes "$UPSTREAM_URL"
else
  git remote add hermes "$UPSTREAM_URL"
fi
test "$(git remote get-url hermes)" = "$UPSTREAM_URL"

git fetch --no-tags hermes "refs/tags/${UPSTREAM_TAG}:refs/tags/${UPSTREAM_TAG}"
UPSTREAM_SHA="$(git rev-parse "refs/tags/${UPSTREAM_TAG}^{}")"
test "$(git show -s --format='%s' "$UPSTREAM_SHA")" != "" || { echo "error: empty upstream commit" >&2; exit 1; }

if git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
  echo "error: target branch already exists: ${TARGET_BRANCH}" >&2
  exit 1
fi

git switch "$BASE_BRANCH"
git switch -c "$TARGET_BRANCH"

echo "target_branch=${TARGET_BRANCH}"
echo "upstream_tag=${UPSTREAM_TAG}"
echo "upstream_sha=${UPSTREAM_SHA}"

set +e
git merge --no-ff --no-commit "$UPSTREAM_SHA"
merge_status=$?
set -e
if [[ $merge_status -eq 0 ]]; then
  echo "merge staged cleanly; run contract and test suites before committing"
  exit 0
fi
if git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
  echo "merge active with conflicts; resolve semantically, then run acceptance" >&2
  exit 2
fi
echo "error: merge failed before creating a merge state" >&2
exit 1
