# 开发说明

检查与打包只需要 Python 3.10+ 标准库，已在 Python 3.13 验证，不需要额外 pip 依赖或启动 Kodi。

```bash
git clone https://github.com/yyhoworks/YoPlayer.git
cd YoPlayer
python tools/check_infuse_structure.py --repository
```

公开仓库可直接克隆。界面 XML 位于 `source/skin.yoplayer.infuse/1080p/`，皮肤脚本位于 `scripts/`；首页组件入口为 `default.py`，库模块位于 `resources/lib/`。

## 检查范围

| 入口 | 环境 | 范围 |
|---|---|---|
| `python tools/check_infuse_structure.py --repository` | 全新克隆 / 可选 Actions | ID、版本与依赖，XML/JSON/Python 语法，必需入口、许可及字体，运行成员 SHA256 |
| `python tools/check_infuse_structure.py` | 完整维护者工作区 / 全新克隆 | 本地冻结契约可用时运行当前限定回归；缺少本地维护者模块时明确运行仓库检查 |

仓库检查生成 `docs/structure-validation.repository.json`，该文件不进入 Git。检查读取源码，不导入 Kodi 运行模块、不重建 `source/`、不连接设备。

原版 `scripts/R4.xml` 实际为 PO 翻译参考文本，按固定 SHA256 保留校验，不作为 XML 解析；其余 XML 均检查语法。

## 可选自动检查

[Actions 模板](offline-workflow.yml)运行同一仓库检查，目前未启用：现有 GitHub 凭据没有 `workflow` 权限。需要启用时，用具有相应权限的登录把模板放到 `.github/workflows/offline.yml`，并从 `.gitignore` 移除对该目录的忽略后提交。当前不会自动更改登录权限。

部分版本限定回归、参考数据、设备快照和历史输入未进入Git。全新克隆建议使用`--repository`；默认入口检测不到本地维护者模块时会明确运行同一仓库检查，不导入缺失的历史依赖、不把仓库语法检查算作设备验收。完整维护者工作区按对应冻结契约运行96–101有限检查，101当前13项通过。本次公开源码与已验证101安装包逐成员一致，具体设备证据留在维护者本地。

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

指定目录必须位于项目 `dist/` 内，已有同名包或校验清单仍会使构建停止。

完整维护者工作区核验历史版本时使用：

```bash
python tools/check_infuse_structure.py
python tools/package_project.py
```

默认打包保留历史基准与当前验证要求，输出到 `releases/`，拒绝覆盖已交付同版本包。101版沿用已由上面 `--repository` 打包入口生成的两独立包，逐成员匹配当前源码和CE101安装树；发布时复用已交付包，不覆盖同版本档案。仓库独立构建不自动获得实机验收状态。

## 修改规则

- 运行插件 ID 保持不变。运行文件变化时对应升版，并调整必要的 Home 最低依赖。
- 文档和开发工具不改变当前运行版本。`.gitattributes` 禁用源码换行转换，保持运行字节。
- 保留许可证、字体、CoreELEC 操作、分库设置、播放地址及真实观看/续播值。
- 删除资源前核对静态与动态引用，记录精确退役文件。
- 检查与构建不会部署；设备维护需要当前状态和有效备份，不重复历史脚本。

体验改动应提供相关 CoreELEC 证据；实体电视、硬解/HDR、遥控及 CEC 人工验收单独记录。
