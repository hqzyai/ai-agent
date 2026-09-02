# Portable brand profile

Before resolving branding, packaging, storage, or Skill Hub conflicts, load the repository's approved environment profile. The canonical template is `ai-agent/config/brand.env.example`; a tenant may provide an equivalent validated profile.

| Variable | Meaning |
| --- | --- |
| `BRAND_NAME` | User-visible product brand. |
| `BRAND_WORDMARK` | Display-only wordmark. |
| `BRAND_SLUG` | Lowercase machine-readable brand slug. |
| `BRAND_ASSETS_DIR` | Repository-relative logo and platform-icon directory. |
| `ORG_NAME` | Path-safe organization identifier and profile namespace. |
| `APP_NAME` | Desktop application and installer name. |
| `APP_ID` | Stable reverse-domain application identity. |
| `APP_DATA_DIR` | Shared application data root; loaders must expand a leading `~`. |
| `APP_DEFAULT_LOCALE` | Default locale. |
| `SKILL_HUB_NAME` | User-visible Skill Hub name. |
| `SKILL_HUB_SOURCE` | Internal Skill Hub source identifier. |

Do not invent catch-all names such as `BRAND_APP_NAME`, `BRAND_COMPANY_NAME`, or `BRAND_SKILL_HUB_NAME`. `BRAND_*` is reserved for actual visual or brand identity. Reject the retired `COMPANY_NAME`; use `ORG_NAME`.

AgentOS defaults are `AgentOS`, `AGENT OS`, `agentos`, `branding/agentos`, `hqzyai`, `com.hqzyai.agentos`, `~/.agentos`, `zh-CN`, `华清严选`, and `nacos`. Treat them as the default profile, not constants for another brand.

All actual app data belongs under `{APP_DATA_DIR}/profiles/{ORG_NAME}`; the default resolves to `~/.agentos/profiles/hqzyai`. Validate `ORG_NAME` as one lowercase path-safe segment. Keep desktop state, cache, logs, crash dumps, managed Agent data, updates, and migration backups inside that organization-scoped root.

`APP_ID`, `APP_DATA_DIR`, and `ORG_NAME` are persistent identities. Changing any of them requires explicit N-1 upgrade, migration, rollback, and data-preservation acceptance. Keep internal compatibility identifiers such as `HERMES_HOME`, `hermes:*`, protocol routes, and backend executable names unless a separately tested migration changes them.
