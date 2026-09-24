---
name: docker-deployment
description: Use when the user asks to release a version from main as a Draft GitHub Release, or deploy a Published GitHub Release to a Docker Compose production server. Deploy is currently a skeleton only.
---

# Docker Deployment

仅支持 `release` 和 `deploy` 两个操作。当前实现 release；deploy 尚未实现，不得将占位脚本描述为已完成部署，也不得绕过占位脚本临时执行真实部署。

## 操作路由

- **release**：用户要求将当前 main 发布为指定版本时，读取 [references/release.md](references/release.md)，在目标应用仓库中执行本技能的 `scripts/release.sh <version>`。脚本创建并推送 Tag，然后创建 Draft GitHub Release。不要自动 Publish。
- **deploy**：用户要求将指定版本部署到 production 时，读取 [references/deploy.md](references/deploy.md)。当前只能说明未来接口和缺失实现；`scripts/deploy.sh` 始终以非零状态退出。

脚本路径相对于本技能目录；release 的工作目录必须是目标应用仓库。执行 release 前确认版本和目标仓库属于用户要求的发布范围，不要因为用户只要求编写或测试技能就执行真实发布。

## 部署约束

1. Production deployment 必须基于 **Published GitHub Release**；Draft Release 不允许部署。
2. Release 必须对应已存在的 Git Tag；解析 Tag（包括 annotated Tag）对应的 **exact Commit SHA**，并在服务器 checkout 该 SHA。
3. Production 不允许用 `git pull` 确定部署版本。
4. 不输出 secret value，不打印 `.env` 内容，不启用可能泄露凭据的命令跟踪。
5. 不覆盖服务器已有 `.env`；manifest 只记录文件路径和必需的变量名称。
6. Docker image 使用 release version 标签，禁止使用 `latest`。
7. 自动验证成功后仍要求人工业务验证；两种验证状态分别报告，不能将自动通过等同于业务验收完成。

## 资源

- [templates/manifest.yaml](templates/manifest.yaml)：未来部署配置的字段和示例；当前脚本不读取它。
- [templates/release-notes.md](templates/release-notes.md)：人工审阅 Draft 时可参考的说明模板；release 脚本使用 GitHub 自动生成说明。
- `scripts/verify-deployment.sh` 是未来 deploy 的内部辅助脚本，不是第三个技能操作。
