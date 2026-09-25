# Docker Deployment Skill

支持 `release` 和 `deploy`，均由 Skill 引导 Agent 使用 Git、GitHub CLI、SSH 和项目已有命令完成，不内置发布或部署脚本。

```text
main/master 已合并的 previous Tag → HEAD
→ 阅读代码变化 → 分析 migration / env / deployment
→ 询问缺失信息 → 按模板起草 Release Note
→ 开发者确认 → 确认 Tag/Commit → gh 创建 Draft Release
→ 人工 Publish → SSH → 按现有模式更新代码 → 项目部署
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

> 为当前 main 的 HEAD 准备 v0.2.0 Release。查找已合并的上一 Tag，阅读代码差异，整理部署影响；信息不足先问我。展示完整 Release Note，确认后创建 GitHub Draft。

Agent 按 [release 指引](references/release.md) 操作：

1. 用 git/gh 查看仓库、主分支已合并的 Tags 和已有 Release，确定 previous Tag、目标版本和 exact HEAD SHA。
2. 比较 previous Tag → HEAD，阅读相关代码、数据库变化、环境配置和部署文件。
3. 不足的信息询问开发者，不猜测 migration、服务器 `.env`、人工操作或回滚方法。
4. 按 [Release Note 模板](templates/release-note.md) 起草并展示完整内容、版本和 SHA。
5. 开发者确认后，再检查工作区、HEAD 与 Tag；必要时创建并推送 annotated Tag，然后直接用 gh 创建 Draft。

Release Note 必须包含：

| 内容 | 要求 |
| --- | --- |
| 部署内容 | 本次功能、修复及部署方式变化 |
| Database Migration | 明确是否需要；需要时写已确认的内容、命令和顺序 |
| Environment | 明确是否新增/更新服务器 `.env`；只写变量名称、用途和时机 |
| 人工部署与回滚 | 明确是否需要人工步骤；需要时写执行顺序、回滚方式和限制 |
| 人工验收 | 只写业务操作及预期结果，不包含技术测试 |
| 客户更新 | 明确是否需要通知客户以及通知内容，不自动发送 |

确认后由 Agent 使用如下命令创建 Draft（变量来自已确认的版本、仓库和正文）：

```bash
gh release create "$VERSION" \
  --repo "$REPO" \
  --draft \
  --verify-tag \
  --title "$VERSION" \
  --notes-file "$NOTES_FILE"
```

不再调用 `release.sh`。不自动生成 manifest，不自动 commit，不强推或移动 Tag。创建后返回 Draft 链接与 **AWAITING RELEASE REVIEW**，等待人工 Review / Publish。

## Deploy：部署 Published Release

例如向 Agent 提出：

> 部署 v1.3.0 到 production。

Agent 按 [deploy 指引](references/deploy.md) 操作：

1. 本地通过 gh 读取 Release、Tag 和完整 Note，确认已 Published、不是 Draft。
2. 从 Note、项目文档确认部署目录、migration、env 变化、人工步骤与回滚；信息不足就询问。
3. 用现有 SSH Key 免密连接；未配置好则停止，不保存或传递密码。
4. 检查服务器 Git 状态、分支和 origin，有未提交代码就停止。
5. fetch tags 后，按照项目已有 main/master 或 Tag 模式更新代码。
6. 按 Release Note 和项目已有方式处理配置、migration 和人工步骤，执行部署并持续展示脱敏日志。
7. 根据本次变更查验运行结果，输出 Deployment Result，单独列出未勾选的人工业务验收清单。

例如 SSH config：

```sshconfig
Host production
    HostName 192.168.1.100
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Skill 使用 BatchMode 检查免密访问，保留严格主机密钥验证；未知主机或认证失败交给用户处理，不改用密码登录。

## 代码更新模式

| 项目已有模式 | 更新方式 | 版本检查 |
| --- | --- | --- |
| main/master | checkout 对应分支，`git pull --ff-only origin <branch>` | 当前 HEAD 必须包含 Release Tag；报告实际 SHA 和额外提交 |
| Tag | detached checkout Release Tag 对应提交 | 当前 HEAD 与已核实的 Tag commit 完全一致 |

两种模式都先 `git fetch origin --tags` 并核对 Tag。禁止强制覆盖未提交代码或修改已有 Tag。分支模式可能包含比 Release 更新的提交；存在未说明的部署影响时先确认，不能把它描述为精确运行该 Tag。

## 按本次 Release 部署和查验

Compose 项目通常执行 `docker compose build` 和 `docker compose up -d`；有项目现有部署脚本时优先遵循。Migration 按项目和 Note 确定的方式与顺序执行，不套统一时机；需要迁移但方法不明确就询问。

`.env` 只检查变量名称和配置状态，不显示值、不生成 Secret、不自动覆盖文件。变量已存在也不代表本次要求的值更新已完成，需要用户处理的配置必须确认完成后继续。

查验由 **Release Note + 项目配置 + 服务器状态** 决定：至少核对实际 Git 版本，Compose 项目查看 `docker compose ps`，并针对变化检查新增服务、环境变量名称、目录、health endpoint 和 migration 结果。不使用固定“五项通过”。

例如本版新增 worker、REDIS_URL 且需要 migration，就重点确认 app/worker、REDIS_URL、迁移完成状态和项目 health endpoint。业务验收仍单独展示：

```text
Deployment Result
Release: v1.3.0
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
