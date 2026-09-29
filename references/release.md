# Release：分析并直接创建 Draft

Release 由 Agent 使用 `git` / `gh` 完成，不再提供 release 脚本或自动文案生成器。Release Note 写给开发者和发布审核人员，不能仅用 commit 标题或文件列表代替代码分析。

```text
最新 Published Release 的 previous Tag → origin/main 或 origin/master 的 exact SHA
→ 阅读代码差异 → 分析 migration / env / deployment
→ 补齐必要信息 → 按模板起草
→ 固定 target SHA → gh 创建候选 Draft（不创建正式 Tag）
```

只使用当前仓库和现有 main/master，不新建其他分支。不自动 commit、不自动 Publish、不部署、不执行 migration，也不发送客户通知。

## 1. 确定仓库、提交和 previous Tag

检查 Git、GitHub CLI 和认证，确认 origin 对应的 GitHub 仓库。所有 `gh` 调用显式指定同一个 `--repo`，不要依赖可能指向其他项目的 `GH_REPO` 或 CLI 默认仓库。

标准入口为“准备发布 vX.Y.Z”。用户提供版本则直接使用，未提供则询问，不自行推断版本号。

1. 检查工作区、当前分支和 origin，执行 `git fetch origin --tags`。根据项目约定及远端默认分支确定 main/master；无法确定时询问。确认 fetch 已更新所选远端跟踪分支（窄 refspec 时显式 fetch 该分支）。记录 `TARGET_SHA=$(git rev-parse "refs/remotes/origin/$RELEASE_BRANCH^{commit}")`；即使当前在 feature 分支，也不用本地 HEAD，不切换或合并分支。
2. 分页读取 GitHub Releases，排除 Draft、prerelease 和未 Published 的条目，按 `published_at` 选最新正式 Release 的 Tag。不使用最大版本号、最近可达 Tag 或 GitHub Latest 标记代替这一规则。读取该 Release Note 作为背景；查询失败不能视为首次发布。`gh api` 使用已核实的 `repos/$REPO/releases` 路径（不支持 `--repo`），可用 `--paginate --slurp` 汇总后筛选。
3. 解引用 previous Tag 到 commit，并验证它是 `TARGET_SHA` 的祖先；缺失、冲突或非祖先时停止并说明，不回退选旧 Tag。记录 previous Tag、previous SHA、目标版本和完整 `TARGET_SHA`。
4. 范围固定为 `previous_tag..target_sha`；用 `git rev-list --count "$PREVIOUS_TAG..$TARGET_SHA"` 检查，无新提交则停止，不创建空 Draft。确认没有任何正式 Release 时按首次发布分析目标 SHA 的完整代码，明确注明首次发布，不虚构 previous Tag。

## 2. 比较 previous Tag → target SHA，并阅读相关代码

先看范围，再读具体变更及相关调用方；文件内容也从目标提交读取（如 `git show "$TARGET_SHA:path/to/file"`），避免混入当前 feature 分支或未提交改动：

```bash
git log --oneline "$PREVIOUS_TAG..$TARGET_SHA"
git diff --stat "$PREVIOUS_TAG" "$TARGET_SHA"
git diff --name-status "$PREVIOUS_TAG" "$TARGET_SHA"
git diff "$PREVIOUS_TAG" "$TARGET_SHA" -- <相关文件>
```

重点阅读：

- 功能入口、业务逻辑、权限、用户可见行为及兼容性变化。
- migration、数据库 schema、ORM model、数据回填和迁移运行方式。没有新增 migration 文件不等于无需迁移。
- `.env.example`、配置读取点和 Compose 环境变量引用。只记录变量名称、用途、是否新增/更新；不展示生产 `.env` 或 secret value。
- Dockerfile、Compose、服务、依赖、端口、挂载、构建与启动方式。
- 部署文档、上一个 Release Note、人工操作和回滚约束。上一版说明只作为背景，不能原样沿用为本版事实。

不要在输出中粘贴可能包含凭据的原始 diff、配置或命令日志。说明应基于阅读后的业务和部署影响，而不是把全部技术改动罗列成流水账。

## 3. 缺失信息向开发者询问

无法从仓库可靠确定时，先提出具体问题，继续阅读其他独立部分。重点确认：

- 是否需要数据库 migration、执行命令、顺序，以及是否涉及不可逆数据变化。
- 是否需要新增/更新服务器 `.env`，具体变量名称和操作时机。
- 人工部署步骤、停机或兼容性要求、回滚前提；代码回退是否兼容新数据库 schema。
- 应验收的关键业务路径，以及是否包含需要通知客户的功能或操作变化。

未发现证据不能直接写“无需”。不要猜生产路径、迁移命令、环境值或回滚方式；不能保证可回滚时明确说明限制。尚未解决的关键问题可以列在讨论草稿中，但必须解决后再创建 GitHub Draft；仅为补齐必要信息提问，不增加正文或创建操作的确认步骤。

## 4. 按模板生成 Release Note

使用 [templates/release-note.md](../templates/release-note.md)，替换所有说明和占位内容，不保留与本项目无关的示例。

必须覆盖六类内容：

1. 部署内容：本次交付的功能、修复及部署方式变化。
2. Database Migration：明确需要/不需要；需要时说明内容、顺序和已确认的命令。
3. Environment：明确服务器 `.env` 是否需要新增或更新；仅记录变量名称、用途和操作时机。
4. 人工部署与回滚：明确是否需要人工操作；需要时列顺序、前提和回滚方式。不要默认“切回上一 Tag”就能撤销数据库或外部系统变更。
5. 人工验收：简短的业务验收清单，只写用户可感知的行为与预期结果；不写单元测试、接口测试、CI、lint、health check 或容器状态。
6. 客户更新：明确是否有需要通知客户的内容，必要时摘要变化和客户需执行的操作；不自动发送。

用户请求执行 release 时，直接创建 GitHub Draft，无需再次确认 Release Note 或 Draft 创建。正文、仓库、previous Tag、目标版本和 exact Commit SHA 应准备完整，创建后提供 Draft 供人工审核。仅要求“分析/起草正文”时，只返回正文，不写入 GitHub。

## 5. 直接使用 gh 创建 Draft

将生成的正文保存到仓库外的临时 Markdown 文件，供 `--notes-file` 使用；这不是业务仓库配置，也不作为额外 Release asset 上传。不创建分支。

在写入远端前再次核对：

- 工作区干净；再次 fetch 后，`origin/main` 或 `origin/master` 仍等于记录的 `TARGET_SHA`，最新正式 Release 也未改变；若有变化，重新分析并更新正文，不静默改用新提交。
- origin/GitHub 仓库未改变；获取远端 Tags 后，目标 Tag 不存在，或确实指向已核实 SHA。
- 目标 Release 未存在。已有 Draft/Published Release 时停止并报告，不覆盖、不追加重复内容；更新已有 Draft 需要开发者明确要求。
- 正文与最终分析范围一致，不包含秘密值或未解决的占位信息。

Draft 阶段不创建、推送、移动或删除正式 Tag。目标 Tag 不存在时直接创建 Draft；若本地或远端已存在，分别解引用并核对其 commit 等于 `TARGET_SHA`，不一致则停止，不能靠 `--target` 覆盖已有 Tag。

用生成的完整正文创建 Draft：

```bash
gh release create "$VERSION" \
  --repo "$REPO" \
  --draft \
  --target "$TARGET_SHA" \
  --title "$VERSION" \
  --notes-file "$NOTES_FILE"
```

`--draft` 支持尚不存在的 Tag；`--target` 必须传完整 SHA，作为候选提交。不要使用要求远端 Tag 已存在的 `--verify-tag`。正式 Tag 在后续人工 Publish 时才会为缺失的 Tag 创建；已有 Tag 时 GitHub 忽略 target，因此仍须核对 Tag。Draft 不锁定未来 Tag，人工发布前应再次核对 Tag/候选 SHA 一致。

不使用 `--generate-notes` 替换分析正文，也不用 `--fail-on-no-commits` 代替上述明确范围检查。失败立即停止，查询并报告 Draft/Tag 实际状态，不自动清理、重试写入或回滚。

成功后用 `gh release view "$VERSION" --repo "$REPO" --json tagName,isDraft,url` 确认 `isDraft=true` 及版本匹配；通过 Releases API 核对 `target_commitish` 与候选 SHA，并检查远端 Tag 仍不存在或与创建前一致。向开发者返回 Draft 链接、候选版本、比较范围、Commit 和 **AWAITING RELEASE REVIEW**。不自动 Publish。

## 与 Deploy 的衔接

Release Note 不要求 manifest 或机器可读 Deployment Contract。后续 Agent 按 [deploy 指引](deploy.md)，结合 Published Release Note、项目已有配置和服务器实际状态执行部署；信息不足时询问开发者，不猜测操作。

Release 的人工验收清单仅包含业务，部署技术检查在 Deploy 阶段按本次变更决定。Release Note 中记录的人工回滚方法并不授权自动执行高风险回滚。
