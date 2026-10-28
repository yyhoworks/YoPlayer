# 安装与升级

当前公开版本为 **[Skin 2026.10.3.122 / Home 1.0.38](https://github.com/yyhoworks/YoPlayer/releases/tag/v2026.10.3.122)**。附件与已安装到维护者 CoreELEC 的原包逐字节一致；发布说明见[118发布说明](docs/github/RELEASE118.md)，117限定测试边界见[117限定测试报告](docs/github/VALIDATION117.md)。插件 ID 仍为 `skin.yoplayer.infuse` / `plugin.video.yoplayer.home`。

## 准备

- Kodi 需满足 `xbmc.gui >= 5.17.0`、`xbmc.python >= 3.0.0`，主要验证环境为 CoreELEC。见[兼容性说明](docs/github/COMPATIBILITY.md)。
- 使用现有 Kodi 片库或已配置的 Emby 节点；Emby 插件先完成自身连接配置。
- 备份用户配置、数据库和键位，等待当前播放结束再升级。
- 从公开的 [Releases](https://github.com/yyhoworks/YoPlayer/releases) 下载两个独立插件 ZIP，核对同一 Release 的 `SHA256SUMS.txt`。

## 首次安装

1. 如尚未允许从 ZIP 安装，在“设置 → 系统 → 插件”中启用“未知来源”。各平台菜单名称可能略有差异。
2. 在“插件 → 从 ZIP 文件安装”安装 `YoPlayer-Home-1.0.38.zip`。
3. 再安装 `YoPlayer-Skin-2026.10.3.122.zip`。
4. 在“设置 → 界面 → 皮肤”选择 **YoPlayer · Infuse**，确认保留皮肤。
5. 检查首页、分库、详情和自己的媒体播放，再按需要调整首页和轨道偏好。

GitHub“Download ZIP”是源码，不能直接装为 Kodi 插件。历史 bundle 也是合集，需要先解压取出两个插件 ZIP。安装不要求扫描、清库或重置观看与续播。

## 升级与回退

升级仍先 Home 后 Skin，最低 Home 依赖由皮肤 `addon.xml` 指定。保留插件 ID 可继续沿用原设置。

先记录版本并备份，再安装新配套 ZIP。有问题时先切回可用皮肤，用本次核验备份及上一配套版本恢复；不要执行历史部署/恢复脚本。

Kodi ZIP 升级可能保留退役文件。Release 的 `*-retired-files.json` 用于核对，不可直接删除整个插件目录或用户资源。需要清理时，确认 Kodi 正常退出、已停止且备份可用，仅按精确清单和原哈希逐项处理。维护者设备部署流程留在本地工作区。

## 主题配色

进入“皮肤设置 → 界面显示 → 主题配色”。方向键移动到经典、雾白、暖沙、石墨或深海时预览，按确定保存；返回或取消恢复此前选择。“恢复经典”只复位配色，不重置其他偏好。

安装后延续原经典配色，已有背景与媒体图片设置仍保留。详细色值、主题适用场景和 VI 规则见[主题说明](docs/github/THEMES.md)。

## 返回键

[返回键模板](source/skin.yoplayer.infuse/resources/keymaps/zzzz-yoplayer-playback-back.xml)可选，安装不会自动覆盖用户键位。

需要“一次返回打开退出播放确认”时，检查系统、用户和活动 profile 映射，备份后放入适合设备的独立映射。模板含 `backspace` / `escape` / `browser_back`；有专用数字键或 CoreELEC 自定义操作时先审查冲突，不能盲目复制，也不覆盖原 XML。

已有 OSD 或模态窗口时先关闭当前层。软件输入测试不能证明实体遥控和 CEC 已通过。

## 常见问题

**安装提示依赖不满足**：检查 Kodi GUI/Python API 版本，以及 Home 是否先安装且达到最低版本。

**首页为空或缺少分库**：先确认 Kodi / Emby 原界面可看到媒体，再检查首页栏目和分库显示。隐藏分库会影响相关列表。

**播放前没有轨道选项**：来源可能没有可靠轨道资料，可开播后手动切换，参见[兼容性](docs/github/COMPATIBILITY.md)。

**GitHub 附件无法下载**：打开具体 Release 下的 Assets，下载配套插件 ZIP。若网络请求失败，稍后重试并核对 `SHA256SUMS.txt`，避免使用不完整的下载文件。
