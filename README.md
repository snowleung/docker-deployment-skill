# Docker Deployment Skill

支持 `release` 和 `deploy`。Release 由 Skill 引导 Agent 直接使用 Git / GitHub CLI，现有 deploy 流程保持不变。

```text
main/master 已合并的 previous Tag → HEAD
→ 阅读代码变化 → 分析 migration / env / deployment
→ 询问缺失信息 → 按模板起草 Release Note
→ 开发者确认 → 确认 Tag/Commit → gh 创建 Draft Release
```

不新建其他分支，不自动 Publish，不自动发送客户通知。

## 依赖

| 位置 | 依赖 |
| --- | --- |
| Release 本地 | Git、已认证的 GitHub CLI；由 Agent 阅读代码和生成说明 |
| Deploy 本地 | Bash、Git、GitHub CLI、OpenSSH client、Python 3.9+（仅标准库） |
| SSH 服务器 | Python 3.9+（标准库）、Git、Docker、本地 Docker daemon、Docker Compose V2、curl |

Release 不再需要专用 Bash/Python 脚本、YAML 解析器或自动文案生成器。现有 deploy 依赖不变。

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

Release 的人工说明不强制包含部署契约。模板末尾保留现有 deploy 所需的 `Deployment Contract` 格式；若要使用现有自动部署脚本，需要另行补齐并确认该部分。缺少契约时 deploy 会按原逻辑停止。

## Deploy：部署 v1.0.0 到服务器

部署上下文来自 Published Release 的 Release Note，仓库里没有 manifest/contract 文件。

```bash
# 从目标应用 Git 仓库执行：
/path/to/docker-deployment-skill/scripts/deploy.sh v1.0.0 root@192.168.1.100
# 也可使用 ~/.ssh/config 中的 host：
/path/to/docker-deployment-skill/scripts/deploy.sh v1.0.0 production-host
```

参数只有 `<version> <server>`。所有项目路径来自 **指定 Published Release 的 Release Note 中的 Deployment Contract**，不会读取当前 working tree 的任何配置。`docker.image: myapp` 是基础镜像名，Compose 应写 `image: myapp:${APP_VERSION}`。Release Note 缺失、Draft、缺 Deployment Contract、字段不完整或含歧义（例如「migration 可能需要」）时 `DEPLOYMENT BLOCKED`：Deploy 不猜测 migration 命令、env 文件、deploy path、持久目录或 services。

脚本先从 GitHub API 确认 Published Release、Tag 和 SHA，解析 Release Note 的 Deployment Contract，再打印 Deployment Plan。之后连接 SSH，检查依赖、Git 仓库、现有环境文件/变量、持久目录、Docker endpoint 和磁盘空间。预检通过才 fetch tags、核对 SHA、detached checkout、build、up、执行 Release Note 声明的 migration，再自动验证。

服务器布局由 Release Note 的 Deployment Contract 决定，例如：

```text
/opt/apps/myapp/             # Deployment.deploy_path
├── repository/             # 提前准备的应用 Git 仓库
└── shared/.env             # 提前准备的环境文件，位于 repository 外
/data/myapp/                # 提前准备的持久目录
```

SSH 使用现有密钥、agent 或 SSH config；启用 BatchMode 和严格主机密钥检查，known_hosts 必须提前核实配置。不接收或存储 SSH password，不转发 agent。

Compose 通过 `--env-file` 读取已有环境文件，以 release 参数设置 `APP_VERSION`，先 build，再 `up -d --no-build --pull never`，最后只执行 Release Note 声明的 migration（必须是 `docker compose exec/run ...`）。构建和启动日志实时输出，并遮盖 `.env` 值及 URL 密码；Dockerfile/构建脚本自身也必须禁止输出 secret。

挂载目录必须已存在，bind mount 要使用 `create_host_path: false`；持久 named volume 只支持已有 external volume。不会自动创建目录、卷或 `.env`。服务器配置、dotenv 支持范围、Compose 示例和恢复边界见 [deploy 文档](references/deploy.md)。

## 验证与结果

自动检查 Git HEAD、服务 running 状态、必需环境变量名称、目录和 HTTP 健康状态码。服务和健康检查有有限重试，不执行自动修复。

成功结果包含：

```text
Deployment: PASS
Git Commit        PASS
Containers        PASS
Environment       PASS
Directories       PASS
Health Check      PASS
5 / 5 PASSED
Status: AWAITING MANUAL VERIFICATION
Manual verification is still required.
```

必须再人工验收关键业务路径。可用内部辅助脚本只读重跑自动检查：

```bash
/path/to/docker-deployment-skill/scripts/verify-deployment.sh v1.0.0 production-host
```

该脚本不执行服务器 checkout、build 或 up。

## 测试

```bash
bash tests/test-deploy.sh
# 如果安装了 ShellCheck：
shellcheck scripts/*.sh tests/*.sh
```

Release 已改为 Skill 引导的 Git/gh 人工审核流程，不再保留原 release 脚本测试。现有 Deploy 测试仍使用 Python 标准库 unittest、临时 Git 仓库及 stub；测试不连接 production，也不创建真实 Release。

## 文件

- `SKILL.md`：技能入口，只支持 release/deploy。
- `scripts/deploy.sh`、`scripts/verify-deployment.sh`：现有 deploy 的 Bash 入口。
- `scripts/contract.py`：Release Note 与 Deployment Contract 解析、歧义/secret 校验（标准库）。
- `scripts/deployment.py`：manifest 解析、SSH 执行、远端部署和共享验证逻辑。
- `scripts/requirements.txt`：本地 YAML 依赖。
- `references/`：release/deploy 操作和失败处理说明。
- `templates/`：标准化 Release Note 模板（人工作业章节 + Deployment Contract）。
- `tests/`：离线 release/deploy 测试。

## 范围与下一步

V1 不实现 rollback、image registry 发布、Kubernetes、多服务器编排、服务器自动初始化或修复。不删除卷、旧镜像，不执行 prune，不修改防火墙，也不执行破坏性数据库操作。

目前自动验证不检查运行镜像 digest、每个副本的健康状态或实际 volume mounts；Compose 配置层会检查版本标签和持久化约束。部署中途失败可能已修改 checkout 或启动部分容器，没有自动恢复。

真实测试服务器的准备和验收步骤见 [验收清单](references/deploy.md#真实测试服务器验收)。

## 许可证

[MIT](LICENSE)
