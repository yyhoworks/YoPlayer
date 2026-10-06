# YoPlayer

面向电视和遥控操作的 Kodi 媒体界面，包含 **YoPlayer · Infuse 皮肤**和**首页数据组件**。浅色单首页集中展示分库、继续观看、最近添加和播放历史，保留 Kodi 原生播放与设置能力。

当前版本：**Skin 2026.10.3.65 / Home 1.0.25**。仓库为私有仓库，源码与附件需要相应 GitHub 权限。

[安装说明](INSTALL.md) · [下载 Releases](https://github.com/luyang1104/YoPlayer/releases) · [开发说明](docs/github/DEVELOPMENT.md) · [近期更新](docs/github/CHANGELOG.md)

## 可以做什么

- **浏览真实分库**：复用 Kodi / Emby 已有节点，调整首页栏目与分库显示，过滤隐藏分库。
- **继续观看与搜索**：使用真实续播位置、观看记录和最近添加内容，不另建观看历史。
- **电影与剧集详情**：统一详情、评分、选季选集和当前播放信息。
- **音轨与字幕**：资料可靠时支持播放前预选、播放中切换和“记住本季”；无法唯一确认时保留原选择。
- **遥控导航**：焦点、快捷菜单、设置和播放控制适配电视操作，保留 CoreELEC 原生设置。
- **列表加载优化**：评分采用单次列表的批量只读校验，完整条目一次提交，保留顺序、播放地址和续播。

轨道预选、评分和 Emby 已看同步依赖来源及接口。已验证的 Emby Next Gen 接口版本为 **11.1.27**，详见[兼容性与限制](docs/github/COMPATIBILITY.md)。

## 快速安装

1. 从 Releases 下载 `YoPlayer-Home-1.0.25.zip` 和 `YoPlayer-Skin-2026.10.3.65.zip`。
2. 在 Kodi“插件 → 从 ZIP 文件安装”中先安装 Home，再安装 Skin。
3. 在“设置 → 界面 → 皮肤”选择 **YoPlayer · Infuse**。

已有片库可继续使用。升级前备份用户配置，不需要重新扫描或清库。更多步骤和返回键说明见 [INSTALL.md](INSTALL.md)。

## 仓库结构

```text
source/
  skin.yoplayer.infuse/          皮肤 XML、脚本、字体与图片
  plugin.video.yoplayer.home/    首页、分库、搜索和评分组件
tools/                          离线检查和打包入口
docs/github/                    使用、开发、发布和版本说明
.github/                        Actions 与问题模板
```

设备备份、数据库、观看样本、部署日志、历史归档和安装 ZIP 留在本地或 Releases，不进入 Git。原版 `baseline/` / `reference/` 在维护者工作区保持原字节，全新克隆可独立检查和打包。详见[仓库与发布](docs/github/PUBLISHING.md)。

## 开发

只需 Python 3.10+，无需启动 Kodi：

```bash
python tools/check_infuse_structure.py --repository
python tools/package_project.py --repository
```

ZIP 输出至 `dist/`，不覆盖已有文件。提供同一仓库检查的 [GitHub Actions 模板](docs/github/offline-workflow.yml)，当前尚未启用。完整维护者工作区另有历史参考回归，两种范围见[开发说明](docs/github/DEVELOPMENT.md)。

## 验证范围

当前版本完成对应离线验证、Windows 安装同步和 CoreELEC 自动验证。65 版重点验证列表输出与请求耗时；近期 UI 和播放行为沿用 63/64 及此前对应证据。Windows 未进行功能或界面测试。

实体电视、硬解/HDR、实体遥控及 CEC 仍需人工确认。离线通过、远程截图和 RPC 不能替代这些接受结果。性能条件见[近期更新](docs/github/CHANGELOG.md)。

## 来源与许可

项目以 Infuse Skin 2026.10.2.12 / Home 1.0.6 为起点，基于 Minsk Infuse 和 Kodi Confluence，保留 Minsk、Jezz_X、Kodi Team 及上游贡献者署名。

皮肤沿用 GNU GPL v2，Home 声明 GPL-2.0-or-later；字体、图标等遵循独立许可。见 [LICENSE](LICENSE)、[第三方说明](THIRD_PARTY_NOTICES.md)和源码许可。本项目与 Firecore 的 Infuse 产品没有官方关联。
