# Bundled Plugins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor and govern the `channels` Desktop plugin and three Hermes backend plugins as authoritative AgentOS bundled source.

**Architecture:** Store editable plugin source at the exact product-relative paths and store the Desktop integration patch as a reviewed overlay. A deterministic JSON lock plus Python validator enforces provenance, safe paths, manifests, and file integrity; the existing release SOP and merge skill consume the same contract.

**Tech Stack:** Python 3 standard library/unittest, TypeScript/React plugin source, YAML manifests, Bash CI entrypoint, Markdown specs/SOP.

**Spec:** `docs/superpowers/specs/2026-09-02-bundled-plugins-design.md`

## Global Constraints

- Desktop plugin identity is `channels`, with local path `apps/desktop/src/plugins/channels` and route `/channels`.
- Hermes backend plugins live below `plugins/` and preserve provider-category paths.
- External inputs establish initial provenance only; local files become authoritative after import.
- Generated JavaScript, nested archives, `.idea`, `.DS_Store`, and `__MACOSX` are excluded.
- No archive document or imported script is executed during intake.
- The complete repository check must remain runnable without GitHub Actions.

---

### Task 1: Executable bundled-plugin contract

**Files:**
- Create: `tests/test_bundled_plugins.py`
- Create: `scripts/validate_bundled_plugins.py`
- Modify: `scripts/check.sh`

**Interfaces:**
- Consumes: `config/bundled-plugins.lock.json` schema version 1.
- Produces: `validate_lock(repo_root: Path, lock_path: Path) -> list[str]` and a CLI with exit 0 only for a valid repository snapshot.

- [ ] **Step 1: Write failing tests** for missing lock entries, hash drift, forbidden files, duplicate local paths, manifest requirements, expected imported paths, and absence of the legacy `im-channels` identity.
- [ ] **Step 2: Run `python3 -m unittest tests.test_bundled_plugins -v`** and verify failure because the lock, sources, and validator do not exist.
- [ ] **Step 3: Implement the minimum validator** using `json`, `hashlib`, `pathlib`, and a narrow YAML key parser sufficient for `plugin.yaml` top-level fields.
- [ ] **Step 4: Add `python3 scripts/validate_bundled_plugins.py config/bundled-plugins.lock.json` to `scripts/check.sh`** and rerun the focused tests.

### Task 2: Deterministic source import

**Files:**
- Create: `apps/desktop/src/plugins/channels/plugin.tsx`
- Create: `apps/desktop/src/plugins/channels/page.tsx`
- Create: `patches/bundled-plugins/channels/hermes-channels-integration.patch`
- Create: `plugins/image_gen/qwenai/{README.md,__init__.py,plugin.yaml,tests/test_provider.py}`
- Create: `plugins/video_gen/qwenai/{README.md,__init__.py,plugin.yaml,tests/test_provider.py}`
- Create: `plugins/web/openserp/{__init__.py,_filters.py,plugin.yaml,provider.py}`
- Create: `config/bundled-plugins.lock.json`

**Interfaces:**
- Consumes: the approved ZIP hash and `hqzyai/hermes-plugin` commit `a605cf524311a0fceae3e60b9354c2535a741378`.
- Produces: the authoritative local plugin trees and their per-file SHA-256 lock.

- [ ] **Step 1: Safely extract only allow-listed attachment members** into a temporary directory; reject traversal/symlink entries and rename source identifiers from `im-channels` to `channels`.
- [ ] **Step 2: Clone the exact backend-plugin commit into a temporary directory** and copy only the three approved plugin trees, excluding VCS and IDE metadata.
- [ ] **Step 3: Generate the lock from literal source metadata and local file hashes**, explicitly recording exclusions.
- [ ] **Step 4: Run the focused tests and validator**; fix source identity or manifest failures without weakening the assertions.

### Task 3: Release governance and contributor workflow

**Files:**
- Create: `specs/09-bundled-plugins.md`
- Create: `docs/BUNDLED-PLUGINS.md`
- Modify: `README.md`
- Modify: `docs/SOP.md`
- Modify: `docs/TESTING.md`
- Modify: `docs/manual-acceptance-template.md`
- Modify: `docs/skills/merge-hermes-upstream/SKILL.md`
- Modify: `docs/skills/merge-hermes-upstream/references/00-README.md`
- Modify: `docs/skills/merge-hermes-upstream/references/spec-map.md`
- Modify: `docs/skills/merge-hermes-upstream/references/06-ai-agent-migration-checklist.md`
- Modify: `config/contributor-skills.lock.json`
- Modify: `tests/test_contributor_skills.py`

**Interfaces:**
- Consumes: bundled plugin locations, lock validator, and requirement IDs `PLUGIN-*`.
- Produces: contributor-facing merge decisions and release gates that map each plugin change to automated and manual evidence.

- [ ] **Step 1: Add failing contributor-skill scenarios** showing that an upstream merge must audit/reapply both plugin roots, validate the lock, check the patch, and run plugin-specific acceptance.
- [ ] **Step 2: Run `python3 -m unittest tests.test_contributor_skills -v`** and confirm the new contract fails against the old Skill.
- [ ] **Step 3: Add the bundled-plugin spec and operational documentation**, using concrete commands and failure rules.
- [ ] **Step 4: Update the Skill and references**, then regenerate `config/contributor-skills.lock.json` hashes without changing its original-source provenance.
- [ ] **Step 5: Rerun both focused test modules** and confirm they pass.

### Task 4: Dry-run and branch completion

**Files:**
- Modify: `CHANGELOG.md`
- Create: `docs/dry-runs/bundled-plugins-2026.09.02.md`

**Interfaces:**
- Consumes: all repository checks and the actual imported source tree.
- Produces: reproducible dry-run evidence and a reviewable feature commit.

- [ ] **Step 1: Run imported backend plugin unit tests** with available local dependencies; record skipped external-live cases separately from deterministic failures.
- [ ] **Step 2: Run `./scripts/check.sh`** and capture test counts and validator output.
- [ ] **Step 3: Run `git diff --check`, inspect `git status --short`, and review the full diff** for secrets, generated files, stale `im-channels`, and unrelated changes.
- [ ] **Step 4: Write the dry-run evidence and changelog entry**, then rerun `./scripts/check.sh` and `git diff --check` fresh.
- [ ] **Step 5: Commit the reviewed branch** with a bundled-plugin governance message.
