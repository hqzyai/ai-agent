# ai-agent vYYYY.MM.DD

- Product version: `v<Hermes semver>-YYYY.MM.DD`
- Source commit: `<40-character AgentOS SHA>`
- Upstream Hermes: `<official tag + link + peeled SHA>`
- Brand profile: `<path + SHA-256; list APP_ID/APP_DATA_DIR/ORG_NAME changes>`
- Acceptance evidence: `<URL>`

## Highlights

- User-visible AgentOS changes.
- Important upstream capabilities retained after product adaptation.

## Compatibility and migration

- Supported upgrade starting versions.
- Data/config migration and rollback constraints.
- Known issues and platform-specific limitations.

## Artifacts

- Container: `ghcr.io/hqzyai/ai-agent:vYYYY.MM.DD@sha256:<digest>` (`linux/amd64`, `linux/arm64`)
- Linux: filename + SHA-256
- macOS: filename + SHA-256
- Windows: filename + SHA-256

## Verification

- Automated acceptance result and report.
- Manual devices/OS matrix and approvers.
- SBOM, scan and provenance links.

## Rollback

- Previous stable container digest.
- Previous desktop update-feed target.
- Data recovery notes.
