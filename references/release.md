# Release

## 接口与前置条件

在目标应用仓库中运行：

```bash
/path/to/docker-deployment-skill/scripts/release.sh v0.1.0
```

如果当前仓库就是要发布的项目，可用 `./scripts/release.sh v0.1.0`。

需要 Bash、Git、已认证的 GitHub CLI，以及 `origin` 对应仓库的 Tag 推送和 Release 创建权限。Git 必须已配置提交者身份；若启用 Tag 签名，也需可用的签名配置。确保 `gh` 的目标仓库与 `origin` 相同，不要设置指向其他仓库的 `GH_REPO` 或 GitHub CLI 默认仓库。

V1 仅支持带 `v` 前缀的正式 SemVer：`vMAJOR.MINOR.PATCH`，例如 `v0.1.0`。数字段不能有前导零；预发布版本和 build metadata 暂不支持。

## 执行顺序

1. 校验版本参数，检查 `git`、`gh` 和 `gh auth status`。
2. 确认当前位于 Git 工作仓库，working tree clean（包括未跟踪文件）。
3. 获取当前 branch，仅允许 `main`，拒绝 detached HEAD。
4. 执行 `git fetch origin --tags`；失败即退出。
5. 检查同名 Tag 不存在，再解析 `HEAD^{commit}` 为完整 SHA。
6. 为该 SHA 创建 annotated Tag，然后推送 `refs/tags/<version>` 到 origin。
7. 执行 `gh release create <version> --draft --verify-tag --generate-notes`。
8. 输出 release version 和 commit SHA，明确 Release 尚未 Publish。

任意失败以非零状态停止。脚本不会输出 Git/gh 原始诊断，以免远端 URL、凭据或其他敏感信息进入输出；错误提示会指出失败阶段。

发布对象是**本地当前 main 的 HEAD**。fetch 不会合并或更新本地 main，脚本也不检查本地 main 与 origin/main 是否相等。运行前应确认当前提交就是要发布的内容。

## 发布与恢复

创建 Draft 后，人工检查自动生成的说明和 Tag 对应提交，可参考 [release-notes.md](../templates/release-notes.md)，再在 GitHub 上手动 Publish。脚本不会自动 Publish，也不会自动部署。

- Tag 创建失败：检查 Git 身份、签名和权限；不会继续 push 或创建 Release。
- Push 失败：本地 Tag 保留；检查远端是否已接收 Tag（网络错误不一定代表未写入）。
- Release 创建失败：已推送 Tag 保留；检查 GitHub 是否已创建 Draft，再决定恢复操作。
- 重复运行时遇到已有 Tag 会拒绝，不自动删除、重建、强推或改写版本。

恢复时先确认 Tag 仍指向预期 SHA。如果远端 Tag 已存在且确认没有对应 Release，可手动使用同样的 `gh release create <version> --draft --verify-tag --generate-notes` 补建 Draft。恢复不能改变已发布版本的提交映射。
