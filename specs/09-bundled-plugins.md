# 09 Bundled Plugins

## Requirements

- **PLUGIN-001** Desktop bundled plugin source is authoritative at `apps/desktop/src/plugins/<id>`; Hermes backend plugin source is authoritative at `plugins/<provider-kind>/<id>`. External archives and repositories are import provenance, not build-time dependencies.
- **PLUGIN-002** The Desktop plugin id, directory and route are `channels`, `apps/desktop/src/plugins/channels` and `/channels`. Source and packaged output must not retain the legacy `im-channels` identity.
- **PLUGIN-003** `config/bundled-plugins.lock.json` records every bundled file, SHA-256, local root and immutable initial source. Missing, undeclared, changed, unsafe, symlinked or forbidden files block CI.
- **PLUGIN-004** Backend `plugin.yaml` files declare name, version, description, author, `kind: backend` and every required environment variable. Missing credentials fail closed and must not be logged.
- **PLUGIN-005** Generated Desktop JavaScript, `.idea`, `.DS_Store`, `__MACOSX`, nested delivery archives, dependency caches and Python bytecode are excluded from source control and candidate provenance.
- **PLUGIN-006** The `channels` integration overlay must pass `git apply --check` against each synchronized Hermes source commit before application. If upstream already supplies equivalent APIs, the PR replaces the patch with reviewed native integration and maps the decision to these requirements.
- **PLUGIN-007** Upstream synchronization audits both plugin roots for SDK, manifest, discovery, credential, network and packaging compatibility. A clean textual merge or unchanged plugin file does not permit skipping this audit.
- **PLUGIN-008** Candidate images contain the three locked backend plugins, and all supported Desktop packages contain the compiled `channels` plugin built from the locked TypeScript source. Release promotion reuses the same tested artifacts.
- **PLUGIN-009** Bundled plugin upgrades preserve explicit user enablement, configuration and organization-scoped data under `{APP_DATA_DIR}/profiles/{ORG_NAME}`; uninstall and rollback follow the documented data-retention policy.

## Automated acceptance

- Run `python3 scripts/validate_bundled_plugins.py config/bundled-plugins.lock.json` in L0 and again before candidate packaging.
- Run Qwen image/video provider tests and OpenSERP filter/provider tests under the target Hermes Python 3.11–3.13 runtime without live credentials; external HTTP and asynchronous job status are deterministic fakes.
- Against the selected Hermes checkout, run Desktop lint, typecheck, UI tests and build for `apps/desktop/src/plugins/channels`, plus onboarding start/status/apply/cancel success, expiration and error tests.
- Run `git apply --check patches/bundled-plugins/channels/hermes-channels-integration.patch` before applying the overlay; record an explicit reviewed native-integration decision when the patch is obsolete.
- Inspect container and Desktop package manifests to prove all four plugins are present and no excluded input or secret is packaged.

## Manual acceptance

1. On an immutable RC, confirm `channels` appears once, opens `/channels`, and remains enabled/disabled across restart and upgrade according to the user's explicit choice.
2. Exercise DingTalk, personal Weixin and QQ QR creation, polling, cancellation, expiration, successful credential apply and gateway restart; retain screenshots/logs with QR payloads and credentials redacted.
3. Exercise Qwen text-to-image, Qwen text-to-video and OpenSERP search with test accounts/services, including missing credential and upstream error behavior.
4. Verify macOS, Windows and Linux packages plus AMD64/ARM64 images contain the expected plugin versions, then verify rollback preserves the previous compatible configuration and organization-scoped data.
