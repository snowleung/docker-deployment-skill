# Release：分析、确认、创建 Draft

Release 由 Agent 使用 `git` / `gh` 完成，不再提供 release 脚本或自动文案生成器。Release Note 写给开发者和发布审核人员，不能仅用 commit 标题或文件列表代替代码分析。

```text
main/master 已合并的 previous Tag → HEAD
→ 阅读代码差异 → 分析 migration / env / deployment
→ 询问缺失信息 → 按模板起草 → 展示并获得开发者确认
→ 确定 Tag 对应提交 → gh 创建 Draft Release
```

只使用当前仓库和现有 main/master，不新建其他分支。不自动 commit、不自动 Publish、不部署、不执行 migration，也不发送客户通知。

## 1. 确定仓库、提交和 previous Tag

检查 Git、GitHub CLI 和认证，确认 origin 对应的 GitHub 仓库。所有 `gh` 调用显式指定同一个 `--repo`，不要依赖可能指向其他项目的 `GH_REPO` 或 CLI 默认仓库。

只读检查示例（`OWNER/REPO` 要替换为已核实的实际仓库）：

```bash
git status --short --branch
git remote -v
git branch --show-current
git rev-parse HEAD
gh auth status
git fetch origin --tags
git tag --merged HEAD
git log --oneline --decorate --graph -30
gh release list --repo OWNER/REPO --limit 100
```

- 当前 HEAD 应位于现有 main 或 master。若不是，先说明实际分支并询问开发者应分析的提交；不要自行新建、切换或合并分支。
- 查看本地 main/master 与 origin 对应分支的关系。落后、分叉或包含尚未合并的提交时，明确指出并确认范围，不能用远端分支替换用户要求的 HEAD。
- 以已合并到当前主分支、且是 HEAD 祖先的 Tag 为候选；结合 Git 提交图和 `gh release view <tag> --repo OWNER/REPO` 了解上一版发布背景。超过一页则继续查找，不把未出现在列表首页误判为不存在。
- 默认使用最近可达的上一发布 Tag。不要直接取全仓库最大版本号、最新创建的 Release 或未合并分支上的 Tag。存在多个无法确定的候选时，询问开发者。
- 排除本次目标 Tag。可用 `git describe --tags --abbrev=0 --exclude='<目标版本>' HEAD` 辅助查找，但仍需确认该 Tag 的用途。
- 首次发布没有 previous Tag 时，明确说明这是首次发布，阅读当前版本涉及的应用和部署文件，不虚构历史差异。
- 记录目标版本、previous Tag、previous Commit SHA、当前完整 HEAD SHA。已有目标 Tag 必须解引用到同一个 SHA；不一致则停止，不覆盖或移动 Tag。

## 2. 比较 previous Tag → HEAD，并阅读相关代码

先看范围，再读具体变更及相关调用方：

```bash
git log --oneline <previous-tag>..HEAD
git diff --stat <previous-tag> HEAD
git diff --name-status <previous-tag> HEAD
git diff <previous-tag> HEAD -- <相关文件>
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

未发现证据不能直接写“无需”。不要猜生产路径、迁移命令、环境值或回滚方式；不能保证可回滚时明确说明限制。尚未解决的关键问题可以列在讨论草稿中，但必须解决后再请求最终确认、创建 GitHub Draft。

## 4. 按模板生成并展示 Release Note

使用 [templates/release-note.md](../templates/release-note.md)，替换所有说明和占位内容，不保留与本项目无关的示例。

必须覆盖六类内容：

1. 部署内容：本次交付的功能、修复及部署方式变化。
2. Database Migration：明确需要/不需要；需要时说明内容、顺序和已确认的命令。
3. Environment：明确服务器 `.env` 是否需要新增或更新；仅记录变量名称、用途和操作时机。
4. 人工部署与回滚：明确是否需要人工操作；需要时列顺序、前提和回滚方式。不要默认“切回上一 Tag”就能撤销数据库或外部系统变更。
5. 人工验收：简短的业务验收清单，只写用户可感知的行为与预期结果；不写单元测试、接口测试、CI、lint、health check 或容器状态。
6. 客户更新：明确是否有需要通知客户的内容，必要时摘要变化和客户需执行的操作；不自动发送。

展示**完整 Release Note**，同时说明仓库、previous Tag、目标版本和 exact Commit SHA，取得开发者明确确认。确认范围包含该版本的 Tag 创建/推送及 Draft 创建；此前明确要求执行这些动作的授权仍然有效，但新生成的 Note 内容仍需展示并确认。仅要求“分析/起草”不代表允许写入 GitHub。

用户要求改内容后，展示最终版本再确认。不要把没有回复视为同意。

## 5. 确认后使用 gh 创建 Draft

将确认过的正文保存到仓库外的临时 Markdown 文件，供 `--notes-file` 使用；这不是业务仓库配置，也不作为额外 Release asset 上传。不创建分支。

在写入远端前再次核对：

- 工作区干净，HEAD 仍等于开发者确认的 SHA；若有变化，重新比较和确认。
- origin/GitHub 仓库未改变；获取远端 Tags 后，目标 Tag 不存在，或确实指向已确认 SHA。
- 目标 Release 未存在。已有 Draft/Published Release 时停止并报告，不覆盖、不追加重复内容；更新已有 Draft 需要开发者明确要求。
- 正文仍是确认过的版本，不包含秘密值或未解决的占位信息。

若目标 Tag 尚不存在，创建 annotated Tag 并仅推送该 Tag（示例中的变量需先设置为已确认值）：

```bash
git tag -a "$VERSION" "$COMMIT_SHA" -m "Release $VERSION"
git push origin "refs/tags/$VERSION"
```

若 Tag 已存在，先用 `git rev-parse "refs/tags/$VERSION^{commit}"` 核对 exact SHA；远端也必须存在且指向同一提交。禁止强推、移动或删除已有 Tag，不让 GitHub 自动从 moving branch 创建 Tag。

用经过人工确认的正文创建 Draft：

```bash
gh release create "$VERSION" \
  --repo "$REPO" \
  --draft \
  --verify-tag \
  --title "$VERSION" \
  --notes-file "$NOTES_FILE"
```

不使用 `--generate-notes` 替换确认过的正文。失败立即停止，说明 Tag 是否已创建/推送及 Draft 是否已存在；不自动清理、重试写入或回滚。

成功后用 `gh release view "$VERSION" --repo "$REPO" --json tagName,isDraft,url` 检查状态，向开发者返回 Draft 链接、Tag、Commit 和 **AWAITING RELEASE REVIEW**。不自动 Publish。

## 与 Deploy 的衔接

Release Note 不要求 manifest 或机器可读 Deployment Contract。后续 Agent 按 [deploy 指引](deploy.md)，结合 Published Release Note、项目已有配置和服务器实际状态执行部署；信息不足时询问开发者，不猜测操作。

Release 的人工验收清单仅包含业务，部署技术检查在 Deploy 阶段按本次变更决定。Release Note 中记录的人工回滚方法并不授权自动执行高风险回滚。
