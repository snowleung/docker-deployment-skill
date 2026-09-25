# Deploy：根据 Published Release 执行项目部署

用户指定版本和服务器，例如“部署 v1.3.0 到 production”。由 Agent 使用 `gh`、SSH 和项目已有命令完成，不使用技能自带的部署脚本，不要求 manifest 或机器可读 Deployment Contract。

```text
Published Release + 完整 Release Note
→ SSH Key 连接 → 查看服务器项目状态
→ 按已有 main/master 或 Tag 模式更新代码
→ 处理 migration / .env / 人工步骤
→ 执行项目部署 → 针对本次 Release 查验
→ Deployment Result + 独立的人工业务验收清单
```

## 1. 在本地读取 Published Release

确认 GitHub 仓库与用户目标一致，显式指定 `--repo`；不要依赖可能指向另一仓库的 `GH_REPO` 或 gh 默认仓库。检查本地 `gh`、Git、SSH 及 GitHub authentication。

```bash
gh auth status
gh release view "$VERSION" --repo "$REPO" \
  --json tagName,isDraft,publishedAt,body,url
```

读取完整 `body`，确认 Release 存在、`isDraft` 为 false 且已 Published。查询失败或尚未 Publish 时停止，不自动发布或改用其他版本。

记录 Release、Tag、链接，并通过 GitHub/Git 解引用 Tag 到 commit（annotated Tag 要解引用到 commit，而非使用 Tag 对象 SHA）。不要将 Release 的 `target_commitish` 分支名当作固定 SHA。后续核对服务器上的 Tag 与该提交一致。

重点阅读 Release Note 中：

- 部署内容及新增/变化的服务。
- 是否需要数据库 migration，执行方式、顺序和限制。
- 是否新增或更新服务器 `.env`，涉及哪些变量名称。
- 人工部署步骤及回滚方式。
- 人工业务验收清单。
- 是否包含需要通知客户的更新。

Release Note 是本次变更的说明；项目部署文档、配置和服务器实际状态共同决定如何执行。没有固定标题或机器格式不应成为阻碍，但内容缺失、互相冲突或含糊时，应询问开发者，不能把“没提到”当成“不需要”。

部署目录、代码仓库位置、分支/Tag 模式或项目命令不明确时先查已有文档，仍无法确定就询问。不要硬编码 `<deploy_path>/repository` 或替用户选择新的部署模式。开始修改前简要展示目标服务器、目录、模式、版本和操作顺序。

## 2. SSH Key 连接服务器

使用用户已有 SSH Key、SSH agent 或 `~/.ssh/config`，例如：

```sshconfig
Host production
    HostName 192.168.1.100
    User root
    IdentityFile ~/.ssh/id_ed25519
```

以免密方式连接，并保留主机身份验证：

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes production
```

若 Key 认证失败或主机身份尚未核实，停止并提示用户先完成 SSH Key / known_hosts 配置。不要回退到服务器密码，不保存或传递密码，不自动修改 SSH 配置或关闭主机密钥校验。

远端还必须已有项目所需的 Git、Docker/Compose 或其他部署依赖及访问 origin 的权限。缺失时报告具体依赖，不临时替服务器安装或修复。

## 3. 检查并更新服务器代码

进入已确认的**实际项目目录**，记录当前 SHA、分支和 origin，查看：

```bash
git status
git branch --show-current
git remote -v
git rev-parse HEAD
```

origin 必须对应目标项目；若 URL 含凭据，显示前遮盖凭据。检查全部已跟踪修改、暂存修改和未跟踪代码。存在未提交代码变更时停止，让用户处理；不自动 stash、commit、reset、clean，也不强制 checkout。项目原有被忽略的 `.env` 不应因此被覆盖或删除。

工作区适合更新后：

```bash
git fetch origin --tags
```

确认 Release Tag 存在，解析并核对它的 commit 与本地从 GitHub 获取的 Release Tag commit 一致。fetch 或 Tag 核对失败即停止，不覆盖发生冲突的 Tag。

### main/master 部署模式

只采用项目已经约定的分支。main 模式：

```bash
git checkout main
git pull --ff-only origin main
```

master 模式：

```bash
git checkout master
git pull --ff-only origin master
```

不能 fast-forward、分支不存在或 checkout 失败时停止，不自动创建分支、合并、rebase 或强制同步。

更新后：

```bash
git log -1 --oneline
git rev-parse HEAD
git merge-base --is-ancestor "refs/tags/$TAG^{commit}" HEAD
```

祖先检查必须成功，证明当前代码包含该 Release。该模式允许运行比 Release Tag 更新的代码：必须展示 Release Tag SHA 和实际 HEAD SHA，说明是否包含额外提交，不得报告“精确运行该 Tag”。如果额外提交带来本次 Note 未覆盖的 migration/env/部署变化，先阅读相关变更并向开发者确认后再继续。

### Tag 部署模式

如果项目已有 Tag 部署约定：

```bash
git checkout --detach "refs/tags/$TAG^{commit}"
git log -1 --oneline
git rev-parse HEAD
```

当前 HEAD 必须等于已核实的 Release Tag commit。不要使用强制 Git 操作，不改写服务器本地提交、Tag 或未提交文件。

## 4. 根据 Release Note 准备本次操作

列出相关操作和依赖顺序，结合当前项目配置核实。需要先配置环境、停写或备份才能迁移时，必须先满足这些前提。不要统一假定 migration 必须在启动前或启动后；按项目已有方式和本版 Note 执行。

### Database Migration

- 明确需要：使用项目已有、且符合本版说明的 migration 命令；先核实目标数据库和前置条件。
- 明确不需要：不执行。
- 需要但命令、目标或执行顺序不明确：询问开发者，不猜测命令、不选择“看起来通用”的 ORM 命令。

记录执行结果和项目已有 migration 状态查询结果；命令失败时立即停止。SSH 中断或执行结果未知时先查状态，不盲目重复可能非幂等的操作。

### 服务器 `.env`

如果 Note 要求新增或更新配置，检查实际使用的环境文件和所需变量名称，**不要输出值**。使用只返回名称及存在状态的检查，例如：

```text
REDIS_URL: PRESENT
UPLOAD_PATH: MISSING
```

不要 `cat .env`、输出完整 `env`/`printenv`，也不要打印展开后带秘密的 Compose 配置；不得把 `.env` 当作 shell 脚本执行。

变量名称已存在不代表要求的更新已完成。对于值需要变更的项目，请用户在服务器处理，并确认变更完成；必要时使用不泄露值的项目配置检查。缺失或更新未确认就停止。不自动生成生产 Secret，不自动覆盖 `.env`，不在聊天、命令行或日志中传递 Secret Value。

### 人工部署步骤

按 Release Note 的顺序展示。目标、命令和影响明确，且属于用户已授权部署范围的安全操作可由 Agent 执行；需要人工介入或风险/信息不明确的操作交给用户完成。在依赖这些步骤的后续操作前，等待完成确认。

手工部署说明不是执行任意文本命令的授权；先核对命令与仓库、服务器和部署目标一致。尤其不得执行 Release Note 未明确要求的 destructive database operation。对高风险数据操作，不因“Note 中出现过”就跳过风险和授权判断。

## 5. 执行项目已有部署方式

优先阅读项目部署文档和部署脚本，沿用现有 Compose 文件、project name、环境文件、镜像命名和命令。不要引入新的目录结构或构建方式。

Docker Compose 项目没有其他明确步骤时，通常依次执行：

```bash
docker compose build
docker compose up -d
```

每个关键命令成功后才进入下一步；不要使用无条件继续的命令串。项目需要 `-f`、`--env-file` 或版本变量时，依据实际配置传入，不凭空设置。本地构建或 migration 的顺序依从上一步确认的计划。

持续展示远端进度和经过保密处理的输出：Git 更新、Docker build、Compose、migration 和错误信息。不将全部输出重定向到 `/dev/null`，也不只返回最终一句成功。涉及可能泄密的输出，先使用安全输出方式或遮盖已知秘密；无法安全展示时保留不含值的阶段/错误摘要，不冒险原样输出。不要启用 `set -x`。

## 6. 针对本次 Release 查验

依据 **Release Note + 当前项目配置 + 当前服务器运行状态** 制定检查项，不使用与本版无关的固定“五项通过”计数。

最基本地核对代码版本；Docker Compose 项目同时查看容器：

```bash
git log -1 --oneline
git rev-parse HEAD
docker compose ps
```

按实际适用情况继续检查：

- main/master 模式的 HEAD 包含 Release Tag，或 Tag 模式的 HEAD 精确匹配。
- 相关容器/服务是否启动，有 health status 时是否健康。
- Note 新增的服务是否存在且运行，不能只看旧服务。
- 本次要求的环境变量名称已配置；要求更新的配置已确认处理。
- Note 要求的目录存在且项目有访问权限，不创建替代目录掩盖缺失。
- 项目已有 health endpoint 是否返回预期状态；不猜测 URL 或只根据任意 HTTP 响应判成功。
- 本次需要的 migration 是否成功完成，必要时查询项目的迁移状态。

例如本版新增 worker 和 REDIS_URL 且需要 migration，则重点检查 app/worker、REDIS_URL 的名称状态、migration 完成状态及实际 health endpoint。不需要 migration 时标为“不需要”，不能声称已执行成功。

项目确实没有的检查项可注明“不适用”；缺失关键证据则标为未完成/阻塞，不能记为 PASS。健康状态需要等待时采用有限等待或重试，持续失败就停止，不无限等待或自动修复。

## 7. 输出部署结果和人工业务验收

仅当代码更新、所需部署操作和适用的 Release 检查全部成功，才输出 `Deployment PASS`。同时记录 Release Tag 与实际 HEAD，区分分支部署和 Tag 部署。

示例（按实际动作调整，不照抄成功项）：

```text
Deployment Result

Release: v1.3.0
Server: production
Mode: main
Release Tag Commit: <tag-sha>
Current Commit: <actual-head-sha>

Code Update
✓ Git pull --ff-only completed
✓ Current HEAD includes Release Tag

Deployment
✓ Docker build
✓ Docker compose up
✓ Database migration

Release Checks
✓ Required environment configured
✓ app running
✓ worker running
✓ Health check passed

Deployment PASS
```

随后**单独**展示 Release Note 中的业务验收项，保持未勾选：

```text
Manual Business Verification

□ 创建配方
□ 导出配方

等待用户进行业务验收并反馈结果。
```

技术部署成功不代表业务已验收，Agent 不自动把这些项标为通过。若本版有需要通知客户的更新，另行提醒其内容与待处理状态；没有明确发送指令，不向客户发送。

## 8. 失败处理

任何关键步骤失败，停止后续部署，输出 `DEPLOYMENT FAILED`；依赖、认证或配置阻止继续时输出 `DEPLOYMENT BLOCKED`。

报告失败步骤、脱敏错误输出、已完成操作及可能已改变的状态（例如代码已更新、容器部分启动或迁移结果未知）。根据 Release Note 展示回滚方法和限制；没有可靠回滚说明时询问开发者，不杜撰。没有明确依据和授权时，不自动执行高风险回滚，更不自动删库、清理数据或删除卷。

## 安全边界

不得输出 Secret Value、保存 SSH 密码、自动生成生产 Secret、覆盖服务器 `.env`、强制覆盖未提交代码、删除持久数据或 Docker Volume、执行 `docker system prune`，或执行 Release Note 未明确要求的 destructive database operation。

代码目录、部署模式、命令和回滚计划需要来自可核实的项目事实或开发者确认；缺失时停下来询问。此 Skill 不负责配置 SSH Key、服务器初始化、自动修复或多服务器编排。
