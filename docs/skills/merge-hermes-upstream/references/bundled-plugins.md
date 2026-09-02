# Bundled Plugin Overlay Contract

AgentOS bundled plugins are authoritative downstream source in the `ai-agent` governance repository. They are not fetched from moving external repositories during a Hermes merge.

## Required roots

- Desktop: `apps/desktop/src/plugins/channels`
- Hermes backend: `plugins/image_gen/qwenai`, `plugins/video_gen/qwenai`, `plugins/web/openserp`
- Integration overlay: `patches/bundled-plugins/channels/hermes-channels-integration.patch`
- Provenance: `config/bundled-plugins.lock.json`

Use an explicit governance checkout path:

```bash
AI_AGENT_ROOT=/absolute/path/to/ai-agent
python3 "$AI_AGENT_ROOT/scripts/validate_bundled_plugins.py" \
  "$AI_AGENT_ROOT/config/bundled-plugins.lock.json"
```

Do not substitute `hqzyai/hermes-plugin/main` or re-extract an unverified ZIP. Reconcile the locked files into the product checkout file by file; if the target plugin directory contains undeclared files, stop and review rather than deleting or overwriting the directory.

## Desktop compatibility decision

The plugin directory, id and route are `channels`, `channels` and `/channels`. Reject a merge that restores `im-channels` or packages the attachment's prebuilt JavaScript instead of building current TypeScript source.

Before applying the backend integration overlay:

```bash
git apply --check "$AI_AGENT_ROOT/patches/bundled-plugins/channels/hermes-channels-integration.patch"
```

If it applies, apply it and test the combined code. If it does not apply because upstream changed, inspect each rejected hunk. Reimplement the four onboarding operations against the new upstream structure or document that upstream now supplies equivalent behavior. The PR records the endpoint/SDK mapping and `PLUGIN-002`, `PLUGIN-006`, `PLUGIN-007` evidence; never force the patch or silently skip it.

## Required acceptance

- Run the source lock validator before copying and before candidate packaging.
- Run backend provider tests under the target Hermes Python 3.11–3.13 runtime with the product checkout on `PYTHONPATH`; external services stay mocked and missing env variables fail without logging values.
- Run Desktop lint, typecheck, UI tests and build for the `channels` source and SDK exports.
- Test onboarding start, status polling, apply, cancel, expiration, errors and gateway restart.
- Inspect AMD64/ARM64 images and Linux/macOS/Windows packages for the expected plugins and absence of excluded inputs.
- On the immutable RC, manually exercise three QR flows, Qwen image/video and OpenSERP, then verify N-1 upgrade and rollback persistence.

Any failed provenance, patch, SDK, credential or package-inclusion check blocks the candidate. Upstream tests alone do not satisfy `PLUGIN-*`.
