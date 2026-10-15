# 开发说明

检查与打包只需要 Python 3.10+ 标准库，已在 Python 3.13 验证，不需要额外 pip 依赖或启动 Kodi。

```bash
git clone https://github.com/yyhoworks/YoPlayer.git
cd YoPlayer
python tools/check_infuse_structure.py --repository
```

当前源码为115基线上的117，已打包并完成CE停态安装与限定测试；仍有两项P2未通过，见[117限定测试报告](VALIDATION117.md)。Home源码及依赖保持1.0.37；不包含116视觉改动。本次GitHub同步不重打包、不再连接设备。

公开仓库可直接克隆。界面 XML 位于 `source/skin.yoplayer.infuse/1080p/`，皮肤脚本位于 `scripts/`；首页组件入口为 `default.py`，库模块位于 `resources/lib/`。

## 检查范围

| 入口 | 环境 | 范围 |
|---|---|---|
| `python tools/check_infuse_structure.py --repository` | 全新克隆 / 可选 Actions | ID、版本与依赖，XML/JSON/Python 语法，必需入口、许可及字体，运行成员 SHA256 |
| `python tools/check_infuse_structure.py` | 117维护者工作区 / 全新克隆 | 117专项：115交付哈希、允许差量、控件几何、结构与44项离线回归；不导入旧恢复模块 |

仓库检查生成 `docs/structure-validation.repository.json`，该文件不进入 Git。检查读取源码，不导入 Kodi 运行模块、不重建 `source/`、不连接设备。

原版 `scripts/R4.xml` 实际为 PO 翻译参考文本，按固定 SHA256 保留校验，不作为 XML 解析；其余 XML 均检查语法。

## 可选自动检查

[Actions 模板](offline-workflow.yml)运行同一仓库检查，目前未启用：现有 GitHub 凭据没有 `workflow` 权限。需要启用时，用具有相应权限的登录把模板放到 `.github/workflows/offline.yml`，并从 `.gitignore` 移除对该目录的忽略后提交。当前不会自动更改登录权限。

117的专项回归与冻结115成员/控件指纹随源码跟踪，默认入口运行它们；`--repository`仍只是语法、资源和静态契约检查。其他历史版本的本地限定回归可能不随Git提供，不能将其结果记到117。检查报告写入`docs/structure-validation.json`和`docs/structure-validation.repository.json`，不重建源码。报告中的packaged/deployed/coreelec_acceptance描述该离线入口未执行这些操作，不是对历史安装状态的查询；实际部署和验收结论见单独测试报告。

## 打包

全新克隆运行：

```bash
python tools/package_project.py --repository
```

此模式先运行仓库检查，仅打包两个插件的运行成员，输出到 `dist/`，同时生成 `SHA256SUMS.txt`。已有同名 ZIP 或校验清单会使操作停止，不覆盖旧文件；不生成含本地证据的 bundle。

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
