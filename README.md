# Docker Deployment Skill

可复用的单服务器 Docker Compose 部署技能，支持 `release` 和 `deploy`。

```text
main → Git Tag → GitHub Release（先 Draft，人工 Publish）
     → exact Commit SHA → SSH Server Build → Docker Compose
     → Automatic Verification → Manual Verification
```

Production 仅部署 Published Release；拒绝 Draft。Tag 必须存在，服务器 checkout 的 exact Commit SHA 必须与 GitHub 一致。禁止 `git pull` 决定版本、`latest` 镜像、输出 secret value、覆盖服务器 `.env` 或自动修复缺失配置。

## 依赖

| 位置 | 依赖 |
| --- | --- |
| Release 本地 | Bash、Git、已认证的 GitHub CLI |
| Deploy 本地 | Bash、Git、GitHub CLI、OpenSSH client、Python 3.9+、PyYAML 6.x |
| SSH 服务器 | Python 3.9+（标准库）、Git、Docker、本地 Docker daemon、Docker Compose V2、curl |

PyYAML 是唯一额外的 Python 依赖，用于可靠、安全地解析 YAML 和严格校验 manifest。远端不需要安装 PyYAML。可在技能目录手动准备本地环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r scripts/requirements.txt
```

脚本会检测依赖，缺失就停止，不安装系统 package。

## Release：发布当前 main 为 v0.1.0

在要发布的应用仓库内运行；技能位于当前仓库时：

```bash
./scripts/release.sh v0.1.0
```

检查依赖、gh 认证、干净工作区和 main 分支 → fetch tags → 拒绝重复 Tag → 解析本地 HEAD → 创建并推送 annotated Tag → 用 `--draft --verify-tag --generate-notes` 创建 GitHub Release → 输出版本和 SHA。

**不会自动 Publish 或推送 main 分支。** 版本格式为 `vMAJOR.MINOR.PATCH`，暂不支持预发布或 build metadata。本地 main 不会被自动更新，也不要求等于 origin/main。请先确认 HEAD 是预期提交，随后人工审阅 Draft 并 Publish。重复版本会拒绝；部分失败不会删除已创建的 Tag。详见 [release 文档](references/release.md)。

## Deploy：部署 v1.0.0 到服务器

从 [manifest 模板](templates/manifest.yaml) 创建应用项目的 `.deploy/manifest.yaml`，连同 Dockerfile、Compose 提交后再发布 Release。

```bash
# 从目标应用 Git 仓库执行：
/path/to/docker-deployment-skill/scripts/deploy.sh v1.0.0 root@192.168.1.100
# 也可使用 ~/.ssh/config 中的 host：
/path/to/docker-deployment-skill/scripts/deploy.sh v1.0.0 production-host
```

参数只有 `<version> <server>`。所有项目路径来自 **指定 Release 的 commit 中的 manifest**，不会读取当前 working tree 的 manifest。顶层 `version: 1` 是 schema 版本；`docker.image: myapp` 是基础镜像名，Compose 应写 `image: myapp:${APP_VERSION}`。

脚本先从 GitHub API 确认 Published Release、Tag 和 SHA，再打印 Deployment Plan。之后连接 SSH，检查依赖、Git 仓库、现有环境文件/变量、持久目录、Docker endpoint 和磁盘空间。预检通过才 fetch tags、核对 SHA、detached checkout、build、up 和自动验证。

服务器布局由 manifest 决定，例如：

```text
/opt/apps/myapp/             # server.deploy_path
├── repository/             # 提前准备的应用 Git 仓库
└── shared/.env             # 提前准备的环境文件，位于 repository 外
/data/myapp/                # 提前准备的持久目录
```

SSH 使用现有密钥、agent 或 SSH config；启用 BatchMode 和严格主机密钥检查，known_hosts 必须提前核实配置。不接收或存储 SSH password，不转发 agent。

Compose 通过 `--env-file` 读取已有环境文件，以 release 参数设置 `APP_VERSION`，先 build，再 `up -d --no-build --pull never`。构建和启动日志实时输出，并遮盖 `.env` 值及 URL 密码；Dockerfile/构建脚本自身也必须禁止输出 secret。

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
bash tests/test-release.sh
bash tests/test-deploy.sh
# 如果安装了 ShellCheck：
shellcheck scripts/*.sh tests/*.sh
```

Release 测试使用临时 Git 仓库和模拟 gh；Deploy 测试使用 Python 标准库 unittest、真实临时 Git 仓库及 gh/SSH/Docker/curl stub，远端逻辑只在临时本地目录执行。测试不连接 production，也不创建真实 Release。

## 文件

- `SKILL.md`：技能入口，只支持 release/deploy。
- `scripts/release.sh`、`deploy.sh`、`verify-deployment.sh`：Bash 入口。
- `scripts/deployment.py`：manifest 解析、SSH 执行、远端部署和共享验证逻辑。
- `scripts/requirements.txt`：本地 YAML 依赖。
- `references/`：release/deploy 操作和失败处理说明。
- `templates/`：manifest、release notes 模板。
- `tests/`：离线 release/deploy 测试。

## 范围与下一步

V1 不实现 rollback、image registry 发布、Kubernetes、多服务器编排、服务器自动初始化或修复。不删除卷、旧镜像，不执行 prune，不修改防火墙，也不执行破坏性数据库操作。

目前自动验证不检查运行镜像 digest、每个副本的健康状态或实际 volume mounts；Compose 配置层会检查版本标签和持久化约束。部署中途失败可能已修改 checkout 或启动部分容器，没有自动恢复。

真实测试服务器的准备和验收步骤见 [验收清单](references/deploy.md#真实测试服务器验收)。

## 许可证

[MIT](LICENSE)
