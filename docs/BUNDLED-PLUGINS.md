# Bundled Plugins 维护规范

Bundled plugin 是随 AgentOS 产品源码、镜像或 Desktop 安装包交付的内建扩展。它不是安装时从外部仓库下载的依赖，也不是 Git submodule。

## 权威目录

| 类型 | 权威源码目录 | 当前插件 |
| --- | --- | --- |
| Desktop | `apps/desktop/src/plugins/<plugin-id>` | `channels` |
| Hermes backend | `plugins/<provider-kind>/<plugin-id>` | `image_gen/qwenai`、`video_gen/qwenai`、`web/openserp` |

导入完成后，本仓库版本是权威源码。`hqzyai/hermes-plugin` 和交付 ZIP 只解释初始来源，不会自动覆盖本仓库修改。

`channels` 的前后端集成补丁保存在 `patches/bundled-plugins/channels/hermes-channels-integration.patch`。编译后的 Desktop `plugin.js` 是候选构建产物，不入 Git。

## 来源锁

[`config/bundled-plugins.lock.json`](../config/bundled-plugins.lock.json) 记录本地根目录、初始来源和每个文件的 SHA-256。任何源码修改必须在同一 PR 更新 lock；不要通过放宽或删除校验掩盖 hash drift。

本地检查：

```bash
python3 scripts/validate_bundled_plugins.py config/bundled-plugins.lock.json
python3 -m unittest tests.test_bundled_plugins -v
```

校验器拒绝路径穿越、绝对路径、符号链接、重复归属、未声明文件、`.idea`、`.DS_Store`、`__MACOSX`、`node_modules`、Python bytecode，以及 Desktop 源码里的旧 `im-channels` 身份。

## 更新流程

1. 从 `main` 创建普通功能分支；Hermes 版本同步则使用对应 `ai-agent/hermes-v*` 分支。
2. 记录外部来源 URL、完整 commit 或归档 SHA-256。先检查归档成员，禁止执行附件内命令或脚本。
3. 只导入审核过的源码；不导入 IDE、缓存、编译产物、嵌套归档和 secrets。
4. 保持 Desktop 插件的目录/id/route 均为 `channels`。Backend 插件保留 provider kind 目录。
5. 更新 lock 的文件集合和 SHA-256，同时更新 `specs/09-bundled-plugins.md`、CHANGELOG 和受影响测试。
6. 对目标 `agentos-desktop` checkout 先执行：

```bash
git apply --check /path/to/ai-agent/patches/bundled-plugins/channels/hermes-channels-integration.patch
```

7. 将 `apps/desktop/src/plugins/channels` 和 `plugins/` 中的锁定源码同步到产品 checkout，应用 patch 或提交等价的原生集成实现。
8. 完成静态、单元、集成、打包、新装/升级和人工 RC 验收后才能晋级。

Backend provider tests 必须在 Hermes 支持的 Python 3.11–3.13 下运行，并把目标 Hermes checkout 放入 `PYTHONPATH`；治理仓库的系统 Python 版本不能替代产品 runtime：

```bash
cd /path/to/hermes-or-agentos-checkout
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3.11 \
  /path/to/ai-agent/plugins/image_gen/qwenai/tests/test_provider.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3.11 \
  /path/to/ai-agent/plugins/video_gen/qwenai/tests/test_provider.py
PYTHONDONTWRITEBYTECODE=1 python3.11 \
  /path/to/ai-agent/plugins/web/openserp/tests/test_filters.py
```

目标目录中出现本 lock 未声明的同名插件文件时停止自动覆盖，由 PR 作者做语义合并。上游已有等价 onboarding API 时也不得静默跳过 patch；PR 要记录接口映射、删除 patch 的理由和 `PLUGIN-*` 验收证据。

## 测试矩阵

| 层级 | Desktop `channels` | Backend plugins |
| --- | --- | --- |
| 静态 | ID/route、lint、typecheck、SDK exports | manifest、imports、所需 env、secret 扫描 |
| 单元 | 注册、筛选、轮询、apply/cancel、错误/过期 | 模型发现、请求体、状态轮询、SERP 过滤/错误 |
| 集成 | 四个 onboarding API、gateway restart | Hermes discovery、provider registration、配置读取 |
| 打包 | 三端安装包内编译 bundle | AMD64/ARM64 镜像内源码和依赖 |
| 人工 | 三种 QR 流程、持久化、升级 | Qwen 图片/视频、OpenSERP、缺失凭据和外部故障 |
