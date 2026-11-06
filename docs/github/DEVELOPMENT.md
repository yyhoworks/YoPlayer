# 开发说明

检查与打包使用 Python 3.10+。XBT 像素验证需要 Pillow 和 lzokay，安装固定依赖后运行；不需要启动 Kodi。

```bash
git clone https://github.com/yyhoworks/YoPlayer.git
cd YoPlayer
python -m pip install -r tools/requirements-checks.txt
python tools/check_infuse_structure.py --repository
```

当前源码为 Skin152/Home1.0.48。`python tools/check_playback_controls.py` 运行既有23项隔离偏好、导航与轨道展示回归；`python tools/check_theme_delivery.py` 运行23项主题打包与空心焦点、双向资源集合、生成器只读、真实调色板故障注入和升级提示回归。`python tools/check_home_rows.py`运行7项首页状态/刷新回归，`python tools/check_browse_cache.py`运行7项缓存边界回归；上述入口均不连接Kodi，不替代CE实机验证。历史117冻结检查和遗留边界保留。

公开仓库可直接克隆。界面 XML 位于 `source/skin.yoplayer.infuse/1080p/`，皮肤脚本位于 `scripts/`；首页组件入口为 `default.py`，库模块位于 `resources/lib/`。

## 检查范围

| 入口 | 环境 | 范围 |
|---|---|---|
| `python tools/check_infuse_structure.py --repository` | 全新克隆 / Actions | ID、版本与依赖，语法、资源、主题、XBT与散图像素，许可及字体，运行成员 SHA256 |
| `python tools/check_infuse_structure.py` | 117维护者工作区 / 全新克隆 | 117专项：115交付哈希、允许差量、控件几何、结构与44项离线回归；不导入旧恢复模块 |

仓库检查生成 `docs/structure-validation.repository.json`，该文件不进入 Git。检查读取源码，不导入 Kodi 运行模块、不重建 `source/`、不连接设备。

原版 `scripts/R4.xml` 实际为 PO 翻译参考文本，按固定 SHA256 保留校验，不作为 XML 解析；其余 XML 均检查语法。

## 可选自动检查

当前 `.github/workflows/skin-gate.yml` 在 PR 和 main push 上运行 `build_theme_assets.py --check`、严格引用、仓库检查和主题交付回归；真实生成检查比较themes.json与PNG，仓库检查再比较PNG与XBT。[旧 Actions 模板](offline-workflow.yml)仅作历史参考。

## 主题素材维护

`python tools/build_theme_assets.py --check` 和 `python tools/build_theme_xml.py --check` 仅比较，不写源码；未知参数会报错。无 `--check` 才显式生成。

修改主题PNG后运行 `python tools/check_texture_bundle.py --sync-themes`，在保留旧包独有资源的基础上替换主题图、增加新图并删除主题别名对应的退役项；默认无参数仅检查。不要仅从现有散图目录重建整个XBT，否则会丢失没有散图副本的原生控件资源。检查器比较所有同路径PNG/JPEG，3处既有差异由 `tools/texture-check-baseline.json` 的固定双侧哈希限定，主题不允许例外。

主题命名空间 `infuse/themes/` 必须在散图与XBT中双向一致。缺少散图的包内条目会失败，不能以“旧资源保留”为由豁免；非主题旧资源不受此集合限制。删除单个主题图后，应明确审查并更新包内对应条目，或恢复散图；`--sync-themes` 不会猜测删除非别名目录中的孤儿，仓库检查会阻止它进入交付。

117的专项回归与冻结115成员/控件指纹随源码跟踪，默认入口运行它们；`--repository`仍只是语法、资源和静态契约检查。其他历史版本的本地限定回归可能不随Git提供，不能将其结果记到117。检查报告写入`docs/structure-validation.json`和`docs/structure-validation.repository.json`，不重建源码。报告中的packaged/deployed/coreelec_acceptance描述该离线入口未执行这些操作，不是对历史安装状态的查询；实际部署和验收结论见单独测试报告。

## 打包

全新克隆运行：

```bash
python tools/package_project.py --repository
```

此模式先运行仓库检查，仅打包两个插件的运行成员，输出到 `dist/`，同时生成 `SHA256SUMS.txt`。已有同名 ZIP 或校验清单会使操作停止，不覆盖旧文件；不生成含本地证据的 bundle。

SHA256标识该次构建制品。新建ZIP当前使用构建时间戳，尚非确定性输出；不同检出或构建时间的ZIP字节可能不同。验证源码一致性时比较归档成员和解压内容，不能把某次ZIP哈希当作独立重建保证。复用已交付同内容归档时保留原ZIP字节。

已有交付文件时，可以指定新的子目录，原输出保持：

```bash
python tools/package_project.py --repository --output dist/my-new-build
```

指定目录必须位于项目 `dist/` 内。117打包先运行专项门禁，并只读检查当前/主工作区`dist/`及`releases/`中的标准同版本档案；同版不同内容拒绝，存在相同成员的已交付包时复用原ZIP字节。目标目录已有同名包或校验清单仍会使构建停止。守卫使用临时夹具测试；117已于2026-10-15打包并安装，本次同步不重复打包。已交付运行文件（包括addon.xml的news和changelog）保持原字节，后续运行修复必须升版，不能用同版覆盖。

完整维护者工作区核验历史版本时使用：

```bash
python tools/check_infuse_structure.py
python tools/package_project.py
```

默认打包仍依赖维护者本地冻结基准与证据输入，输出到`releases/`，同样进行跨目录同版本内容核对。全新克隆缺少历史输入时使用上述`--repository`打包入口；无论哪种模式，离线通过都不自动获得设备验收状态。117没有新增退役文件。

## 修改规则

- 运行插件 ID 保持不变。运行文件变化时对应升版，并调整必要的 Home 最低依赖。
- 文档和开发工具不改变当前运行版本。`.gitattributes` 禁用源码换行转换，保持运行字节。
- 保留许可证、字体、CoreELEC 操作、分库设置、播放地址及真实观看/续播值。
- 删除资源前核对静态与动态引用，记录精确退役文件。
- 检查与构建不会部署；设备维护需要当前状态和有效备份，不重复历史脚本。

体验改动应提供相关 CoreELEC 证据；实体电视、硬解/HDR、遥控及 CEC 人工验收单独记录。

## 148 页面主题接入

resources/theme-ui.json记录中性蒙版与原始形状来源；tools/theme_ui_assets.py纳入素材生成器。同一蒙版由语义颜色在渲染时着色，不为新页面复制五套有色原生贴图。包内旧资源只读解码作形状来源，新增蒙版与旧条目各自存在；XBT检查同时约束themes与theme-ui双向集合。

tools/check_theme_coverage.py覆盖主要页面接入、蒙版纯白RGB与tint、全主题/播放角色、原生选中标签selectedcolor、浅色详情徽章边界和剩余时间无效值。Kodi原生ListLabel在选中时使用COLOR_SELECTED，参照[GUIListLabel.cpp](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/guilib/GUIListLabel.cpp#L32)；colordiffuse动态值见[Texture Attributes](https://kodi.wiki/view/Texture_Attributes)。不以页面存在素材代替实际引用与截图。


## 149 播放透明玻璃

所有Overlay角色独立于主题，播放专属窗显式引用Overlay；共享弹窗在fullscreenvideo/visualisation使用相同颜色。主要面板复用既有alpha166玻璃蒙版，固定字面路径与尺寸，详GLASS149.md与VALIDATION149.md。
