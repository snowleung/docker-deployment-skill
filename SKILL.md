---
name: docker-deployment
description: Use when the user asks to release a version from main on GitHub, or deploy a Published GitHub Release to a single Docker Compose server over SSH.
---

# Docker Deployment

仅支持 `release` 和 `deploy`。命令路径相对于本技能目录；工作目录必须是要发布或部署的应用 Git 仓库。不要将用户要求编写或测试技能视为真实发布、部署授权。

## 操作路由

- **release**：读取 [references/release.md](references/release.md)，运行 `scripts/release.sh <version>`。创建 annotated Tag、推送后创建 Draft GitHub Release；不自动 Publish。
- **deploy**：读取 [references/deploy.md](references/deploy.md)，运行 `scripts/deploy.sh <version> <server>`，例如 `v1.0.0 production-host`。脚本从 Published Release 的 exact commit 读取 `.deploy/manifest.yaml`，输出计划，预检后执行远端部署。路径来自 manifest，不得硬编码业务项目路径或使用工作区 manifest 替代。

## 必须保持的约束

1. Production 只部署 **Published GitHub Release**，拒绝 Draft 和不存在的 Release/Tag。
2. 从 GitHub Tag 解析 **exact Commit SHA**；本地取得的 Tag、服务器 Tag 和 checkout 后 HEAD 必须与之相等。禁止用 `git pull`、`checkout main` 或 moving branch 决定生产版本。
3. Docker image 使用 release version，通过 `APP_VERSION` 传入 Compose；禁止 `latest`。只在 SSH 服务器的本地 Docker daemon 上构建和启动。
4. 不输出密码或 secret value，不打印 `.env` 或 Compose 展开的配置，不启用命令跟踪。构建脚本也不能输出秘密；日志遮盖不能替代这一约束。
5. 不创建或修改 `.env`，不自动创建缺失的持久目录或卷；环境只报告变量名称的 PRESENT/MISSING 状态。
6. 缺少依赖或配置就停止。不得自动安装系统包、修复服务器配置、修改防火墙、删除卷/旧镜像、执行 prune 或破坏性数据库操作。
7. 自动验证通过仅表示五项技术检查通过。最终状态必须为 **AWAITING MANUAL VERIFICATION**；请求用户执行关键业务路径并反馈结果，不得声称业务已经验证。

## 资源与范围

- [templates/manifest.yaml](templates/manifest.yaml)：schema `version: 1`，应提交到应用仓库的 `.deploy/manifest.yaml`，不是 release version。
- [templates/release-notes.md](templates/release-notes.md)：Draft 的人工审阅模板。
- `scripts/verify-deployment.sh <version> <server>`：deploy 的只读辅助工具，重跑相同的五项自动检查，不是第三个技能操作。
- V1 不提供 rollback、镜像 registry 发布、Kubernetes、多服务器编排或自动修复。失败后报告阶段和已发生的动作，人工检查状态，不擅自清理或回滚。
