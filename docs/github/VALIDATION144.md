# 144 限定验证

PR #18当前候选Skin144/Home1.0.43。143和144都尚未在Kodi实机加载；本轮没有连接设备、播放、扫描或修改共享观看状态。

## 离线验证

- 两个生成器 `--check`、严格引用、仓库结构 `--repository`（含主题和XBT）、16项主题交付回归及23项播放控制回归通过。
- 新增4项：真实调色板改动而PNG过期；新安装在startup先完成/首次有播放/后续重入时不派发提醒；旧用户因播放或弹窗延迟后可提示且随后不派发；已有主题和提醒标志阻止派发。
- `ink.onAccent` 从 `#141416` 改为 `#000000` 的临时故障注入，只改themes.json，旧PNG/XBT不动时，素材 `--check` 必须失败并列出3张开关图，且不得写文件。CI现在显式执行这一真实生成检查。
- 新安装标记在Home启动动作之前执行，通知动作同时要求 `FirstTimeRun`；测试按Kodi“先筛选整组条件、再顺序执行”的方式重放实际XML，并模拟startup在排队通知前完成。不能仅在通知脚本里晚读FirstTimeRun。
- 保留143提醒标志和脚本内保护：播放、模态窗口、非首页不通知，通知失败不标记，用户主题不自动改写。此标志只能表示是否完成过初始化，无法恢复被重置或丢失的历史用户状态。
- PNG及XBT与143完全相同；XBT 2600条，1011同路径图检查，393主题图一致，3处非主题例外继续锁定双方哈希。2442个继承条目的元数据/压缩内容保持，1589个包独有资源保留。

## 实现依据与限制

Kodi21.2的 [GUIAction.cpp](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/guilib/GUIAction.cpp#L69) 先筛选满足条件的动作，再按顺序派发；[SkinBuiltins.cpp](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/interfaces/builtins/SkinBuiltins.cpp#L154) 的Skin.SetBool直接写入皮肤设置。新安装动作不依赖Python先后启动时序。

XBT去重由 [Kodi XBTFWriter](https://github.com/xbmc/xbmc/blob/21.2-Omega/tools/depends/native/TexturePacker/src/XBTFWriter.cpp#L119) 支持。当前143/144共501帧复用偏移，不是509。离线LZO验证使用lzokay，尚未使用目标Kodi的liblzo2或设备加载验证；依赖固定版本，尚未使用pip包哈希锁定。

无参数结构检查仍缺当前版本的reviewed default contract，通过的是 `--repository`。主题/通知真实显示、完整切换保存、OSD、实体电视/遥控/CEC待验；P142-PROTECT-001、P142-CAPTURE-001、P142-LOG-001不因本轮修复关闭。143旧包不覆盖。
