# YoPlayer 2026.10.3.118 / Home 1.0.38

基于 117 的页面浏览速度与 UI 流畅性优化版，合入 PR #1（第一档 11 项 + 第二档 2 项）、代码评审修正与 3 项皮肤遗留修正。附件与已核验并部署到 CoreELEC 的原包逐字节一致。

## 主要更新

### 1. 首页与分库性能（Home 1.0.38）
- **隐藏栏目零后台开销**：`Home.xml` 8 个栏目容器按皮肤设置开关条件渲染 `<content>`，关闭的栏目不再在后台触发插件进程。
- **跨进程临时文件缓存**：为分库节点（30s）、可见分库归属签名与集合（60s）、首页单路由媒体结果（20s）及 Emby 数据库路径探测（300s）引入基于 `tempfile` 的原子 JSON 缓存，消除首页多栏目并发启动时的重复目录遍历与 SQLite 读取。
- **懒加载归属与空态回写保障**：继续观看与播放历史路由仅在存在待补全排队剧集时才构建完整分库归属集合，确保命中轻量签名路径；正常非空路由跳过冗余 `Window(10000)` 属性写入，空库或全隐藏时仍写回 `Count.<route>=0` 与 `Loaded.<route>=true`，确保首页空态提示正常切换。

### 2. 详情页、列表与播放面板（Skin 2026.10.3.118）
- **异步背景纹理加载**：海报墙、横幅、缩略图等视图的背景扇出图启用 `<background>true</background>`，降低快速滚动时的主线程解码阻塞。
- **详情页启动瘦身与身份锁定**：移除已无消费方的 `genre.py`；将 `castphoto.py` 与 `embypath.py` 延后 1s 启动，并在 `DialogVideoInfo.xml` 打开时锁定 `YoPlayer.Detail.Identity`（`DBType:DBID`），防止延迟启动期间焦点漂移读错条目。
- **OSD 面板与播放时降载**：合并 `Custom_1140_OSD_Next.xml` 重复 `<onload>`；`player_streams.refresh()` 直接刷新快照供 `infuse_player.py` 复用，切换音轨/字幕时强制实时查询并清理旧快照；视频全屏播放时暂停首页与详情页的 4K 轮播图定时器。
- **纹理瘦身与遗留修复**：无损/高质量重编码 43 张高频 4K 纹理（缩减约 31.3 MB）并降采样 2 张超清 Logo PNG；补齐 `Variables.xml` 中缺失的 `ColorHighlight` 与 `WeatherBackgroundTypeVar` 变量定义；修正 `Custom_1142_OSD_Cast.xml` 中 `<font>FONT11</font>` 大小写。

## 验证范围与已知限制

- **离线检查**：`python tools/repository_checks.py`（结构、语法、五主题哈希、打包校验）与 43 项专项回归全部通过。
- **CoreELEC 停态部署**：已在维护者 CoreELEC 设备完成停态备份、78 个变更成员原子安装及启动验证（`skin.yoplayer.infuse` `2026.10.3.118` + `plugin.video.yoplayer.home` `1.0.38`，8 个启用首页栏目正常加载，用户配置无改动）。
- **已知限制**：117 记录的确认框初始焦点与无播放时预告片错误提示两项 P2 问题及实体验收边界见 [117限定测试报告](https://github.com/yyhoworks/YoPlayer/blob/v2026.10.3.118/docs/github/VALIDATION117.md)。

## 下载与安装

1. 下载下方 Assets 中的两个插件 ZIP 及 `SHA256SUMS.txt`，核对 SHA256。
2. 先安装 `YoPlayer-Home-1.0.38.zip`，再安装 `YoPlayer-Skin-2026.10.3.118.zip`。
3. 已有用户保留原设置和片库，无需重新扫描、清库或重置观看记录。插件 ID 不变，118 相对 117 无退役文件。

GitHub 自动生成的 Source code ZIP 是源码快照，不能直接作为 Kodi 插件安装。

| 附件 | SHA256 |
| --- | --- |
| YoPlayer-Skin-2026.10.3.118.zip | `1b1795d516fa86955094766d2f4b056180d019cc40e37c9bb63a1da5b804392b` |
| YoPlayer-Home-1.0.38.zip | `8f6eb769eb0b2d839ef0da01fa4f97ccfe1d54fe1ee766b560af84449cdb9e94` |
