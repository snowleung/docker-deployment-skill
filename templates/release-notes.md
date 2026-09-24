# Release <version>

Commit SHA: `<exact-commit-sha>`

## 变更

- 填写本次功能、修复及关联 PR。

## 部署注意事项

- 填写兼容性变化、数据迁移和配置要求；只写变量名称，不写 secret value。
- 镜像使用本次 release version，保留服务器现有 `.env`。

## 验证

- 自动验证：待部署后记录服务、目录及健康检查结果。
- 人工业务验证：待人工执行并记录关键业务路径和结论。

## 发布前检查

- 确认已存在的 Tag 对应预期 exact Commit SHA。
- 审阅说明后手动 Publish；Draft 不可用于 production deployment。
