# Docker Deployment Skill

支持 `release` 和 `deploy`，均由 Skill 引导 Agent 使用 Git、GitHub CLI、SSH 和项目已有命令完成，不内置发布或部署脚本。

```text
最新 Published Release 的 previous Tag → origin/main 或 origin/master 的 exact SHA
→ 阅读代码变化 → 分析 migration / env / deployment
→ 询问缺失信息 → 按模板起草 Release Note
→ 核对候选 SHA → 直接用 gh 创建 Draft Release（不创建正式 Tag）
→ 人工 Publish → Resolve Release → Preflight → Backup
→ Deploy Release Tag → Apply Release Instructions → Verify
→ 针对 Release 查验 → 人工业务验收
```

不新建其他分支，不自动 Publish，不自动发送客户通知。

## 通过对话安装

将下面这段话复制给支持 Skill 的 Agent：

```text
请安装这个 Skill：
https://github.com/snowleung/docker-deployment-skill

Skill 入口是仓库根目录的 SKILL.md，名称为 docker-deployment。
请完整安装 SKILL.md、references/ 和 templates/，保持相对目录结构。

如果你是 Codex，请使用 skill-installer，从该仓库 main 分支的根目录安装，
安装名称指定为 docker-deployment。

这里只安装技能，不执行真实 release 或 deploy。
```

不要只复制 `SKILL.md`，它引用了 `references/` 和 `templates/` 中的文件。
其他 Agent 按其支持的技能安装方式保存完整目录即可。

## 依赖

| 位置 | 依赖 |
| --- | --- |
| Release 本地 | Git、已认证的 GitHub CLI；由 Agent 阅读代码和生成说明 |
| Deploy 本地 | Git、已认证的 GitHub CLI、OpenSSH client、可用的 SSH Key/agent/config |
| SSH 服务器 | Git、项目已有的部署依赖；Docker Compose 项目需要 Docker/Compose，健康检查使用项目已有工具 |

不再额外要求 Python、YAML 解析器或机器可读部署契约。服务器依赖和 SSH Key 由用户提前准备，Skill 不自动安装或配置。

## Release：准备当前 main/master 的发布说明

例如向 Agent 提出：

> 准备发布 v0.2.0

Agent 按 [release 指引](references/release.md) 操作：

1. fetch origin 和 tags，以最新 Published Release（排除 Draft/prerelease）的 Tag 为起点，以远端 main/master 当前 exact SHA 为终点；版本未提供则询问。
2. 检查 `previous_tag..target_sha`，无新提交则停止；有变更时阅读该范围代码、数据库变化、环境配置和部署文件。
3. 不足的信息询问开发者，不猜测 migration、服务器 `.env`、人工操作或回滚方法。
4. 按 [Release Note 模板](templates/release-note.md) 生成完整内容，并记录版本和 SHA。
5. 核对工作区、远端发布分支与 Tag，直接创建候选 Draft；不创建、推送或移动正式 Tag。

Release Note 必须包含：

| 内容 | 要求 |
| --- | --- |
| 部署内容 | 本次功能、修复及部署方式变化 |
| Database Migration | 明确是否需要；需要时写已确认的内容、命令和顺序 |
| Environment | 明确是否新增/更新服务器 `.env`；只写变量名称、用途和时机 |
| 人工部署与回滚 | 明确是否需要人工步骤；需要时写执行顺序、回滚方式和限制 |
| 人工验收 | 只写业务操作及预期结果，不包含技术测试 |
| 客户更新 | 明确是否需要通知客户以及通知内容，不自动发送 |

Agent 直接使用如下命令创建 Draft（变量来自已核实的版本、仓库和生成的正文）：

```bash
gh release create "$VERSION" \
  --repo "$REPO" \
  --draft \
  --target "$TARGET_SHA" \
  --title "$VERSION" \
  --notes-file "$NOTES_FILE"
```

不再调用 `release.sh`。不自动生成 manifest，不自动 commit，不强推或移动 Tag。创建后返回 Draft 链接与 **AWAITING RELEASE REVIEW**，等待人工 Review / Publish。

## Deploy：部署 Published Release

例如向 Agent 提出：

> 部署 v1.4.0 到 production。

Agent 按 [deploy 指引](references/deploy.md) 执行六步流程。Release 负责判断和说明；Deploy 只执行已审核且 Published 的正式 Release Note：

1. **Resolve Release**：本地从 GitHub 读取指定 Release、正式 Tag、exact commit SHA 和完整 Release Note，记录链接；不存在、Draft、prerelease、未 Published 或 Tag 无法解析时停止。
2. **Preflight**：以 Note 为部署要求依据，只查项目文档/已有脚本确定如何执行，不重新阅读代码判断 migration、env、部署影响或业务验收。用已有 SSH Key/agent/config 连接，核对目录、origin、工作区、当前 SHA、依赖和执行顺序；信息不足或未提交代码阻塞时停止。
3. **Backup**：修改服务器代码或部署前，必须成功执行项目已有标准备份；失败立即停止。没有已有机制时明确报告并停止，等待安全处置确认，不自行发明备份命令。
4. **Deploy Release Tag**：服务器执行 `git fetch origin --tags` 或等价安全方式，从 GitHub 获取目标代码与 Tag；核对 Tag commit 等于记录的 GitHub SHA，再 detached checkout 精确提交，并验证 `server HEAD == Release Tag SHA`。任何不一致立即停止；不以 main/master 或 git pull 作为部署目标。
5. **Apply Release Instructions**：依照 Note 的前提和顺序，采用项目已有 deploy/Compose 方式部署；明确要求 migration 时按已有标准方式执行。按 Note 检查 `.env` 要求，不猜值、不打印 Secret、不自动覆盖，需要人工处理时停止等待。所有前提必须在依赖操作之前满足，关键失败立即停止，展示脱敏进度。
6. **Verify**：核对实际 Tag/SHA、相关 Docker 服务、health、migration 和 Note 明确要求的技术状态；全部适用技术操作与检查成功才输出 **Deployment PASS**。单独展示 Note 中未勾选的 **Manual Business Verification**，不自动标记通过。

例如 SSH config：

```sshconfig
Host production
    HostName 192.168.1.100
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Skill 使用 BatchMode 检查免密访问，保留严格主机密钥验证；未知主机或认证失败交给用户处理，不改用密码登录。

## 精确 Release Tag 部署

唯一代码目标是指定正式 Published Release 的 Tag commit。服务器仍通过 `git fetch origin --tags` 从 GitHub 获取目标代码和 Tag；核对 GitHub exact SHA 后执行 detached checkout。服务器 Tag commit 和实际 HEAD 必须都等于记录的 GitHub SHA；任何不一致立即停止。不采用 main/master 分支部署模式，不以 `git pull` 更新生产目标。

## 按本次 Release 部署和查验

优先采用项目已有 deploy/Compose 方式，不为所有项目硬编码统一 build/up 命令。Migration 按 Note 要求和项目已有标准方式、顺序执行，不套统一时机；需要迁移但方法不明确就询问。

`.env` 只检查变量名称和配置状态，不显示值、不生成 Secret、不自动覆盖文件。变量已存在也不代表本次要求的值更新已完成，需要用户处理的配置必须确认完成后继续。

查验由 **Release Note + 项目配置 + 服务器状态** 决定：至少核对实际 Git 版本，Compose 项目查看 `docker compose ps`，并针对变化检查新增服务、环境变量名称、目录、health endpoint 和 migration 结果。不使用固定“五项通过”。

例如本版新增 worker、REDIS_URL 且需要 migration，就重点确认 app/worker、REDIS_URL、迁移完成状态和项目 health endpoint。业务验收仍单独展示：

```text
Deployment Result
Release: v1.4.0
Server: production
Release Tag Commit: <tag-sha>
Current Commit: <actual-head-sha>

Code Update: PASS
Deployment: PASS
Release Checks: PASS
Deployment PASS

Manual Business Verification
□ 创建配方
□ 导出配方
```

只有所需技术操作和适用检查全部成功才能报告 Deployment PASS。Agent 不自动勾选业务验收，也不会因为 Note 提到客户更新而自动发送通知。

## 失败与安全边界

关键步骤失败立即停止，展示脱敏错误、失败阶段和已发生的修改，依据 Release Note 展示回滚方式。没有明确依据和授权，不自动执行高风险回滚。

不得输出 Secret Value、保存 SSH 密码、生成生产 Secret、覆盖服务器 `.env`、强制覆盖未提交代码、删除持久数据或 Docker Volume、执行 `docker system prune`，或执行 Note 未明确要求的 destructive database operation。

## 文件

```text
SKILL.md
README.md
references/
  release.md
  deploy.md
templates/
  release-note.md
LICENSE
```

旧的发布/部署脚本、契约解析器、相关脚本测试和过时实施计划已移除；不再要求 manifest、额外部署 schema 或 Release asset。部署时使用项目自身的命令，信息不足询问开发者。

## 许可证

[MIT](LICENSE)
