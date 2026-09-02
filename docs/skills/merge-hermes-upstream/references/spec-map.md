# AgentOS Transformation Spec Map

The canonical runtime documentation is bundled beside this file. Read `00-README.md` and `06-ai-agent-migration-checklist.md` for every merge. A machine-local `$AGENTOS_SPEC_DIR` is only a maintenance mirror and is never required to execute the skill.

| Changed surface | Required specification | Non-negotiable checks |
| --- | --- | --- |
| `apps/desktop/electron`, auth, boot, connection | `02-auth-and-remote-gateway.md` | BFF password login, HttpOnly cookies, fresh WS tickets, token refresh, retry-to-login UX, no secret logging |
| chat, media, files, artifacts | `03-chat-media-artifacts.md` | remote API download/cache, hidden remote paths, no `all` artifact tab, files default, tool-output suppression |
| cron, messaging, i18n, shell UI | `04-cron-messaging-i18n-ui.md` | time controls instead of cron syntax, desktop-only delivery, five China platforms, complete field localization, no duplicate statusbar `子智能体` / `定时任务`, archived chats in lower-left gateway menu, in-app terminal disabled without removing the backend terminal tool |
| skills, Hub install, slash commands, homepage workflow guides | `04-cron-messaging-i18n-ui.md` | category-safe `skill_view`, profile-scoped dashboard `skills.external_dirs` multi-path editor, immediate config-mtime/list/prompt/slash refresh, Hub lock cross-process generation, Nacos-only routing branded as “华清严选” with server/renderer enforcement and no public fallback, four editable professional workflow drafts, `【...】` fields render as editable placeholders without changing submitted text |
| `apps/desktop/src/plugins`, root `plugins`, plugin SDK/provider discovery | `bundled-plugins.md` | validate `config/bundled-plugins.lock.json`, keep Desktop id/route `channels`/`/channels`, run `git apply --check`, backend provider tests, Desktop typecheck/build, package inclusion and `PLUGIN-*` evidence |
| package scripts, Electron resources, workflows | `05-offline-packaging-and-ci.md` | `com.hqzyai.agentos` appId/AUMID, stable Windows installer GUIDs, one-time macOS appId bridge, hqzy install/data/cache roots with lossless legacy migration, schema-2 sanitized/relocatable bundled-agent manifest, schema-3 tenant release config with Windows EXE and macOS DMG sources, self-contained Python and browser-use, no recursive installers or credentials, staged native dependency closure, AgentOS icons/EXE identity/installer names, tenant package-only updates, no backend/Git/Nous fallback |
| model clients, transports, auxiliary LLM calls | `06-ai-agent-migration-checklist.md` | every header-capable model HTTP request carries canonical `HERMES_SESSION_ID` plus the equal LiteLLM compatibility header; retries, summaries, compression/title calls and native Gemini preserve the same durable session id; legacy `SESSION_ID` is stripped before transport |
| any migration or conflict | `06-ai-agent-migration-checklist.md` | end-to-end sequence, branding audit, remote boundaries, regression commands |

## Conflict Policy

Use the three Git stages:

```bash
git show :1:path/to/file  # merge base
git show :2:path/to/file  # current AgentOS branch
git show :3:path/to/file  # official Hermes upstream
```

Prefer upstream implementation structure when it adds real behavior, then apply AgentOS product policy at the narrowest display/config/transport boundary. Typical examples:

- Keep a new upstream settings field, but localize it and replace user-visible Hermes branding.
- Keep a refactored component, but retain the centralized AgentOS product policy: the domestic model/provider allowlist, hidden bundled skills, and fully hidden unsupported toolsets.
- Keep internal `hermes` executable, module, env, RPC, and compatibility names when renaming would break the runtime.
- Remove reintroduced user-facing version pills, shell buttons, log panes, foreign providers, or the artifact `all` tab when the specification forbids them.

## Mandatory Regression Matrix

1. Fresh install reaches Chinese login instead of a generic boot failure.
2. Valid saved login resumes after a full app restart without exposing credentials.
3. Expired access credentials refresh or return to login with the waiting message.
4. Remote sessions, media, files, and artifacts never fall through to local paths.
5. Artifact filters equal `image`, `file`, `link`; default is `file`; remote paths are hidden.
6. Messaging displays only DingTalk, Feishu, WeCom app, personal WeChat, and QQ in the specified order.
7. Messaging descriptions, labels, help, and placeholders are Chinese.
8. Server APIs, dashboard, desktop, and runtime discovery all apply `hermes_cli/agentos_policy.py`; unsupported model providers and bundled coding-agent skills remain hidden, and `image_gen`, `video_gen`, `x_search` remain hidden as complete toolsets while backend compatibility IDs stay intact.
9. Statusbar shows `网关`, omits the duplicate `子智能体` / `定时任务` entries, and has no client/backend version pills; their left navigation entries remain available.
10. Lower-left gateway menu contains archived chats and sign out.
11. Welcome wordmark is `AGENT OS`; assistant identity is AgentOS.
12. Packaged icons, offline payload, native dependencies, and installer size are correct.
13. A Hub skill installed into an existing nested category is visible immediately in `skills_list`, the next skills prompt, and slash commands; malformed plugin namespaces and traversal paths remain rejected.
14. The full Capabilities page opens on an `专家技能` tab before `技能`, showing searchable expert cards in the exact order `差旅报销`、`项目研判`、`投资合同审核`、`文书起草`; the empty-chat intro no longer duplicates them, and embedded Bot Mode omits this launch-only tab. Clicking a card always opens a fresh main chat, replaces its composer with the exact editable slash command, and never auto-submits or calls the backend. Chinese-bracket template fields (`【...】`) are visibly editable and serialize unchanged; the travel template has four such fields, project assessment has two, and ordinary JSON braces are not highlighted. The empty composer placeholder is exactly `今天帮你做些什么? /调用技能与指令`.
15. Main, streaming, retry/fallback, iteration-summary and auxiliary model HTTP requests include exactly one canonical `HERMES_SESSION_ID` header and one equal `X-LiteLLM-Session-ID` compatibility header whose value is the current durable conversation id; legacy `SESSION_ID` is removed and never emitted, AI Gateway resolves the compatibility value as LiteLLM session metadata, concurrent sessions never exchange values, and Bedrock/Codex app-server transports receive no unsupported header kwargs.
16. Desktop update checks and pushes always target the current tenant's AgentOS installation package, including in remote mode and background polling; packaged schema 3 carries both the tenant Windows EXE and macOS DMG source. macOS requires version/SHA-256 TOS metadata, validates UDIF/bundle identity, replaces through staging/backup, relaunches from the original `.app` path, and rolls back on failure. No renderer call reaches `/api/hermes/update*`, no missing package source falls back to Git/Nous/`hermes update`, and packaged bootstrap uses bundled resources only.
17. Password login remains the default tab; Feishu QR login opens the OAuth window only on explicit user action, accepts only an already-bound AgentOS account, installs the result in the persistent OAuth partition, and never exposes tokens to the renderer.
18. Bundled-agent schema 2 is accepted only for the current platform/architecture and only when `sanitized`, `relocatable`, and `pythonRuntimeBundled` are true; both the Hermes and browser-use Python environments are self-contained, credential files/build-machine paths are absent, and the valid manifest is written last.
19. Hub exposes only internal source `nacos` under the visible label “华清严选”; `source=all` is only a compatibility alias for Nacos, legacy config/server responses cannot reopen public catalogs, non-Nacos identifiers are rejected, and Nacos miss/timeout never falls back to a public skill.
20. Desktop and Bot Mode use the AgentOS Hub UI and the active backend's skill APIs; they never embed or fall back to the public Nous Skills Hub picker.
21. Desktop does not register or render the in-app terminal pane, PersistentTerminal, terminal statusbar/command/keybind/settings entries, or terminal-dependent layouts; upgrades remove stale terminal tracks without leaving empty space, while the backend terminal tool remains available to the agent.
22. Ordinary new packages use `com.hqzyai.agentos`; Windows and macOS fresh installs use the documented `hqzy` application directory. Windows keeps the historical NSIS/MSI installation identity while using the new runtime appId; old macOS clients cross the identity change through exactly one lower bridge version followed by a higher final version. Before auth/session reads, legacy Electron state and managed Agent data migrate into `{APP_DATA_DIR}/profiles/{ORG_NAME}`; cookies remain available, target conflicts are not overwritten, a complete recovery copy remains under `migration-backups`, explicit custom `HERMES_HOME` values still work, WSL font cache remains inside the organization profile, local SSH sockets are transient, and remote `~/.hermes` paths are unchanged.
