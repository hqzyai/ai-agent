---
name: merge-hermes-upstream
description: Use when synchronizing an official Hermes release into AgentOS, creating an ai-agent/hermes-v* branch, resolving upstream conflicts, or preparing the corresponding pull request.
---

# Merge Official Hermes Upstream

Merge one immutable release tag from `https://github.com/NousResearch/hermes-agent.git` while preserving the AgentOS product contracts bundled with this skill.

## Fixed contracts

- Accept only the official repository and an exact upstream release tag. Never substitute `origin/main`, local `main`, a mirror, or the moving `hermes/main` branch.
- Derive product version `v<hermes>-YYYY.MM.DD` and branch `ai-agent/hermes-v<hermes>-YYYY.MM.DD` from explicit inputs.
- Start from a clean, full-history worktree and an explicit base branch. Shallow clones are rejected because they can hide the shared upstream ancestry and produce a false unrelated-history failure. Do not mix contributor changes into the merge or hide them in an implicit stash.
- Resolve conflicts semantically: retain upstream architecture and fixes, then reapply AgentOS behavior.
- Read `references/00-README.md`, `references/brand-profile.md`, `references/bundled-plugins.md`, `references/06-ai-agent-migration-checklist.md`, and `references/spec-map.md` before resolving conflicts or accepting automatic merges.
- Treat `ai-agent/apps/desktop/src/plugins` and `ai-agent/plugins` as authoritative bundled-plugin overlays. Never replace them from a moving external branch during the merge.
- A green upstream test suite does not replace AgentOS contract, packaging, upgrade, or real manual acceptance.

## Workflow

### 1. Read repository instructions and scope the change

Read applicable `AGENTS.md` files. Record the Hermes semver, official tag, tag object SHA, peeled commit SHA, AgentOS CalVer, base branch, previous upstream commit, new diff range, affected paths, owning specifications, and bundled-plugin lock state.

Stop if the bundled specifications are missing. Do not reconstruct product behavior from memory or machine-local documents.

### 2. Protect the worktree

Capture current branch, HEAD, remotes, and `git status --short`. The merge script refuses a dirty worktree, detached HEAD, active merge, or pre-existing target branch. Preserve unrelated user work in another checkout or explicitly named stash before invoking it; never discard that work.

### 3. Start the exact release merge

Run inside the `agentos-desktop` checkout:

```bash
bash docs/skills/merge-hermes-upstream/scripts/start-merge.sh \
  0.21.0 v2026.8.31 2026.09.02 main
```

Arguments are `HERMES_VERSION UPSTREAM_TAG CALVER [BASE_BRANCH]`. The example creates `ai-agent/hermes-v0.21.0-2026.09.02` and merges the peeled commit of `v2026.8.31` with `--no-ff --no-commit`.

Exit code `2` means a merge is active with conflicts. Continue with semantic resolution. Any other nonzero code is a preflight, provenance, or Git failure and must be fixed first.

### 4. Resolve and audit

For each unmerged file:

1. Inspect base, AgentOS, and upstream stages with `git show :1:path`, `:2:path`, and `:3:path`.
2. Read its owning reference from `references/spec-map.md`.
3. Retain new upstream APIs, fields, tests, and bug fixes.
4. Reapply the validated brand profile, localization, authentication, remote boundaries, product policy, artifact privacy, packaging, and update behavior. Use the domain-specific variables from `references/brand-profile.md`; do not hardcode the AgentOS defaults into reusable adaptation logic.
5. Stage only after conflict markers are gone and the resolution has a corresponding requirement or test.

Do not blanket-select `ours` or `theirs`, delete upstream tests to obtain green CI, or review only conflict files. Automatic merges across desktop, gateway, i18n, policy, package, updater, and workflow surfaces require the same audit.

```bash
bash docs/skills/merge-hermes-upstream/scripts/audit-agentos-contracts.sh
```

Then follow `references/bundled-plugins.md`: validate `config/bundled-plugins.lock.json`, reconcile `apps/desktop/src/plugins/channels` and `plugins/` from the explicit `ai-agent` checkout, and run `git apply --check` on the channels integration overlay before applying it. Map every compatibility decision to `PLUGIN-*`.

### 5. Test the combined product

At minimum run:

```bash
git diff --check
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop run test:desktop:platforms
npm --prefix apps/desktop run test:ui -- --run
python3 "$AI_AGENT_ROOT/scripts/validate_bundled_plugins.py" \
  "$AI_AGENT_ROOT/config/bundled-plugins.lock.json"
```

Then run targeted Python, Electron, TUI, remote gateway, MCP/A2A, packaging, installation, upgrade, and rollback tests for every affected contract. Use `references/06-ai-agent-migration-checklist.md` for commands and failure symptoms.

### 6. Commit, validate, and open the PR

After conflicts and pre-commit checks pass:

```bash
git commit -m "merge: Hermes 0.21.0 (v2026.8.31)"
bash docs/skills/merge-hermes-upstream/scripts/validate-merge.sh \
  0.21.0 v2026.8.31 2026.09.02
git push -u origin ai-agent/hermes-v0.21.0-2026.09.02
```

Create a Draft PR using the `ai-agent` upstream-sync PR template. Include provenance, diff range, conflict decisions, affected requirement IDs, automated evidence, candidate build plan, manual acceptance owner, and rollback target. Do not mark it ready until the source commit is locked in the release manifest.

### 7. Candidate and release handoff

This skill stops at a validated source commit and Draft PR. Candidate construction, human acceptance, merge to `main`, gray deployment, and formal promotion follow `ai-agent/docs/SOP.md`. Formal release must promote the exact tested RC artifacts without rebuilding.

## Failure rules

- If the official tag cannot be fetched or its SHA disagrees with the release manifest, stop; there is no fallback source.
- If the target branch exists, inspect and resume only the intended run; never reset, overwrite, or force-push it.
- If product tests fail, fix the integration boundary and keep the candidate unapproved.
- If the bundled-plugin lock fails, a target directory has undeclared files, or the channels overlay does not pass `git apply --check`, stop and resolve the provenance or API compatibility explicitly.
- If push or PR creation lacks credentials, retain the verified local commit and report the exact failure.
- Never use destructive reset, checkout, clean, or forced push to recover this workflow.
