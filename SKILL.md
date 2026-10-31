---
name: docker-deployment
description: Use when the user asks to prepare a GitHub Release from main or master, draft release notes, or review release impacts before publishing.
---

# GitHub Release

仅支持 GitHub Release 的分析、Release Note 起草和 Draft 创建。在目标应用仓库操作；不要将编写或测试技能视为真实发布授权。

## Release

标准入口：**准备发布 vX.Y.Z**；未提供版本时询问用户。先读取 [references/release.md](references/release.md)。由 Agent 直接使用 `git` / `gh`，不调用 release 专用脚本：

1. `git fetch origin --tags`，确定发布分支 main/master；以上一个最新 Published Release（排除 Draft/prerelease）的 Tag 为起点，以 `origin/main` 或 `origin/master` 当前 HEAD 的 exact SHA 为终点。
2. 核验 `previous_tag..target_sha`；没有新提交则停止，不创建空 Draft。有变更时阅读该范围真实代码，不仅看 commit 标题或文件列表。
3. 分析发布内容、数据库 migration、服务器 `.env` 变化、人工部署步骤及回滚约束。
4. 信息不足就询问开发者，不猜测命令、生产配置或“无需变更”。
5. 按 [templates/release-note.md](templates/release-note.md) 生成完整 Release Note，包含业务人工验收清单及客户更新需求。
6. 将正文、比较范围、目标版本和 SHA 准备完整，直接进入 Draft 创建，不询问正文或创建操作的确认。
7. 再次核对远端发布分支、工作区和 Tag；使用 `gh release create --draft --target "$TARGET_SHA" --notes-file` 创建候选 Draft，不创建、推送或移动正式 Tag。
8. 返回 Draft 链接及 **AWAITING RELEASE REVIEW**。不自动 Publish，不新建其他分支。

Release Note 必须回答：发布什么、是否需要 migration、是否修改服务器 `.env`、人工部署和回滚如何进行、哪些业务需要人工验收、是否有需要通知客户的更新。业务验收不包含技术测试；客户通知仅整理内容，不自动发送。

不自动生成或提交 manifest，不要求额外的机器可读契约。流程在创建并核验 Draft 后结束，交由人工 Review / Publish。

## 安全边界

- 不输出 Secret Value，不打印 `.env` 或含秘密的配置/日志。
- 不强制覆盖未提交代码，不自动 stash/reset/clean，不强推、移动或删除已有 Tag。
- migration、环境配置、人工部署及回滚仅写入 Release Note；不连接服务器或执行这些操作。
- Draft 创建失败时停止，查询并报告 Draft/Tag 实际状态和脱敏错误，不自动清理、重试写入或回滚。
- 人工业务验收不自动标记通过；客户更新仅整理或提醒，未经明确授权不发送。

## 资源与范围

- [references/release.md](references/release.md)：比较、起草与直接创建 Draft 的流程。
- [templates/release-note.md](templates/release-note.md)：六类人工作业说明模板。

不内置发布脚本；仅依赖 Git 和已认证的 GitHub CLI。
