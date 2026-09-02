# GitHub Actions 额度不足时的执行方式

先验证治理仓库自身：

```bash
./scripts/check.sh
python3 scripts/verify_upstream.py release-manifests/v2026.09.02.candidate.json
```

这会校验 specs、品牌 profile、所有 candidate manifest、workflow pin、单元测试和 whitespace；它不等价于目标 `agentos-desktop` 的应用测试或三端构建。

`v0.21.0` 的真实本地演练结果见 [`dry-runs/v0.21.0-2026.09.02.md`](dry-runs/v0.21.0-2026.09.02.md)。

额度不足不改变验收标准，只改变 runner 位置。

1. 在受控的 macOS、Windows、Linux 构建机上配置 GitHub self-hosted runner，使用独立低权限账户和一次性工作目录。
2. PR 的 quick/full 脚本可本地运行，上传 `acceptance-report.json` 到 PR；报告 commit 必须等于 PR HEAD。
3. ARM64/AMD64 镜像可在支持 BuildKit/QEMU 的自托管 Linux runner 构建；正式晋级仍按 digest。
4. 三端安装包必须在对应 OS 构建和实际安装。不能用单平台交叉编译结果替代三端验收。
5. 本地证据包含命令、source commit、runner OS/架构、时间、退出码、产物 SHA-256；由非提交者复核。
6. 恢复 Actions 后再启用 GitHub-hosted labels；不要为了省额度移除 branch protection 或正式环境 reviewer。

自托管 runner 不提供 GitHub-hosted runner 的一次性隔离；只允许受信任分支和受限 runner group 使用，PR 内容不得在持有发布 secrets 的 runner 上直接执行。参见 GitHub 的 [self-hosted runner 安全说明](https://docs.github.com/en/actions/reference/security/secure-use) 和 [runner groups 访问控制](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/manage-access)。
