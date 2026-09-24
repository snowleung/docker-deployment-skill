# Docker Deployment Skill

可复用的 Docker Compose 部署技能，仅提供 `release` 和 `deploy` 两个操作。当前已实现 release；deploy 和自动验证仍为占位脚本，不会连接服务器或执行 Docker。

## 整体流程

```text
main → Tag → GitHub Release → Server Build → Docker Compose → Verification
```

完整目标流程：

```text
main
  → annotated Git Tag（固定 Commit SHA）
  → Draft GitHub Release
  → 人工审阅并 Publish
  → SSH Server
  → checkout exact Commit SHA
  → docker compose build（镜像使用 release version）
  → docker compose up -d
  → automatic verification
  → manual business verification
```

Production 只允许部署 Published GitHub Release，拒绝 Draft。Release 必须对应已存在的 Tag，部署必须解析其 exact Commit SHA，不使用 `git pull` 决定版本，不使用 `latest` 镜像，不覆盖服务器 `.env`，不输出 secret value。自动验证通过后仍须人工业务验证。

## Release：发布当前 main 为 v0.1.0

需要 Bash、Git 和已登录的 GitHub CLI（`gh auth login`），并具备目标仓库的写入权限。

在要发布的应用仓库中运行本技能脚本；如果技能就在当前仓库：

```bash
./scripts/release.sh v0.1.0
```

用于其他项目时，在目标应用仓库中运行 `/path/to/docker-deployment-skill/scripts/release.sh v0.1.0`。确保 GitHub CLI 的目标仓库与该项目的 `origin` 一致。

脚本要求干净的 working tree 和 `main` 分支，获取远端 Tag 后拒绝重复版本，将本地 main 的 HEAD 固定为 annotated Tag 并推送，然后用 `--draft --verify-tag --generate-notes` 创建 GitHub Release。最后输出版本与完整 Commit SHA。

**不会自动 Publish。** 请在 GitHub 上审阅 Draft 后手动发布。版本格式只支持 `vMAJOR.MINOR.PATCH`，不支持前导零、预发布和 build metadata。脚本不会更新本地 main 或验证其与 origin/main 相等，运行前需确认当前 HEAD 是预期发布提交。

失败立即停止；已创建或推送的 Tag 会保留，不会自动删除或覆盖。步骤与恢复方式见 [release 文档](references/release.md)。

## Deploy：部署 v0.1.0 到 production

未来接口：

```bash
./scripts/deploy.sh v0.1.0 production ./manifest.yaml
```

**当前尚未实现**：运行后只输出说明并返回非零状态。`verify-deployment.sh` 同样不会执行验证或返回成功。

后续可从 [manifest 模板](templates/manifest.yaml) 复制配置；`version` 表示发布版本，`environment.required` 只填写变量名称，不存储 secret value。字段约定和待实现流程见 [deploy 文档](references/deploy.md)。

## 目录结构

```text
.
├── SKILL.md
├── README.md
├── scripts/
│   ├── release.sh
│   ├── deploy.sh
│   └── verify-deployment.sh
├── references/
│   ├── release.md
│   └── deploy.md
├── templates/
│   ├── manifest.yaml
│   └── release-notes.md
├── tests/
│   ├── test-release.sh
│   └── test-deploy.sh
├── .gitignore
└── LICENSE
```

## 测试

无需测试框架，使用 Bash 和 Git：

```bash
bash tests/test-release.sh
bash tests/test-deploy.sh
```

Release 测试使用临时 Git 仓库、本地 bare 远端和模拟的 `gh`，覆盖参数、环境检查、失败停止和成功流程；不会向 GitHub 发布。Deploy 测试检查占位脚本返回失败且不调用外部部署工具。

可安装 ShellCheck 后执行静态检查：

```bash
shellcheck scripts/*.sh tests/*.sh
```

## 许可证

[MIT](LICENSE)
