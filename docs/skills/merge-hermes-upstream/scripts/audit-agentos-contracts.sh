#!/usr/bin/env bash
set -u

failures=0
BRAND_NAME="${BRAND_NAME:-AgentOS}"
BRAND_WORDMARK="${BRAND_WORDMARK:-AGENT OS}"
SKILL_HUB_NAME="${SKILL_HUB_NAME:-华清严选}"
SKILL_HUB_SOURCE="${SKILL_HUB_SOURCE:-nacos}"

require_match() {
  local pattern="$1"
  local path="$2"
  local message="$3"
  if ! rg -q -- "$pattern" "$path"; then
    printf 'FAIL: %s\n' "$message" >&2
    failures=$((failures + 1))
  fi
}

reject_match() {
  local pattern="$1"
  local path="$2"
  local message="$3"
  if rg -q -- "$pattern" "$path"; then
    printf 'FAIL: %s\n' "$message" >&2
    failures=$((failures + 1))
  fi
}

require_literal() {
  local value="$1"
  local path="$2"
  local message="$3"
  if ! rg -F -q -- "$value" "$path"; then
    printf 'FAIL: %s\n' "$message" >&2
    failures=$((failures + 1))
  fi
}

require_match "ARTIFACT_FILTERS.*\['image', 'file', 'link'\]" \
  apps/desktop/src/app/artifacts/artifact-utils.ts \
  "artifact tabs must exclude all and keep image/file/link"
require_match "useRouteEnumParam\('tab', ARTIFACT_FILTERS, 'file'\)" \
  apps/desktop/src/app/artifacts/index.tsx \
  "artifact default must remain file"
require_match "setPlatforms\(agentosMessagingPlatforms\(result\.platforms\)\)" \
  apps/desktop/src/app/messaging/index.tsx \
  "messaging results must pass through the AgentOS platform filter"
require_match "AGENTOS_PLATFORM_ORDER.*\['dingtalk', 'feishu', 'wecom_callback', 'wecom', 'weixin', 'qqbot'\]" \
  apps/desktop/src/app/messaging/index.tsx \
  "messaging platform order changed"
require_match "archivedChats" apps/desktop/src/app/shell/gateway-menu-panel.tsx "gateway menu must expose archived chats"
require_match "RESERVED_PROFILE_NAMES.*\['default', 'hermes', 'test', 'tmp', 'root', 'sudo'\]" \
  apps/desktop/src/app/profiles/create-profile-dialog.tsx \
  "profile creation must reject backend-reserved names before submit"
require_match "RESERVED_PROFILE_NAMES.*\['default', 'hermes', 'test', 'tmp', 'root', 'sudo'\]" \
  apps/desktop/src/plugins/hermes-bots/plugin.js \
  "bot creation must reject backend-reserved names before submit"
reject_match "id: 'version-(client|backend)'" \
  apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx \
  "statusbar client/backend version pills were reintroduced"
reject_match "id: 'agents'" \
  apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx \
  "statusbar subagents entry was reintroduced"
reject_match "id: 'cron'" \
  apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx \
  "statusbar cron entry was reintroduced"
require_match 'onClick=\{onHide\}' \
  apps/desktop/src/app/right-sidebar/index.tsx \
  "file browser header must expose a working hide action"
require_match 'hideFileBrowserPane' \
  apps/desktop/src/store/layout.ts \
  "file browser hide must follow its actual layout-tree position"
reject_match 'name="collapse-all"' \
  apps/desktop/src/app/right-sidebar/index.tsx \
  "file browser hide button regressed to collapse-all folders"
require_match 'IN_APP_TERMINAL_ENABLED = false' \
  apps/desktop/src/lib/product-features.ts \
  "desktop in-app terminal product switch must remain disabled"
require_match "removeTreePane\('terminal'\)" \
  apps/desktop/src/app/contrib/controller.tsx \
  "stale persisted terminal tracks must be removed during desktop startup"
require_match 'IN_APP_TERMINAL_ENABLED && !isHudWindow\(\)' \
  apps/desktop/src/app/contrib/wiring.tsx \
  "PersistentTerminal must remain gated by the AgentOS product switch"
require_match 'IN_APP_TERMINAL_ENABLED \|\| !IN_APP_TERMINAL_ACTIONS.has' \
  apps/desktop/src/lib/keybinds/actions.ts \
  "terminal shortcuts must not remain reachable while the in-app terminal is disabled"
require_match '"skills.external_dirs":' \
  hermes_cli/web_server.py \
  "dashboard config must expose skills.external_dirs"
require_match '"format": "paths"' \
  hermes_cli/web_server.py \
  "skills.external_dirs must use the dashboard multi-path editor"
require_match '"general", "agent", "skills"' \
  hermes_cli/web_server.py \
  "dashboard config must keep a dedicated Skills category"
reject_match '"skills": "agent"' \
  hermes_cli/web_server.py \
  "dashboard skills settings were merged back into the crowded Agent category"
require_match 'AGENTOS_HIDDEN_TOOLSETS = frozenset\(\{"image_gen", "video_gen", "x_search"\}\)' \
  hermes_cli/agentos_policy.py \
  "unsupported image, video, and X toolsets must remain fully hidden"
require_match '"claude-code"' \
  hermes_cli/agentos_policy.py \
  "foreign bundled coding-agent skills must remain hidden"
require_match '"nous"' \
  hermes_cli/agentos_policy.py \
  "foreign model providers must remain explicitly blocked"
require_match '"deepseek"' \
  hermes_cli/agentos_policy.py \
  "the domestic model provider allowlist changed"
require_match 'is_agentos_toolset_visible' \
  hermes_cli/tools_config.py \
  "toolset discovery must apply the centralized AgentOS policy"
require_match 'is_agentos_model_row_visible' \
  hermes_cli/model_switch.py \
  "model inventory must apply the centralized AgentOS policy"
require_match 'is_agentos_model_row_visible' \
  hermes_cli/inventory.py \
  "shared model payloads must enforce the centralized AgentOS policy"
require_match 'is_agentos_provider_visible' \
  hermes_cli/web_server.py \
  "server provider APIs must apply the centralized AgentOS policy"
require_match 'AGENTOS_UPDATE_ACTION = "agentos-update"' \
  hermes_cli/web_server.py \
  "the user-visible backend update action must remain agentos-update"
require_match 'AGENTOS_DESKTOP_BFF_BASE_URL' \
  apps/desktop/scripts/write-release-config.cjs \
  "release packaging must support an explicit tenant BFF without editing development defaults"
require_match 'DESKTOP_RELEASE_CONFIG\.bffBaseUrl' \
  apps/desktop/electron/main.ts \
  "packaged desktop must read BFF from the generated tenant release config"
require_match '"dist:mac:publish": "npm run dist:mac && npm run upload:tos"' \
  apps/desktop/package.json \
  "mac packaging and TOS publishing must remain separate commands"
reject_match '"dist:mac":.*upload_tos' \
  apps/desktop/package.json \
  "plain mac packaging must not require TOS credentials"
reject_match 'hermes:connections:update-all' \
  apps/desktop/electron/main.ts \
  "desktop must not expose the upstream multi-instance source-update IPC"
reject_match '/api/hermes/update' \
  apps/desktop/electron/main.ts \
  "desktop main must not call the server-side Hermes source-update route"
reject_match 'hermes:connections:update-all' \
  apps/desktop/electron/preload.ts \
  "desktop preload must not expose the upstream multi-instance source-update bridge"
reject_match 'checkHermesUpdate|updateHermes\(|/api/hermes/update' \
  apps/desktop/src \
  "desktop renderer must update only the tenant AgentOS installation package"
reject_match 'EmbeddedHubPicker|HUB_PICKER_URL|hermes-agent\.nousresearch\.com/docs/skills' \
  apps/desktop/src/plugins/hermes-bots/plugin.js \
  "desktop must not embed the public Nous Skills Hub picker"
require_literal "AGENTOS_SKILL_HUB_SOURCE_IDS = frozenset({\"${SKILL_HUB_SOURCE}\"})" \
  hermes_cli/agentos_policy.py \
  "${BRAND_NAME} skill hub must remain locked to the configured source id"
require_literal "AGENTOS_SKILL_HUB_SOURCE_LABELS = {\"${SKILL_HUB_SOURCE}\": \"${SKILL_HUB_NAME}\"}" \
  hermes_cli/agentos_policy.py \
  "the sole skill hub source must use the configured display name"
require_match 'agentosHubSources\(sourcesQuery\.data\?\.sources' \
  apps/desktop/src/app/skills/hub.tsx \
  "desktop must filter old-server skill hub sources"
require_match 'agentosHubResults\(sourcesQuery\.data\?\.featured' \
  apps/desktop/src/app/skills/hub.tsx \
  "desktop must filter old-server featured skill results"
require_literal "const TAG_FULL = '${BRAND_WORDMARK}'" ui-tui/src/components/branding.tsx "TUI wordmark must match BRAND_WORDMARK"
reject_match "The Hermes path|Hermes is not installed|Hermes Desktop SSH" \
  apps/desktop/electron \
  "SSH runtime errors must not expose Hermes branding"
reject_match 'throw "(Hermes|The configured Hermes)' \
  apps/desktop/electron \
  "Windows SSH runtime errors must not expose Hermes branding"

if ((failures > 0)); then
  printf '%d AgentOS contract check(s) failed\n' "$failures" >&2
  exit 1
fi

printf 'AgentOS contract audit passed\n'
