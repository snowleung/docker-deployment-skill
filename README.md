# GitHub Release Skill

由 Skill 引导 Agent 使用 Git 和 GitHub CLI 分析代码、起草 Release Note 并创建 GitHub Draft Release，不内置发布脚本。

```text
最新 Published Release 的 previous Tag → origin/main 或 origin/master 的 exact SHA
→ 阅读代码变化 → 分析 migration / env / deployment
→ 询问缺失信息 → 按模板起草 Release Note
→ 核对候选 SHA → 直接用 gh 创建 Draft Release（不创建正式 Tag）
→ 人工 Review / Publish
```

不新建其他分支，不自动 Publish，不自动发送客户通知。Release Note 保留 migration、环境配置、人工部署与回滚及业务验收说明；Skill 不连接服务器或执行部署。

## 通过对话安装

将下面这段话复制给支持 Skill 的 Agent：

```text
请安装这个 Skill：
https://github.com/snowleung/docker-deployment-skill

Skill 入口是仓库根目录的 SKILL.md，名称为 docker-deployment。
请完整安装 SKILL.md、references/ 和 templates/，保持相对目录结构。

如果你是 Codex，请使用 skill-installer，从该仓库 main 分支的根目录安装，
安装名称指定为 docker-deployment。

这里只安装技能，不执行真实 release。
```

不要只复制 `SKILL.md`，它引用了 `references/` 和 `templates/` 中的文件。
其他 Agent 按其支持的技能安装方式保存完整目录即可。

## 依赖

本地需要 Git 和已认证的 GitHub CLI；由 Agent 阅读代码和生成说明。

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
| 发布内容 | 本次功能、修复及部署方式变化 |
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

## 失败与安全边界

关键步骤失败立即停止，展示脱敏错误、失败阶段和 Draft/Tag 实际状态；不自动清理、重试写入或回滚。

不得输出 Secret Value 或生产 `.env`，不得强制覆盖未提交代码或移动、删除已有 Tag。人工业务验收保持未勾选，客户更新仅整理内容。

## 文件

```text
SKILL.md
README.md
references/
  release.md
templates/
  release-note.md
LICENSE
```

## 许可证

[MIT](LICENSE)
