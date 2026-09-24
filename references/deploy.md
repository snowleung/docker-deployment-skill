# Deploy（待实现）

当前脚本只有接口说明并以非零状态退出，不执行 SSH、服务器修改或 Docker deployment。

## 未来接口

```bash
./scripts/deploy.sh v0.1.0 production ./manifest.yaml
```

参数分别是 release version、目标环境和 manifest 路径。V1 目标环境为 production；SSH 目标的配置方式将在后续实现时确定，当前 manifest 不提供凭据。

## 后续流程

1. 校验 manifest，并查询指定版本的 GitHub Release，拒绝 Draft 或不存在的 Release。
2. 确认 Release 对应 Tag 存在，将 Tag 解引用到 exact Commit SHA，不用 Release 的目标分支字段代替提交解析。
3. 通过 SSH 连接已明确配置的服务器，在 `server.deploy_path` 获取该提交并 checkout exact SHA；不得使用 `git pull` 决定版本。
4. 检查服务器 `.env`、必需变量和目录；不覆盖 `.env`，不输出 secret value。
5. 确保 manifest version 与请求版本一致，Compose 的 image 使用该 release version，拒绝 `latest`。
6. 在服务器执行 `docker compose build`，成功后执行 `docker compose up -d`。
7. 调用内部 `verify-deployment.sh <manifest-path>`，验证服务状态、目录及 HTTP 健康检查；失败返回非零状态。
8. 自动验证成功后报告“等待人工业务验证”，列出需人工验收的业务路径并记录人工结果。

## Manifest 约定

从 [manifest.yaml](../templates/manifest.yaml) 复制并填写。顶层 `version` 是 release version，不是 schema 版本。

| 字段 | 含义 |
| --- | --- |
| `application.name` | 应用名称 |
| `server.deploy_path` | 服务器部署目录，绝对路径 |
| `docker.compose_file` | 相对部署目录的 Compose 文件路径 |
| `docker.image` | 带 release version 标签的镜像名称 |
| `environment.file` | 服务器环境文件，相对部署目录解析 |
| `environment.required` | 必需环境变量名称列表；不得包含值 |
| `directories.required` | 部署前必需存在的目录；相对路径基于部署目录 |
| `verify.services` | 自动验证的 Compose 服务名称 |
| `verify.directories` | 自动验证的目录；相对路径基于部署目录 |
| `verify.health.url` | 计划从服务器访问的健康检查 URL，不嵌入凭据 |
| `verify.health.status` | 预期 HTTP 状态码 |

模板目前仅定义约定，尚未提供解析器或运行时校验。SSH 配置、超时和失败恢复策略也需要在 deploy 实现阶段补齐。
