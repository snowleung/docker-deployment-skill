# Release <version>

比较范围：<previous tag → target tag；首次发布则注明首次发布>
Commit：<完整 SHA>

<!-- 使用前替换所有占位说明。结论必须来自代码分析或开发者确认；不要默认“无需”。 -->

## 部署内容

- <本次交付的业务功能或修复，以及用户可感知的变化>
- <相关服务、依赖或部署方式的变化；无变化则删除此项>

## Database Migration

是否需要：<是 / 否，选择一个>

- <若需要：迁移内容、已确认的命令、执行顺序，以及数据兼容性或不可逆限制>
- <若不需要：简要说明判断依据>

## Environment

是否需要修改服务器 `.env`：<是 / 否，选择一个>

- 新增变量：<变量名称、用途和配置时机；无则写“无”>
- 更新变量：<变量名称、用途和更新时机；无则写“无”>

<!-- 只写变量名称和用途，不写密码、Token、API Key、连接串凭据等值。 -->

## 人工部署与回滚

是否需要额外人工部署：<是 / 否，选择一个>

- <若不需要：写“无需额外人工部署步骤。”>
- <若需要：按顺序列出前置条件和已确认的人工操作>
- <若需要：说明回滚步骤、兼容性前提和不能回滚的部分；不要默认代码回退可以撤销数据库变更>

## 人工验收

- [ ] <本次变化涉及的核心业务操作及预期结果>
- [ ] <必要的兼容性或权限业务场景；不适用则删除>

<!-- 仅业务验收，不包含单元测试、接口测试、CI、lint、health check 或 Docker 状态。 -->

## 客户更新

是否需要通知客户：<是 / 否，选择一个>

- <若需要：摘要客户可见的变化、操作方式变化及客户需执行的操作>
- <若不需要：写明本次无需客户通知>

<!-- 这里只整理通知内容，不自动向客户发送。 -->

## Deployment Contract

> 以下各节是 Deploy 的唯一执行依据：字段必须确定、无歧义，禁止任何 secret value。

### Source

- tag: vX.Y.Z
- commit_sha: <40-character commit sha>
- repository: owner/repo

### Runtime

- application: myapp
- compose_file: compose.yaml
- image: myapp
- services: app, worker
- ports: 3000:3000

### Environment

- file: /opt/apps/myapp/shared/.env
- required: DATABASE_URL, REDIS_URL, UPLOAD_PATH

### Persistent Directories

- /data/myapp

### Deployment

- deploy_path: /opt/apps/myapp
- migration: none
- restart: docker compose up -d

### Verification

- services: app, worker
- health_url: http://127.0.0.1:3000/health
- health_status: 200

### Manual Verification

- 登录后访问关键业务路径并确认结果。
- 记录人工验证结论。
