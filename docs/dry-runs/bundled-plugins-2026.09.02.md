# Bundled Plugins 本地 Dry-run（2026-09-02）

## 输入与来源

- 治理分支：`feat/bundled-plugins`
- ZIP：`/Users/yizhang/Downloads/归档.zip`
- ZIP SHA-256：`76ed98ed53ca5df1e31e10634eec87dd948b0467f5617c7fe837917d56e49ed1`
- Hermes plugin source：`https://github.com/hqzyai/hermes-plugin.git`
- Hermes plugin commit：`a605cf524311a0fceae3e60b9354c2535a741378`
- 兼容性目标：Hermes Agent `v0.21.0` / tag `v2026.8.31`
- Tag object：`6e8f8418e6378eb2617e4de074e13dedd091b8af`
- Peeled commit：`29112bef099274229cadff79cdff7bf7b99c4b77`

ZIP 只读检查发现外层 54 个、内层 20 个成员；没有绝对路径、`..` 路径穿越、symlink 或大小写冲突。导入 allow-list 只包含两个 Desktop TypeScript 源文件和 integration patch；未导入嵌套 ZIP、runtime JavaScript、`.DS_Store` 与 `__MACOSX`。

## 治理与来源锁

```text
python3 scripts/validate_specs.py
validated 9 specs with 76 unique requirements

python3 scripts/validate_bundled_plugins.py config/bundled-plugins.lock.json
validated 4 bundled plugins

python3 -m unittest tests.test_bundled_plugins tests.test_contributor_skills -v
Ran 17 tests ... OK
```

校验场景包含 source path、`channels` identity、初始 commit/archive hash、文件 SHA drift、未声明/禁止文件、路径穿越、重复归属、backend manifest 以及 Contributor Skill 的 bundled-plugin 合并门禁。

## Hermes 合并兼容性

在临时、精确 tag checkout 中执行：

```text
git apply --check .../patches/bundled-plugins/channels/hermes-channels-integration.patch
exit 0

npm exec -- eslint src/plugins/channels/plugin.tsx src/plugins/channels/page.tsx \
  src/api/messaging.ts src/types/hermes.ts src/sdk/index.ts
exit 0

npm run typecheck
exit 0

npm run build
exit 0; Vite built 15,220 modules and assert-dist-built passed
```

构建产物 `dist/assets/index-*.js` 命中 `/channels` 和扫码页面文案，证明该源码进入生产 bundle。构建使用 dirty 临时 checkout，因此 build stamp 正确发出 dirty warning；这不是可发布候选，正式 candidate 必须从锁定 PR commit 构建。

Desktop UI tests：

```text
npm exec -- vitest run --project ui \
  src/plugins/channels/page.test.tsx src/plugins/channels/plugin.test.tsx
Test Files 2 passed; Tests 4 passed
```

覆盖插件只注册一次 `/channels`、只展示钉钉/个人微信/QQ、扫码 session 启动和关闭取消、connected session apply 与状态刷新。

## Backend plugin tests

系统 `/usr/bin/python3` 是 3.9.6，而 Hermes `v2026.8.31` 的 `requires-python` 是 `>=3.11,<3.14`。第一次独立执行因此在 Hermes host provider import/运行时类型语法处失败。切换到 Python 3.11，并将精确 Hermes checkout 加入 `PYTHONPATH` 后：

```text
QwenAI image provider: Ran 4 tests ... OK
QwenAI video provider: Ran 7 tests ... OK
OpenSERP filters: Ran 3 tests ... OK
```

所有 HTTP、模型目录、异步任务和文件保存边界均由测试 fake 控制，没有使用真实 API key。OpenSERP 初始代码对 `javascript:`、`file:`、无 host URL 返回非 junk；新增测试先出现 4 个预期失败，再在 URL filter 边界拒绝非 HTTP(S)/无 host URL，3 个测试转绿。

## 尚未替代的候选门禁

本 dry-run 不等于发布批准，仍需在 candidate workflow/真实设备完成：

- Linux/macOS/Windows 安装包及签名、公证；
- AMD64/ARM64 镜像构建与内部文件清单；
- DingTalk、个人 Weixin、QQ 真实扫码、授权、凭据保存和 gateway restart；
- Qwen/OpenSERP 测试账号的 live smoke；
- N-1 新装/升级、显式启停持久化、回滚和组织级数据保持；
- 非 PR 作者按 `docs/manual-acceptance-template.md` 签字。

这些项目保持 fail closed，不能由本地 typecheck/build 或 mock 单测代替。
