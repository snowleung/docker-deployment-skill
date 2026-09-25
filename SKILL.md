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

不自动生成或提交 manifest，不要求额外的机器可读契约。Release Note 为后续部署提供本次变更、操作和业务验收说明。

## Deploy

先读取 [references/deploy.md](references/deploy.md)。用户指定版本和服务器，例如“部署 v1.3.0 到 production”。由 Agent 使用 gh、SSH 和项目已有命令执行，不调用技能自带部署脚本：

1. 本地用 gh 获取指定 Published Release、Tag 和完整 Release Note；不存在、未发布或 Draft 就停止。
2. 阅读部署内容、migration、服务器 `.env` 变化、人工步骤、回滚、业务验收和客户更新需求。结合项目文档确认代码目录与部署模式，信息不足先询问。
3. 用已有 SSH Key/agent/config 免密连接；未配置好就停止，不保存或传递服务器密码。
4. 检查服务器 Git 状态、分支和 origin。未提交代码不得覆盖；先 fetch tags，再按已有模式更新：main/master 使用对应分支和 `git pull --ff-only`，Tag 模式切到 Release Tag 的精确提交。
5. 核对版本：分支模式 HEAD 必须包含 Release Tag 的提交，报告实际 SHA 及额外提交；Tag 模式必须精确匹配。额外提交带来的部署影响不明时先确认。
6. 根据 Release Note 和项目已有方式处理 migration、env 及人工步骤，再按确认的顺序执行部署。通常是 Compose build/up；优先采用项目已有脚本。关键步骤失败立即停止，持续展示脱敏输出。
7. 根据本版 Note、项目配置和实际运行状态检查代码、相关服务、配置、目录、health 及 migration。只报告实际适用且已核实的结果，不套固定检查清单。
8. 输出 Deployment Result；技术操作和必要检查通过后可记为 **Deployment PASS**，但必须单独展示未勾选的 **Manual Business Verification**，等待用户验收。

## 共用安全边界

- 不输出 Secret Value，不打印 `.env` 或含秘密的配置/日志，不保存 SSH 密码或自动生成生产 Secret。
- 不自动覆盖服务器 `.env`。变量名称存在不代表要求的值更新已完成；需要用户处理时停止并等待确认。
- 不强制覆盖服务器未提交代码，不自动 stash/reset/clean，不强推、移动或删除已有 Tag。
- 不删除持久化数据或 Docker Volume，不执行 `docker system prune` 或 Release Note 未明确要求的 destructive database operation。
- 失败报告阶段、脱敏错误和已改变的状态，并展示 Release Note 中的回滚方式。没有明确依据和授权，不自动进行高风险回滚。
- 人工业务验收不自动标记通过；客户更新仅整理或提醒，未经明确授权不发送。

## 资源与范围

- [references/release.md](references/release.md)：比较、起草、确认与 Draft 创建流程。
- [references/deploy.md](references/deploy.md)：SSH、代码更新、部署、查验与失败处理。
- [templates/release-note.md](templates/release-note.md)：六类人工作业说明模板。

不内置发布/部署脚本或固定部署 schema，不负责服务器初始化、SSH Key 配置、自动修复、自动高风险回滚或多服务器编排。
