# Window(Home) 契约 · YoPlayer

> 基准：`origin/main` 提交 `293f4ab`，Skin `2026.10.3.121` / Home 插件 `1.0.38`。
> 本页所有属性都挂在 `xbmcgui.Window(10000)`（即 `Window(Home)`）上；行号均以该提交为准。
> 121 相对 120 只删除了零引用死定义（Includes.xml / IncludesHomeMenuItems.xml / Includes_Paths.xml / Variables.xml），未触及下方引用的 `Home.xml` 与各 `.py` 脚本，故行号不变。
> 写入方有三处：首页插件 `plugin.video.yoplayer.home`、皮肤脚本 `skin.yoplayer.infuse/scripts/*.py`、
> 皮肤 XML（仅 `DialogButtonMenu.xml` 的 `PowerHelp`）。其余属性皮肤只读不写。

## 1. 刷新与导航：Revision / DataChanged / 焦点恢复

| 属性 | 写方 | 读方 | 值域与含义 |
|---|---|---|---|
| `YoPlayer.Infuse.Revision` | 插件 `resources/lib/actions.py:67`（`refresh()`） | 皮肤 `1080p/Home.xml` 全部 8 个行容器 URL（`:191–519`）及探针容器（`:565–640`） | `time.time_ns()` 字符串。每次 `refresh()` 都 bump；容器 URL 带上它，值一变容器即重载。**插件不比对该参数**，只在行完成时把它原样写回 `Loaded.<route>` |
| `YoPlayer.Infuse.DataChanged` | 皮肤脚本 `scripts/infuse.py:96`（库通知）、`:201`（favourites 文件 mtime 变化） | 插件各缓存的 epoch：`provider.py:311,374`、`genre_directory.py:83,127`；皮肤脚本 `infuse.py:225` | `time.monotonic()` 字符串。只做**相等比对**，不表示时刻。触发源：`VideoLibrary.OnScanFinished / OnUpdate / OnRemove`、`Player.OnStop`、`Favourites.OnUpdated`，以及 favourites 文件 3 秒轮询（`infuse.py:196–201`） |
| `YoPlayer.Infuse.RefreshPending` | 插件 `actions.py:68`（`refresh()` 时写 `time.monotonic()`） | 皮肤脚本 `infuse.py:204,224` | 刷新待恢复焦点标记。皮肤循环在同时满足以下条件时消费它：距写入 > 0.5 秒、`Loaded.libraries == Revision`、无模态对话框；随后按 `RestoreLibraryId/Position` 恢复 302 行焦点并清除它 |
| `YoPlayer.Infuse.RestoreLibraryId` / `RestoreLibraryPosition` | 插件 `actions.py:65–66`（从 `LibraryId/LibraryPosition` 复制） | 皮肤脚本 `infuse.py:216–218` | 刷新前 302 行（分库行）选中的分库 id 与下标 |
| `YoPlayer.Infuse.LibraryId` / `LibraryPosition` | 皮肤脚本 `infuse.py:172–173`（Home 活动且 302 行有焦点时，每隔一轮记录） | 插件 `actions.py:65–66` | 当前分库行选中项的 `Infuse.LibraryId` 与 `CurrentItem - 1` |
| `YoPlayer.Infuse.FocusRow` | 皮肤脚本 `infuse.py:170` | 皮肤脚本 `infuse.py:44`（`focus_content`） | Home 各行容器 id（301/302/303/304/305/307/308/309，见 `infuse.py:15–17`） |
| `YoPlayer.Infuse.RestoreAt` | 皮肤脚本 `infuse.py:111`（runtime 启动时） | 皮肤脚本 `infuse.py:176–194` | 启动后首次焦点恢复的计时起点；满足“> 0.5 秒且已加载（或 > 4 秒）且无模态”时执行一次焦点恢复并清除。这里的“已加载”是 `Count.libraries`/`Error.libraries` 与 `Count.continue`/`Error.continue` 已存在（`infuse.py:178–179`），与 `RefreshPending` 用的 `Loaded.libraries == Revision` 是两套判定 |
| `YoPlayer.Infuse.Heartbeat` / `Owner` | 皮肤脚本 `infuse.py:158,119` | 皮肤脚本 `infuse.py:113–116,139,253–256` | runtime 循环的单例保护：启动时若上次心跳在 2 秒内则直接退出；退出皮肤时清除 `Owner` 与 `Heartbeat`。循环周期 0.25 秒（`infuse.py:240`） |
| `YoPlayer.Infuse.BrowseShow` | 皮肤脚本 `infuse.py:296`（`browse-seasons` 动作） | 未在代码中找到皮肤侧读取 | 剧集 id（整数转字符串），供打开剧集季列表时使用 |

**刷新触发链（窗口打开 / 数据变化 / 手动刷新）：**

1. 窗口打开：`Home.xml:643` 的 `<onload>` 跑 `infuse.py,startup` → `runtime()` 循环（`infuse.py:99`）。
   循环每 3 秒调用 `infuse_device.publish(only_changed=True)`（`infuse.py:154–156`）。
2. 数据变化：库通知或 favourites 变化写 `DataChanged` → 循环在 `DataChanged` 存在超过 0.8 秒、
   且距上次刷新超过 2 秒时调 `actions.refresh()`（`infuse.py:225–239`），随后清除 `DataChanged`。
3. `actions.refresh(routes=None)`（`actions.py:27–68`）：按路由清除缓存键（**daily 除外**，见第 3 节），
   复制 `RestoreLibrary*`，bump `Revision`，写 `RefreshPending`。带 `routes` 参数时只清指定路由的键，
   例如进度类变化只刷 `('continue', 'history')`（`actions.py` 文档字符串）。
4. 容器重载：URL 里的 `revision=` 变了 → 插件 `directory()` 重跑 → 行完成时写 `Count.<route>` 与
   `Loaded.<route> = revision`（`provider.py:726–729`）→ 皮肤循环凭 `Loaded.libraries == Revision`
   确认新一轮已加载，再恢复焦点并清除 `RefreshPending`。

## 2. 行状态：Count / Loaded / Error（按路由）

插件 `directory()`（`provider.py:527`）的每个路由完成时写状态；失败时写 `Error.<route>` 并清掉旧错误
（`provider.py:569,731`）。皮肤用 `Variables.xml:3–7` 的 `YoPlayerHomeLibraryStatus` 汇总 libraries 行：
有 `Error.libraries` 显示 32028；`Count.libraries` 非空且 `Loaded.libraries == Revision` 显示 32027；否则 32026。

| 路由 | 写 `Count.` | 写 `Loaded.` | 写 `Error.` | 备注 |
|---|---|---|---|---|
| `continue`、`history`、`daily`、`recent-movies`、`recent-episodes`、`unwatched`、`libraries`、`detail-seasons`、`player-streams`、`search` | `provider.py:727` | `provider.py:728` | `provider.py:731`（失败文案固定为“内容暂时无法加载，请检查来源或重试”） | `daily` 行容器 limit 12，其余 recent/unwatched/continue 行 limit 25（`Home.xml`） |
| `genres`、`tvshow-genres`（及 `-all` 变体） | `genre_directory.py:236` | 不写 | `provider.py:544`（失败文案“分类资料暂不可用”） | 分类行不参与 `Loaded == Revision` 判定 |
| `genre-items` | 不写 | 不写 | — | 只出目录项 |
| `native-browse`、`tvshow-details` | 不写 | 不写 | — | 走原生浏览 / 剧集打开路径 |

**probe=1（探针容器）**：`Home.xml:565–640` 的 9301–9309 计数容器在 URL 后加 `probe=1`，
插件 `default.py:10` 解析为布尔值。探针语义（`provider.py:599,615,666,726`、`genre_directory.py:219,235`）：
只取首行（`rows[:1]`；分类行只取首组），且**行数 > 0 时不写 `Count./Loaded.`**（避免探针污染行状态）；
行数为 0 时仍写 `Count.=0`，使空行被记录。皮肤脚本 `infuse.py:29–41` 用
`Container(930x).NumItems` 判断哪些行有内容、决定焦点顺序。

Home 行容器本身不读 `Count./Loaded.`，只靠 URL 重载；皮肤侧的直接读取只有两处：
`YoPlayerHomeLibraryStatus` 变量读 libraries 一组（`Variables.xml:3–7`），以及 runtime 焦点恢复门槛读
`Count./Error.libraries` 与 `Count./Error.continue`（`infuse.py:178–179`，见第 1 节）。

## 3. 缓存键与 15 秒规则、cacheToDisc

所有缓存都存在 Window(Home) 属性里，值是 JSON 字符串；**没有落盘缓存**。
插件所有 `endOfDirectory` 调用都传 `cacheToDisc=False`（`provider.py:537,545,554,729,734`、
`genre_directory.py:237`、`browse_directory.py:189`），理由写在 `browse_directory.py:184–188`：
Kodi 的磁盘缓存没有失效钩子，会比 15 秒窗口活得更久，过期后仍可能被命中。

| 缓存键 | 写方 | 命中条件 |
|---|---|---|
| `Cache.continue`、`Cache.history` | `provider.py:189`（`cached_media`） | 15 秒（`time.time()`）内且 membership 签名相等 |
| `Cache.daily`、`Cache.recent-movies`、`Cache.recent-episodes`、`Cache.unwatched` | `provider.py:309`（`cached_home_media`） | 15 秒内（**daily 例外：按日历日 `%Y%m%d`，见下**）且签名相等且 epoch（`[DataChanged]`）相等；写入前复核 epoch 未变 |
| `Cache.libraries` | `provider.py:372`（`cached_libraries`） | 同上 |
| `Cache.GenreSummary.movie` / `.tvshow` | `genre_directory.py:96`（`cached_summary`） | 15 秒（`time.monotonic()`）内且 epoch 相等；载荷超 2 MiB 时不存 |
| `Cache.GenreSnapshot.movie` / `.tvshow` | `genre_directory.py:150,170`（`snapshot`） | 15 秒内且 epoch、签名、分类配置哈希、`rows_fp`（id/类型/fanart/landscape 指纹）全相等 |
| `Cache.Browse.<sha256(完整筛选条件)>` | `browse_directory.py:137` | 15 秒（`time.monotonic()`）内；超 2 MiB 不存；ListItem 每次重建，只省 RPC 与过滤 |
| `Cache.Ratings.<指纹>` | `emby_rating.py:178` | 15 秒内且返回条数与请求条数相等 |
| `GenreArt.<sha256(类型\0分组名)>` / `GenreArt.Keys.<kind>` | `genre_directory.py:36`（`artwork` 选图）、`:52`（`purge_art_cache` 登记） | 无时间窗：命中要求 `signature`（membership 签名 + 候选行 id/字段/值）相等，且缓存的图仍在当前候选集合里；`Keys` 表记录现存键，用于淘汰已消失的分组 |
| `Membership.<分库 id>` | `provider.py:92` | 15 秒内且节点文本指纹相等（见第 4 节） |
| `Search.Cache` | `provider.py:702` | 同查询 + 15 秒内 + 签名相等（`provider.py:689`） |
| `PlayerStreams.Snapshot` | `player_streams.py:63`、`infuse_player.py:126` | 15 秒（`SNAPSHOT_TTL = 15`，`player_streams.py:10`）内且 playerid、媒体身份、`StreamRevision` 全相等 |

要点：

- **epoch 里只有 `DataChanged`，没有 `Revision`**（`provider.py:297–305` 的 A-H3 注释）。
  `refresh()` 之所以能让行重刷，是因为它显式清掉了路由缓存键 + bump `Revision` 让容器重载；
  被清掉键的行重算，未被清的行即使重请求也会命中缓存。
- **daily 特殊**：`refresh()` 从不清除 `Cache.daily`（`actions.py:36–44` 的注释、`:60` 的 `route != 'daily'`）；daily 的“新鲜”按日历日判定，
  同一天内只在 membership 签名或 `DataChanged` 变化时重抽（12 部为按当日日期种子的随机抽样，
  `provider.py:316–331,355`）。想强制重抽须显式传 `routes=('daily',)`。
- **搜索**：`Search.Status`（`provider.py:705,716`）是状态文案，皮肤 `MyVideoNav.xml:224` 显示它；
  空查询时文案固定为“请输入关键词搜索电影或剧集。”
- **非缓存的瞬时属性**：`YoPlayer.Infuse.MediaReadOwner`（`infuse_network_tools.py:22`，置位 `:156`、
  清除 `:161`）是“原生文件读取测速”进行中的持有者令牌，挂在 Window(Home) 上：置位期间再次发起测速
  会被拒绝（`:147`），播放或状态变化则取消（`:152`）；没有 TTL，由测速线程结束时清除。

## 4. membership 签名：不是付费会员

**代码里没有会员等级、有效期、订阅状态这类字段。** 这里的 membership 指“媒体属于哪个分库”的
可见性判定，数据源是 Kodi 原生媒体节点与 Emby 同步库，不是账号体系。

- 判定逻辑：`visibility.py:54–72`（`Membership` 类）。仅当存在被隐藏的分库时才逐项判定；
  一条媒体若属于某个可见分库即判定可见（可见胜出）；归属不明时默认可见，绝不因未知来源抹掉媒体。
- 两种归属来源：目录型分库按路径前缀判定（`visibility.py:27–30` 的 `inside`）；原生节点型分库
  按节点规则（`visibility.py:33–51` 的 `native_filter`：仅支持 `node`/`smartplaylist` 的
  tag/path/title/year/genre/set 规则）结合 Emby 同步库判定（`emby_membership.py:10–62` 的
  `synced_members`：只认“整库节点”，即 `library://video/emby_<kind>_<…>/all.xml` 且单条 `tag is` 规则，
  再读 `emby_*.db` 的 `LibrarySynced` / `EmbyLibraryMapping` 表，取与本地库现存记录的交集）。
- 签名：`provider.py:69–116` 的 `display_membership()` 生成 `membership.signature` =
  `sha256([preferences, 全部（含隐藏）分库列表, 各库节点文本指纹])`；`membership_signature()`
  （`provider.py:119` 起）是只算签名不展开成员 id 集的快路径，两者按注释要求严格镜像，
  不一致时只会导致缓存 miss，不会误命中。插件与皮肤两侧对齐的方式就是**比对这个签名字符串**，
  皮肤 XML 里不出现 membership 字段。
- 偏好来源：分库选择与隐藏状态存在插件配置 `libraries.json`（`provider.py:30–36` 的
  `preferences_path()` / `preferences()`），`visibility.py:8–11` 的 `hidden()` 以它为准。

## 5. 播放记忆与轨道：Memory* / StreamRevision

写方是皮肤脚本 `infuse_player.py` 的 `refresh()`（由 `Custom_1144_OSD_subtitles.xml:631` 的
`<onload>` 及同类入口调用），读方是 1144/1145 两个 OSD 窗口与 `Variables.xml`。

| 属性 | 写方 | 值域与含义 |
|---|---|---|
| `MemoryFile` / `MemoryDBID` | `infuse_player.py:100` | 当前播放器的 `Player.Filenameandpath` 与 `VideoPlayer.DBID`；与播放器标签不一致时整组被清空（`infuse_player.py:80,104` 的 `clear()`；`:97` 只清 `MemoryReady`），换片/停播绝不借用上一部片的上下文 |
| `MemoryKind` | `infuse_player.py:100` | `season`（剧集，`live()` 的 key 以 `show:` 开头）或 `folder`（目录）；来源 `infuse_stream_memory.py:21–42` 的 `live()` |
| `MemoryScope` | `infuse_player.py:100` | 记忆适用范围文案：剧集为“本剧第 N 季”/“本剧特别篇”，目录为“同一剧集目录”；皮肤 `Variables.xml:2468` 用它拼“为……后续播放沿用所选轨道” |
| `MemoryReady` | `infuse_player.py:102` | 固定值 `true`，表示上述四项已发布；识别失败时整组清空（含 `Ready`） |
| `StreamSignature` / `StreamRevision` | `infuse_player.py:122–123` | 记忆属性 + 媒体 token + 当前轨道清单（序号/语言/名称/编码/声道、当前轨、字幕开关）的 sha256；**只有签名变化时才 bump `StreamRevision`**（`time.time_ns()`），读不到状态时返回 None、按“已变化”处理（`infuse_player.py:29–47` 的注释） |
| `PlayerStreams.Snapshot` | `infuse_player.py:126`、`player_streams.py:63` | 见第 3 节；1144/1145 容器 URL 带 `revision=$INFO[…StreamRevision]`（如 `Custom_1144_OSD_subtitles.xml:244,351`），签名变化 → 容器重载 → 插件 `player-streams` 路由重算轨道列表（`player_streams.py` 的 `stream_entries`，每项带 `YoPlayer.StreamKey` 用于选轨校验） |
| `NextEpisodeAvailable` | `infuse_player.py:157,167` | `true`，仅当剧集内容、DBID 为数字、下一集存在且仍在 videoosd 时才写；进入时先清除 |
| `CompactConfirm` | `infuse_player.py:176,181`（`confirm_stop`）、`infuse_playback_back.py:13`（`confirm_exit`） | 对话框存续期间为 `true`，结束即清除；皮肤 `DialogConfirm.xml:23,31,40,130` 据此切换紧凑布局 |
| `PlaybackBackBusy` | `infuse_playback_back.py:12` | 全屏播放时 Back 键确认流程的重入保护标记 |

## 6. 设备能力：Capability.*

写方：`scripts/infuse_device.py:41–52` 的 `publish()`；皮肤脚本 `infuse.py:154–156` 在 runtime 循环里
每 3 秒调一次 `publish(only_changed=True)`（快照不变则跳过）。读方：`DialogButtonMenu.xml`（10 处）、
`SkinSettings.xml`（4 处）、`Variables.xml`（2 处）。值一律为小写 `true` / `false` 字符串。

| 属性 | 判定来源（`infuse_device.py:17–39`） |
|---|---|
| `Capability.quit` | 恒为 `true` |
| `Capability.powerdown` | `System.CanPowerDown` |
| `Capability.coreelec` | Linux 且 CoreELEC 设置插件已启用（`infuse_device.py:30` 的 `bool(ce and settings)`）。`/etc/os-release` 的 `id=coreelec` 只在设置插件未启用时回填内部 `ce`，供 kernel/android/restartkodi/fastoff/poweroff/reboot/clean 判定；它救不回 `coreelec` 本身 |
| `Capability.kernel` | CoreELEC 且 `/storage/.config` 可写 |
| `Capability.android` | CoreELEC 且 `/usr/sbin/rebootfromnand` 存在且可执行 |
| `Capability.restartkodi` | CoreELEC 且 `nohup`、`sh` 均可用 |
| `Capability.fastoff` | CoreELEC 且可关机且 `/usr/sbin/poweroff` 可执行 |
| `Capability.poweroff` | CoreELEC 且可关机 |
| `Capability.reboot` | CoreELEC 且可重启且 `reboot`、`sync` 均可用 |
| `Capability.clean` | CoreELEC 且 `/proc/sys/vm/drop_caches` 可写 |
| `Capability.<name>.Reason` | 不支持时固定文案“当前设备不支持或缺少所需权限”，支持时为空 |
| `Capability.Snapshot` | 全部 10 项的 JSON 快照（`sort_keys`），供 `only_changed` 比对 |

执行侧仍以 `dispatch()`（`infuse_device.py:55` 起）实时重算能力为准，确认对话框期间能力变化会取消操作；
`PowerHelp` 与 Capability 是两套属性，前者只负责菜单里的帮助文案：菜单打开时由 `infuse_power_menu.py:35`
写默认提示，之后各选项聚焦时由 `DialogButtonMenu.xml:104–504` 的 8 处 `onfocus` 覆盖为对应中文说明，
`DialogButtonMenu.xml:5` 的 `onunload` 清除。

## 7. 系统指标：System.*

写方：`scripts/infuse_system.py` 的 `run('refresh')`，由 `custom_1182_HomeSystem.xml:534` 的 `<onload>` 启动；
仅当 1182/1183/1184/1185/1194/SystemInfo 任一窗口可见时持续刷新（`infuse_system.py:18,221–223`），
指标每 1 秒一轮、库计数每 30 轮一轮（`infuse_system.py:256–262`）。读方：`custom_1182_HomeSystem.xml`
等系统窗口；另有 `SettingsSystemInfo.xml:908` 的 `native-versions` 直接弹版本对话框，不走属性。

字段（前缀均为 `YoPlayer.Infuse.System.`，`put()` 位置见 `infuse_system.py`）：

- 设备与版本：`DeviceName`（CoreELEC 或平台名，`:243`）、`OS`、`PlatformVersion`、`Skin`、
  `SkinVersion`（皮肤 addon 版本，`:246`）、`PlayerVersion`（Kodi 构建版本首段，`:245`）、
  `Kernel`、`KernelBuild`、`Firmware`（优先 Skin.String(version)，回退 `PlatformVersion`）、
  `Hardware`（优先 Skin.String(hwtype)，回退 `/proc/device-tree/model`）、`Capacity`、`LinkSpeed`、
  `VersionLabel`（CoreELEC 时为“固件版本”否则“系统版本”）。
- 屏幕与网络：`Screen`、`ScreenMeta`（刷新率 + 全屏/窗口，`:109`）、`IP`、`Link`、`Connected`
  （“已连接”/“未连接”，`:111`）、`HDR`（`:117`）、`DolbyVision`（CoreELEC 时读
  `coreelec.amlogic.dolbyvision.*` 设置）、`RefreshMode`、`DisplayAction`、`LogAction`、`Status`（带时间戳的汇总行）。
- CPU 与内存：`CpuPercent`、`CpuAverage`、`CpuRing`、`Core0–3`、`CoreText0–3`、`CoreLabel0–3`、
  `CpuModel`、`CpuAvailable`（`true`/`false`）、`CpuState`（`ready`/`sampling`/`unavailable`）、
  `MemoryPercent`、`MemoryRing`、`MemoryDetail`、`MemoryTotal`、`MemoryUsage`、`MemoryAvailable`。
  Linux 读 `/proc/stat` 与 `System.Memory(*)` 标签；Windows 走 `ctypes` 的系统 API。
- 运行状态：`Uptime`、`TotalUptime`（`:112`）、`Temperature`、`TemperatureText`（`:115–116`，
  取不到时分别为 `—` 与“设备未提供”）。
- 库计数（`infuse_system.py:58` 的 `library()`，失败时写 `—`）：`Movies`/`MoviesUnwatched`/`MoviesWatched`、
  `Shows`/`ShowsUnwatched`/`ShowsWatched`、`Episodes`/`EpisodesUnwatched`/`EpisodesWatched`、
  `MusicVideos`/`MusicVideosUnwatched`/`MusicVideosWatched`、`Songs`、`Albums`、`Artists`。
- 刷新会话保护：`System.Owner`（`infuse_system.py:216,262`），旧的刷新调用在窗口关闭后不再发布。

## 8. 已核实与未覆盖 / 未找到

**已核实（均有上文文件:行号证据）：** 三方写入分工；Revision/DataChanged/RefreshPending 的完整触发链；
8 个 Home 行路由 + 探针容器的 Count/Loaded/Error 语义；15 秒缓存族与 daily 按日规则；cacheToDisc 全为 False；
membership 签名的构成与“可见胜出、未知默认可见”规则；Memory* 五项与 StreamRevision 的签名触发规则；
Capability 10 项的判定来源；System.* 约 59 组字段的来源与刷新节奏；搜索缓存与状态文案；
GenreArt 缓存与 MediaReadOwner 测速令牌。

**未在代码中找到（不要按惯例补）：**

- 会员/订阅/有效期/等级字段：membership 只是分库归属判定，无账号与付费概念（第 4 节）。
- `YoPlayer.Infuse.Search`（不带后缀）的独立属性：皮肤只读 `Search.Status`（`MyVideoNav.xml:224`），
  另有插件内部键 `Search.Cache`；不存在裸 `Search` 属性。
- `Loaded.<分类路由>`：分类行只写 `Count.`，不写 `Loaded.`；`Loaded.libraries == Revision` 是
  `RefreshPending` 唯一的“行已加载”判定（`Variables.xml:5`、`infuse.py:205`），`RestoreAt` 不用它（见第 1 节）。
- 播放记忆的落盘位置：`Memory*` 只存在 Window 属性里；`infuse_stream_memory.py` 的持久化记忆文件
  本页未展开（`live()` 的 token 与 `save()` 的文件格式不在本次核实范围内）。
- `BrowseShow` 的皮肤侧读取：写方明确（`infuse.py:296`），但未在皮肤 XML 里找到对应读取。
- `infuse.py` 的 `startup` 之外的启动路径：皮肤 addon 没有 service 扩展，runtime 唯一入口是
  `Home.xml:643` 的 `<onload>`；Kodi 非 Home 窗口启动时 runtime 不运行。
