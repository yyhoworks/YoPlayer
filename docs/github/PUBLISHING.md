# GitHub 仓库与发布

目标为 `https://github.com/yyhoworks/YoPlayer`，**Public**，默认分支 `main`。

## 保存范围

Git 保存两个运行插件的完整成员、根目录说明与许可、`docs/github/`、检查/打包入口及 `.github/`。源码约 81 MiB，最大成员约 36 MiB，没有超过 GitHub 100 MiB 单文件限制，目前不依赖 Git LFS。

允许列表式 `.gitignore` 将原版档案、备份、归档、旧文档、设备工具、本机 `AGENTS.md` / `RESUME.md` / 交接、`project.json`、安装 ZIP 和 `dist/` 留在本地。忽略不删除资料。初次提交保存当前源码快照，不导入整个历史工作区；观看数据库、用户配置和凭据始终留在本地。

实机界面预览位于 `docs/github/previews/`，由 [PREVIEW.md](PREVIEW.md) 记录采集版本。公开图片只保留界面内容，重新编码去除原始图片元数据；设备地址、日志与原始验收记录留在本地。

## 日常推送

```bash
git status --short
python tools/check_infuse_structure.py --repository
git add README.md INSTALL.md CONTRIBUTING.md THIRD_PARTY_NOTICES.md docs/github .github source tools
git diff --cached --stat
git commit -m "Describe the change"
git push
```

不要用 `git add -f` 强行加入被忽略的资料。认证使用 GitHub 凭据管理，不在 URL、命令或项目文件里放令牌。

## Releases

正式发布前完成相关离线和实际环境验证；运行文件变化须升版，禁止覆盖已交付同版本档案。使用与源码对应的标签，如 `v2026.10.3.65`。

推荐附件：两个配套插件 ZIP、`SHA256SUMS.txt`，以及适用的精确 `*-retired-files.json`。说明包含安装顺序、变化、验证范围和限制。

初次 GitHub Release 复用核验过的 65/.25 独立 ZIP，历史 bundle 含旧说明与本地证据，留在本地。90/.28 使用 `python tools/package_project.py --repository` 在 `dist/` 构建两个独立插件包，逐成员匹配当前源码。全新克隆亦可使用该入口；新 ZIP 的容器 SHA 可能不同，插件成员应逐字节一致。历史完整检查/打包范围见[开发说明](DEVELOPMENT.md)。

2026-10-09 新增 **90 / Home 1.0.28** 发布与对应源码标签，主分支保存本次源码及说明；63、64、65 历史 Release 保留供回退。本次未删除既有附件或标签。后续保留策略另行决定。

2026-10-10 同步 **99 / Home 1.0.30** 与91–99累计更新。源码标签 `v2026.10.3.99`，复用CE已核验的独立包；新增从公开90升级至99的21文件精确退役清单。63、64、65、90历史Release及附件保持。当前有限实测通过，真实Emby/部分边界和最终验收仍待补验；用户明确要求发布本版，未声明全项验收通过。

2026-10-10 同步 **101 / Home 1.0.32** 与100–101累计更新，标签`v2026.10.3.101`。复用CE已核验包；相对99无新增/退役，附件退役清单保留历史参考。63/64/65/90/99发布保持。本次13项限定离线检查与七个CE点击详情/返回场景通过，实体TV/遥控/CEC和完整验收仍待补验。

2026-10-10 正式发布 **106 / Home 1.0.34** 与102–106累计更新，源码标签 `v2026.10.3.106` 指向提交 `f29f9302c43924bdd6690d4b9900a8e77e374f6a`；GitHub Release 已公开并列为最新版本。附件为已核验的CE候选包和 `SHA256SUMS.txt`，未重打包或覆盖历史附件。当前CE已安装106 / Home34；限定离线检查22项通过，安装树1425个成员与包匹配。短等待抑制路径有CE窗口计时证据，长忙碌提示实际出现、电视观感、实体遥控/CEC及完整验收仍待补验；凡人修仙传详情探测未计通过。Release正文如实列出验证范围和限制。63、64、65、90、99、101历史Release及附件保持。

2026-10-11 同步 **109 / Home 1.0.35** 与102–109累计更新（含107安全收口与108勘误），标签`v2026.10.3.109`。复用CE已核验包；相对101累计退役7个运行成员，附件退役清单仅作记录。63/64/65/90/99/101发布保持。

2026-10-11 同步 **109 / Home 1.0.35** 与102–109累计更新（含107安全收口与108勘误），标签`v2026.10.3.109`。复用CE已核验包；相对101累计退役7个运行成员，附件退役清单仅作记录。63/64/65/90/99/101发布保持。

## 2026-10-15：117源码同步与Release

基于115提交同步Skin117 / Home1.0.37源码、可独立运行的44项离线回归及[脱敏限定测试摘要](VALIDATION117.md)，不带入116工作线。117已在维护者CE完成安装和限定测试，但仍有两项P2未通过，不宣称完整验收。

源码同步提交d64a6d2最初未创建Release；用户指出Latest仍为115后，补齐[117 Release](https://github.com/yyhoworks/YoPlayer/releases/tag/v2026.10.3.117)及标签v2026.10.3.117，设为Latest。附件复用已核验并安装的Skin117、Home37及原SHA256SUMS.txt；先在草稿中校验三个附件的大小与GitHub SHA256，再公开发布。发布说明明确两项P2未通过及实体验收限制。117相对115无文件退役，不附自动清理清单；历史Release、标签和附件保留。

设备地址、原始日志、截图、备份、配置、观看记录及本地部署入口不进入Git。此次补发不改变117运行字节，不连接设备。

## 2026-10-27：118源码同步、CE停态部署与Release

合入 PR #1 页面浏览速度与 UI 流畅性优化（第一档 11 项 + 第二档 2 项）、5 项代码评审修正及 3 项皮肤遗留修正，升级为 **Skin 2026.10.3.118 / Home 1.0.38**。通过仓库完整性检查与 43 项离线回归，在维护者 CoreELEC 完成停态备份、78 项差量安装与启动读回（8 个启用首页栏目均正常加载），并发布 [118 Release](https://github.com/yyhoworks/YoPlayer/releases/tag/v2026.10.3.118)（标签 `v2026.10.3.118`，设为 Latest）。

## 2026-10-27：119死代码清理与Release

合入 PR #2/#3/#4 皮肤引用门禁与死代码清理，升级为 **Skin 2026.10.3.119 / Home 1.0.38**（Home 未变更）。本版不含界面行为改动，只删除零引用定义并把 CI 门禁收紧为失败。

- PR #2 立门禁 `tools/check_skin_refs.py` 与 `skin-gate` workflow；评审发现带参 `$VAR` 与空目录两处盲区并修复（变量引用覆盖 1645→2592）。
- PR #3 删除零引用 include `AudioCodecFlag` / `VideoCodecFlag`，CI 改用 `--strict`。
- PR #4 删除第一批死 include 共 70 个名字（含级联），`dead_includes` 119→75。
- 因运行时文件变更，118 已交付包不再可打包，故升版本至 119；`dead_variables` 基线同步按修正后解析器重算 312→192（未删除任何变量）。

验证：`check_skin_refs.py --strict` 与 `repository_checks.py` 均退出码 0；144 个 1080p XML 全部可解析；在维护者 CoreELEC 完成停态备份与 9 项差量安装，启动后 `skin loaded...`、首页正常渲染（继续观看/媒体分库/每日精选），无播放中断。

发布 [119 Release](https://github.com/yyhoworks/YoPlayer/releases/tag/v2026.10.3.119)（标签 `v2026.10.3.119`，设为 Latest），附件为 Skin 119、Home 1.0.38 与 `SHA256SUMS.txt`。118 及更早 Release、标签和附件保持。

**未覆盖**：Kodi 实机播放/扫描回归、物理电视、实体遥控与 CEC 验收；本版未宣称完整验收通过。

## 2026-10-28：120死变量清理第二批、CE部署与Release

合入 PR #5（`6bd6ee6`），升级为 **Skin 2026.10.3.120 / Home 1.0.38**（Home 未变更）。本版仅删除 143 个零引用变量定义、把基线死变量从 192 收到 53，无界面行为改动。

- 评审：独立复算死变量 192→53 与基线逐项一致；未定义引用 0；4 个级联变量的唯一引用都在被删变量内。评审发现的唯一问题（`<news>` 仍宣传被删变量）已在合入前修正（`741d1b4`）。
- 验证：`check_skin_refs.py --strict` 与 `repository_checks.py` 退出码 0；144 个 XML 解析通过。
- 打包：`dist/deadcode120-20261028/`，皮肤 1379 成员 `3e78703c…e278`、Home 18 成员 `8f6eb769…9e94`。
- 部署：维护者 CoreELEC 停态备份 `3b33506f…c3f1`（72,907,627 字节）后差量安装 5 个皮肤文件；启动后 `skin loaded...`、ERROR 0，主页/设置/视频窗口冒烟正常，无播放。报告 `docs/acceptance/deadcode120-20261028/REPORT.md`。

发布 [120 Release](https://github.com/yyhoworks/YoPlayer/releases/tag/v2026.10.3.120)（标签 `v2026.10.3.120`，设为 Latest），附件为 Skin 120、Home 1.0.38 与 `SHA256SUMS.txt`。119 及更早 Release、标签和附件保持。

**未覆盖**：详情页像素级确认、实体电视、实体遥控与 CEC 验收；本版未宣称完整验收通过。

## 公开访问

源码、界面预览与 Release 附件可公开访问。维护者通过 GitHub Settings 管理协作者的写入权限，推送仍需相应认证。当前没有配置 Kodi 在线插件仓库或自动更新源。
