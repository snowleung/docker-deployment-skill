# Deploy V1

## 接口与输入来源

在目标应用 Git 仓库内执行：

```bash
/path/to/docker-deployment-skill/scripts/deploy.sh v1.0.0 root@192.168.1.100
# 或使用 ~/.ssh/config 中已配置的 host：
/path/to/docker-deployment-skill/scripts/deploy.sh v1.0.0 production-host
```

两个参数分别为 GitHub Release version 和 SSH target。服务器路径等项目配置全部来自 **Release Tag 对应提交中的 `.deploy/manifest.yaml`**。本地工作区可以处于其他分支或有改动，脚本不会读取其 manifest、覆盖其 Tag 或改变其 checkout。

版本须与 Release Tag 相同，且能作为 Docker tag（1–128 个字母、数字、下划线、点、连字符，不能以点或连字符开头，禁止 `latest`）。SSH target 支持 `user@hostname`、IPv4 和 SSH config host；端口、密钥和跳板机通过 SSH config 配置，V1 不直接接受 IPv6 字面量或 SSH 选项。

## 依赖和服务器准备

本地需要 Bash、Git、已认证的 `gh`、OpenSSH client、Python 3.9+ 和 PyYAML 6.x。PyYAML 用于真实 YAML 解析，采用 SafeLoader 并拒绝重复键、未知字段和错误类型；不会使用 grep/sed 解析 YAML。

远端需要 Python 3.9+（仅标准库，不需要 PyYAML）、Git、Docker、支持 `config --format json` 的 Docker Compose V2、curl。需要现有的本地 Unix socket Docker context；拒绝 `DOCKER_HOST` override 和指向另一台机器的 context。Docker 数据目录必须可读取磁盘空间，部署账户还需访问 Docker daemon。

服务器必须提前准备：

- `server.deploy_path` 和其中的 `repository` Git 仓库；该目录本身必须是仓库根目录、工作区干净，origin 对应本次 GitHub 项目。
- `environment.file` 指向可读的现有文件，且其真实路径位于 repository 外。
- manifest 所列的持久目录，真实路径位于 repository 外，部署账户具有读、写和进入权限。
- 仓库和 Docker 数据所在文件系统各至少 1 GiB 可用空间。这是最低门槛，不保证足够构建所有项目。
- 服务器已有访问 Git origin 的权限；脚本不复制 GitHub token 或 SSH 私钥。

脚本不自动安装包、clone 仓库、创建目录、写入 `.env`、改变 Docker context 或修复权限。

## SSH authentication

使用现有密钥、SSH agent 或 `~/.ssh/config`。启用 `BatchMode=yes`、`StrictHostKeyChecking=yes` 和 10 秒连接超时；known_hosts 必须已由用户核实配置。脚本不提示输入 SSH password，不将密码写入命令行、manifest、仓库或日志；不启用 agent forwarding。

经 SSH stdin 发送技能辅助代码和不含 secret value 的配置，在内存中执行，不上传临时文件或安装远端依赖。远端读取 `.env`，仅输出变量名称，例如 `DATABASE_URL: PRESENT`。

## 执行流程

```text
Published Release → Tag → exact Commit → commit-owned manifest
→ Deployment Plan → SSH precheck → checkout exact Commit
→ Server Build → Docker Compose up → Automatic Verification
→ AWAITING MANUAL VERIFICATION
```

1. 检查本地依赖、GitHub authentication、当前 Git 仓库。根据 origin 明确指定 GitHub 仓库，忽略 `GH_REPO` 和 gh 默认仓库；V1 支持 github.com 的标准 HTTPS/SSH origin，不支持凭据嵌入 URL 或 GitHub Enterprise。
2. 读取 Release 并拒绝 Draft/未 Publish 状态。通过 GitHub Git refs API 确认 Tag 存在，递归解析 annotated Tag，得到完整 SHA；不使用 Release 的目标分支字段代替 SHA。
3. 在本地临时 Git 仓库 fetch 指定 Tag，核对 GitHub SHA，使用 `git show <sha>:.deploy/manifest.yaml` 读取、严格校验 manifest。完成后删除本地临时仓库。
4. 连接 SSH 前输出 Deployment Plan：Application、Release、Tag/Commit、Server、Deploy Path、Compose、版本化 Image、必需环境变量名称、目录和健康检查 URL。此时不修改服务器。
5. SSH 连接成功后检查远端 Python/Git/Docker/Compose/curl、Docker daemon/endpoint、目录、Git origin、干净工作区、环境文件及变量、持久目录和磁盘空间。失败输出 `DEPLOYMENT BLOCKED`，不进入 fetch/checkout/build。
6. 在 `<deploy_path>/repository` 执行 `git fetch origin --tags`，解析服务器上的 `refs/tags/<tag>^{commit}`。必须等于预期 SHA，否则停止。然后 `git checkout --detach <sha>`，再次确认 HEAD。checkout 禁用 Git hooks，不自动处理冲突或脏工作区。
7. 校验指定 Compose 文件位于仓库内，读取 `docker compose config --format json` 的结果但不打印其中的环境值。确认要求的服务存在、应用镜像使用 `<docker.image>:<release>` 并配置 build，所有服务镜像都有显式版本且不使用 `latest`。检查挂载配置，阻止自动创建持久目录和卷。
8. 设置 `APP_VERSION=<release>`，以 manifest 的应用名称作为 Compose project name，指定 `--env-file <environment.file>` 和 `-f <compose_file>`，执行 build，成功后执行 `up -d --no-build --pull never`，再输出 `docker compose ps`。后两个 flag 保证启动阶段不另行构建或拉取镜像；第三方服务镜像须提前在服务器上准备。Docker build 自身可能需要下载基础镜像或构建依赖。
9. 执行下述自动验证。任意失败输出 `DEPLOYMENT FAILED` 并停止；不自动重启、清理或回滚。SSH 中断时远端结果可能未知，应人工检查后再决定后续操作。
10. 五项通过后输出 `5 / 5 PASSED` 和 `AWAITING MANUAL VERIFICATION`，请求用户验收关键业务操作。不能将技术通过报告为业务验收完成。

## Manifest schema 1

从 [模板](../templates/manifest.yaml) 复制到应用项目的 `.deploy/manifest.yaml`，在创建 Release 前提交。所有字段必需；列表不可有重复项。`verify.services` 至少一项；环境变量和目录列表允许为空，以支持无持久化存储的应用。

| 字段 | 含义和约束 |
| --- | --- |
| `version` | 整数 `1`，schema 版本，不是 release version |
| `application.name` | Compose project name，小写字母/数字开头，允许下划线、连字符 |
| `server.deploy_path` | 服务器部署目录的绝对路径 |
| `docker.compose_file` | repository 内相对路径，不允许 `..` |
| `docker.image` | 镜像基础名称，不含 tag、digest 或 registry port |
| `environment.file` | repository 外现有环境文件的绝对路径 |
| `environment.required` | 必需环境变量名称列表，值需存在且非空 |
| `directories.required` | 部署前须存在且可访问的持久目录绝对路径列表 |
| `verify.services` | 须处于 running 状态的 Compose 服务名称列表 |
| `verify.directories` | 自动验证需检查的目录绝对路径列表，预检也检查 |
| `verify.health.url` | 从服务器访问的 HTTP(S) URL，不含 userinfo、query 或 fragment |
| `verify.health.status` | 预期 HTTP 状态码，整数 |

manifest 不存储 secret value。路径目前限可打印 ASCII，不允许路径遍历。不要将远端密码或 token 填入健康检查 URL。

## Environment 与 Compose 合约

`.env` 只支持单行字面量 `NAME=value`、`NAME='value'`、`NAME="value"`，可带 `export`、空行和注释。支持行尾注释；不支持多行、双引号转义、变量插值或重复键。包含 `$`、反引号或反斜线的字面值请用单引号。值不会被 shell source/eval。

`PATH`、`HOME`、`PYTHONPATH`、`LD_PRELOAD`、`LD_LIBRARY_PATH`、`BASH_ENV`、`ENV` 以及 `DOCKER_*`/`COMPOSE_*` 是保留的运行配置，不得放进应用 `.env`。脚本通过 `--env-file` 给 Compose 提供值，并清除同名的继承环境值以防覆盖；`APP_VERSION` 始终由 release 参数决定。

`--env-file` 负责 Compose 插值，不会自动把所有变量注入容器。应用的 Compose 文件应明确引用所需变量，例如：

```yaml
services:
  app:
    image: myapp:${APP_VERSION}
    build: .
    environment:
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}
    ports:
      - "127.0.0.1:3000:3000"
    volumes:
      - type: bind
        source: /data/myapp
        target: /app/data
        bind:
          create_host_path: false
```

bind source 必须已存在；须使用长格式并明确 `create_host_path: false`，拒绝默认可能创建目录的短格式。持久化 named volume 只支持提前准备的 `external: true` 卷，拒绝匿名持久卷；tmpfs 可用。不会删除或创建卷，也不会更改挂载配置。相关约定参见 [Docker bind mount 文档](https://docs.docker.com/reference/compose-file/services/#volumes) 和 [external volume 文档](https://docs.docker.com/reference/compose-file/volumes/#external)。

Docker 命令的 stdout/stderr 会实时合并输出，遮盖服务器 `.env`、继承环境、Compose 展开的 environment/build args 中的值、URL 密码及常见编码形式；配置展开结果和 Git 原始错误不直接输出。**发布的 Dockerfile/构建脚本必须禁止打印 secret**：无法可靠识别任意拆分、加密或其他变换后的秘密，日志过滤不替代这一要求。

## Automatic Verification

五项必需检查：

1. Git Commit：服务器 HEAD 与预期 SHA 一致。
2. Containers：manifest 要求的服务均出现在 Compose 的 running 服务列表。
3. Environment：现有环境文件可读，必需变量名称存在且值非空；只输出名称。
4. Directories：必需目录及 verify 目录存在、可访问。
5. Health Check：服务器发起 HTTP 请求，状态码等于 manifest 预期；不输出响应正文。

服务和健康检查最多尝试 3 次，间隔 1 秒；每次 HTTP 连接超时 3 秒，总请求超时 5 秒。不自动修复服务。当前不验证每个副本的健康状态、运行镜像 digest 或容器实际挂载状态；构建前的镜像标签/挂载配置检查也不等于这些运行时检查。

可独立重跑只读验证：

```bash
/path/to/docker-deployment-skill/scripts/verify-deployment.sh v1.0.0 production-host
```

该辅助命令重新解析 Published Release 和 manifest，预检并验证，不执行远端 fetch、checkout、build 或 up。

## 真实测试服务器验收

1. 选择可丢弃的测试服务器；人工准备依赖、SSH/known_hosts、仓库、外置 `.env`、目录、必要的第三方镜像和 external volumes。
2. 在测试应用仓库提交 schema 1 manifest、符合上述合约的 Compose 和 Dockerfile。健康端点应从服务器可访问。
3. 从应用 main 创建一个新版本 Draft，人工检查 Tag/SHA 和配置后手动 Publish。现有技能仓库 `v0.1.0` 不含应用 `.deploy/manifest.yaml`，不能直接用于本次部署验收。
4. 在应用仓库运行 `deploy.sh <version> <test-host>`，核对 plan、SHA、实时日志和五项结果；前后核对服务器 `.env` 未改变。
5. 人工检查关键业务路径、数据持久性和应用日志，记录结论。自动输出必须保持等待人工验证。
6. 在测试环境分别模拟缺失环境变量、目录、构建失败和健康失败，确认停止阶段且没有自动修复或清理。

V1 不实现 rollback、registry 发布/推送、Kubernetes、多服务器编排、自动服务器初始化或失败恢复。部署失败可能已切换代码或启动部分容器，必须先人工确认状态。
