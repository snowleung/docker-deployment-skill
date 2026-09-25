---
name: docker-deployment
description: Use when the user asks to prepare a GitHub release from main or master, review release deployment impacts, or deploy a Published GitHub Release to a single Docker Compose server over SSH.
---

# Docker Deployment

仅支持 `release` 和 `deploy`。在目标应用仓库操作；不要将编写或测试技能视为真实发布、部署授权。

## Release

先读取 [references/release.md](references/release.md)。由 Agent 直接使用 `git` / `gh`，不调用 release 专用脚本：

1. 查看 main/master 已合并的 Tags 和 GitHub Release，确认 previous Tag、目标版本和当前 HEAD 的 exact Commit SHA。
2. 比较 previous Tag → HEAD，阅读相关代码，不仅看 commit 标题或文件列表。
3. 分析部署内容、数据库 migration、服务器 `.env` 变化、人工部署步骤及回滚约束。
4. 信息不足就询问开发者，不猜测命令、生产配置或“无需变更”。
5. 按 [templates/release-note.md](templates/release-note.md) 生成完整 Release Note，包含业务人工验收清单及客户更新需求。
6. 展示正文、比较范围、目标版本和 SHA，取得开发者确认。
7. 再次核对 HEAD、工作区和 Tag，必要时为确认的 SHA 创建并推送 annotated Tag；使用 `gh release create --draft --verify-tag --notes-file` 创建 Draft。
8. 返回 Draft 链接及 **AWAITING RELEASE REVIEW**。不自动 Publish，不新建其他分支。

Release Note 必须回答：部署什么、是否需要 migration、是否修改服务器 `.env`、人工部署和回滚如何进行、哪些业务需要人工验收、是否有需要通知客户的更新。业务验收不包含技术测试；客户通知仅整理内容，不自动发送。

不自动生成或提交 manifest，不强制为普通 Release Note 收集 Deployment Contract。只有开发者还要求准备现有自动部署流程时，才按 deploy 文档补齐契约并一并确认。

## Deploy

读取 [references/deploy.md](references/deploy.md)，运行 `scripts/deploy.sh <version> <server>`，例如 `v1.0.0 production-host`。从 Published Release 的 Release Note 读取 `## Deployment Contract`，生成 Deployment Plan，预检后 SSH 执行。不补充任何缺失的部署事实。

## 部署约束（沿用现有流程）

1. GitHub Release Note 是 Release → Deploy 唯一的部署上下文。业务仓库不保存 manifest / manifest.yaml / deployment.json / contract 文件，Release 不上传额外 asset，不使用 PyYAML、jsonschema 或 yq。
2. Production 只部署 **Published GitHub Release**，拒绝 Draft 和不存在的 Release/Tag。
3. 从 GitHub Tag 解析 **exact Commit SHA**；Release Note 的 `commit_sha`、服务器 Tag 和 checkout 后 HEAD 必须与之相等。禁止用 `git pull`、`checkout main` 或 moving branch 决定生产版本。
4. Deploy 阶段 AI 只能 read / interpret / validate / plan / execute / verify。Release Note 存在缺失或歧义（例如「migration 可能需要」）时 `DEPLOYMENT BLOCKED`，不得猜测 migration 命令、env 文件、deploy path、持久目录、services 或 destructive 命令。
5. Docker image 使用 release version，通过 `APP_VERSION` 传入 Compose；禁止 `latest`。只在 SSH 服务器的本地 Docker daemon 上构建和启动。
6. 不输出密码或 secret value，不打印 `.env` 或 Compose 展开的配置，不启用命令跟踪。Release Note 只记录环境变量名称。构建脚本也不能输出秘密；日志遮盖不能替代这一约束。
7. 不创建或修改 `.env`，不自动创建缺失的持久目录或卷；环境只报告变量名称的 PRESENT/MISSING 状态。
8. 缺少依赖或配置就停止。不得自动安装系统包、修复服务器配置、修改防火墙、删除卷/旧镜像、执行 prune、或执行 Release Note 未明确声明的 migration/destructive 命令。
9. 自动验证通过仅表示五项技术检查通过。最终状态必须为 **AWAITING MANUAL VERIFICATION**；请求用户按 Release Note 的人工验收清单执行业务路径并反馈结果，不得声称业务已经验证。

## 资源与范围

- [templates/release-note.md](templates/release-note.md)：人工作业章节，以及保留的 Deployment Contract 模板。
- `scripts/contract.py`：现有 Release Note 与 Deployment Contract 的解析/校验（标准库），供 deploy 使用。
- `scripts/verify-deployment.sh <version> <server>`：deploy 的只读辅助工具，重跑相同的五项自动检查，不是第三个技能操作。
- V1 不提供自动 rollback、镜像 registry 发布、Kubernetes、多服务器编排或自动修复。Release Note 中经确认的人工回滚说明不代表自动执行回滚。
