# 141 限定验证

- 仓库结构门禁（--repository）、严格引用检查、23项播放控制回归、XML解析与差异检查通过；GitHub skin-gate 在 0f8e847 成功。
- 沙箱 Kodi 21.2 arm64（软件GL，Xvfb 1920×1080，中文界面）加载 Skin 2026.10.3.141，日志无皮肤解析错误。
- 选择框：主页调用为浅色原样式，全屏视频中调用为深色样式，确认 `$EXP[YoPlayerDarkSelectContext]` 在 variable 与 visible 条件中均生效。
- 轨道面板：长章节名（约60字）样片在1144字幕与1145音轨面板中省略显示，与剩余时长不重叠；OSD底栏章节行同样省略。
- HDR原始值映射按播放器 StreamHdrType 枚举（0无、1 HDR10、2 HDR10+、3 Dolby Vision、4 HLG）核对：OSD标签、VS10直通编码角标、全屏视频旗标与HDR类型文字中 raw=3 均为 Dolby Vision。

未覆盖：标准Kodi没有CoreELEC的 `amlogic.vs10.mode` 与真实HDR/DV解码，HDR/DV标签、旗标和VS10转换分支未经实机显示；实体电视观感、大字体设置、实体遥控/CEC、真实Emby片源均未覆盖。Home 1.0.43 为 PR #14–#16 已合入的改动，本轮未单独实机验证。
