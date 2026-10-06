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

初次 GitHub Release 复用核验过的 65/.25 独立 ZIP，历史 bundle 含旧说明与本地证据，留在本地。全新克隆可用 `python tools/package_project.py --repository` 在 `dist/` 构建；新 ZIP 的容器 SHA 可能不同，插件成员应逐字节一致。正式维护者交付继续使用默认完整检查/打包流程。

下载区仅保留最近三版 **63、64、65**，每版对应自己的配套 Home 和源码标签。主分支保存最新版本；不导入更早的交付历史。

## 公开访问

源码、界面预览与 Release 附件可公开访问。维护者通过 GitHub Settings 管理协作者的写入权限，推送仍需相应认证。当前没有配置 Kodi 在线插件仓库或自动更新源。
