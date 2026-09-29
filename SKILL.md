---
name: docker-deployment
description: Use when the user asks to prepare a GitHub release from main or master, review release deployment impacts, or deploy a Published GitHub Release to a single Docker Compose server over SSH.
---

# Docker Deployment

仅支持 `release` 和 `deploy`。在目标应用仓库操作；不要将编写或测试技能视为真实发布、部署授权。

## Release

标准入口：**准备发布 vX.Y.Z**；未提供版本时询问用户。先读取 [references/release.md](references/release.md)。由 Agent 直接使用 `git` / `gh`，不调用 release 专用脚本：

1. `git fetch origin --tags`，确定发布分支 main/master；以上一个最新 Published Release（排除 Draft/prerelease）的 Tag 为起点，以 `origin/main` 或 `origin/master` 当前 HEAD 的 exact SHA 为终点。
2. 核验 `previous_tag..target_sha`；没有新提交则停止，不创建空 Draft。有变更时阅读该范围真实代码，不仅看 commit 标题或文件列表。
3. 分析部署内容、数据库 migration、服务器 `.env` 变化、人工部署步骤及回滚约束。
4. 信息不足就询问开发者，不猜测命令、生产配置或“无需变更”。
5. 按 [templates/release-note.md](templates/release-note.md) 生成完整 Release Note，包含业务人工验收清单及客户更新需求。
6. 将正文、比较范围、目标版本和 SHA 准备完整，直接进入 Draft 创建，不询问正文或创建操作的确认。
7. 再次核对远端发布分支、工作区和 Tag；使用 `gh release create --draft --target "$TARGET_SHA" --notes-file` 创建候选 Draft，不创建、推送或移动正式 Tag。
8. 返回 Draft 链接及 **AWAITING RELEASE REVIEW**。不自动 Publish，不新建其他分支。

Release Note 必须回答：部署什么、是否需要 migration、是否修改服务器 `.env`、人工部署和回滚如何进行、哪些业务需要人工验收、是否有需要通知客户的更新。业务验收不包含技术测试；客户通知仅整理内容，不自动发送。

不自动生成或提交 manifest，不要求额外的机器可读契约。Release Note 为后续部署提供本次变更、操作和业务验收说明。

## Deploy

先读取 [references/deploy.md](references/deploy.md)。标准入口：“部署 v1.4.0 到 production”。Release 负责判断和说明；Deploy 只读取并执行已经审核且 Published 的正式 GitHub Release，由 Agent 使用 gh、SSH 和项目已有命令完成：

1. **Resolve Release**：本地从 GitHub 读取指定 Release、正式 Tag、exact commit SHA 和完整 Release Note，记录链接；不存在、Draft、prerelease、未 Published 或 Tag 无法解析时停止。
2. **Preflight**：以 Note 为部署要求依据，只查项目文档/已有脚本确定如何执行，不重新阅读代码判断 migration、env、部署影响或业务验收。用已有 SSH Key/agent/config 连接，核对目录、origin、工作区、当前 SHA、依赖和执行顺序；信息不足或未提交代码阻塞时停止。
3. **Backup**：修改服务器代码或部署前，必须成功执行项目已有标准备份；失败立即停止。没有已有机制时明确报告并停止，等待安全处置确认，不自行发明备份命令。
4. **Deploy Release Tag**：服务器执行 `git fetch origin --tags` 或等价安全方式，从 GitHub 获取目标代码与 Tag；核对 Tag commit 等于记录的 GitHub SHA，再 detached checkout 精确提交，并验证 `server HEAD == Release Tag SHA`。任何不一致立即停止；不以 main/master 或 git pull 作为部署目标。
5. **Apply Release Instructions**：依照 Note 的前提和顺序，采用项目已有 deploy/Compose 方式部署；明确要求 migration 时按已有标准方式执行。按 Note 检查 `.env` 要求，不猜值、不打印 Secret、不自动覆盖，需要人工处理时停止等待。所有前提必须在依赖操作之前满足，关键失败立即停止，展示脱敏进度。
6. **Verify**：核对实际 Tag/SHA、相关 Docker 服务、health、migration 和 Note 明确要求的技术状态；全部适用技术操作与检查成功才输出 **Deployment PASS**。单独展示 Note 中未勾选的 **Manual Business Verification**，不自动标记通过。

## 共用安全边界

- 不输出 Secret Value，不打印 `.env` 或含秘密的配置/日志，不保存 SSH 密码或自动生成生产 Secret。
- 不自动覆盖服务器 `.env`。变量名称存在不代表要求的值更新已完成；需要用户处理时停止并等待确认。
- 不强制覆盖服务器未提交代码，不自动 stash/reset/clean，不强推、移动或删除已有 Tag。
- 不删除持久化数据或 Docker Volume，不执行 `docker system prune` 或 Release Note 未明确要求的 destructive database operation。
- 失败报告阶段、脱敏错误和已改变的状态，并展示 Release Note 中的回滚方式。没有明确依据和授权，不自动进行高风险回滚。
- 人工业务验收不自动标记通过；客户更新仅整理或提醒，未经明确授权不发送。

## 资源与范围

- [references/release.md](references/release.md)：比较、起草与直接创建 Draft 的流程。
- [references/deploy.md](references/deploy.md)：SSH、代码更新、部署、查验与失败处理。
- [templates/release-note.md](templates/release-note.md)：六类人工作业说明模板。

不内置发布/部署脚本或固定部署 schema，不负责服务器初始化、SSH Key 配置、自动修复、自动高风险回滚或多服务器编排。
