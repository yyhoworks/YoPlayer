# -*- coding: utf-8 -*-
"""
KODI收藏夹同步脚本 (favfenku_updated.py) - 最终定稿版
修改说明汇总(全量完整):
1. ✔ 删除 所有 ActivateWindow 窗口跳转相关代码 (Videos/1119)
2. ✔ 更新完成后 强制执行 皮肤重载 Skin.Reload() 逻辑 (无任何例外)
3. ✔ 保留 无参数静默运行 + 带【check】参数弹窗通知运行 的双模式
4. ✔ 核心逻辑修改：无论任何条件，只要收藏夹有效就【强制更新皮肤变量】
5. ✔ 取消所有「是否需要更新」的判断逻辑，无任何前置条件限制更新操作
6. ✔ 保留原脚本全部核心解析、清残留、异常处理、容错机制 无任何删减
"""

# 导入所有必备模块
import xbmc
import xbmcvfs
import xbmcgui
import os
import sys
import xml.etree.ElementTree as ET

def parse_and_set_skin_strings(xml_file_path):
    """解析指定的XML文件，并将其中的收藏条目设置为KODI皮肤字符串（原逻辑完全不变）"""
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        # 清除旧的变量，防止旧条目残留，这个核心优化必须保留
        i = 1
        while xbmc.getInfoLabel(f'Skin.String(favname{i})'):
            xbmc.executebuiltin(f'Skin.Reset(favname{i})')
            xbmc.executebuiltin(f'Skin.Reset(favpath{i})')
            i += 1

        for index, favourite in enumerate(root.findall('favourite'), start=1):
            fav_name = favourite.get('name', '')
            fav_command = favourite.text
            
            fav_path = ''
            if fav_command and '"' in fav_command:
                parts = fav_command.split('"')
                if len(parts) > 1:
                    fav_path = parts[1]
            elif fav_command and 'PlayMedia(' in fav_command:
                fav_path = fav_command.replace('PlayMedia(', '').rstrip(')')

            name_var = f"favname{index}"
            path_var = f"favpath{index}"

            xbmc.executebuiltin(f'Skin.SetString({name_var},"{fav_name}")')
            xbmc.executebuiltin(f'Skin.SetString({path_var},"{fav_path}")')

            xbmc.log(f"favfenku: Set {name_var} = \"{fav_name}\"", xbmc.LOGDEBUG)
            xbmc.log(f"favfenku: Set {path_var} = \"{fav_path}\"", xbmc.LOGDEBUG)

    except ET.ParseError:
        xbmc.log("favfenku: Error parsing favourites.xml. The file may be corrupted.", xbmc.LOGERROR)
    except Exception as e:
        xbmc.log(f"favfenku: An unexpected error occurred during parsing: {e}", xbmc.LOGERROR)

def main():
    """脚本主函数"""
    # ========== 保留：静默/弹窗 双模式参数判断 ==========
    show_dialog_notify = False
    if len(sys.argv) > 1 and "check" in sys.argv:
        show_dialog_notify = True
        xbmc.log("favfenku: 检测到[check]参数，本次运行将弹窗展示结果", xbmc.LOGINFO)
    dialog = xbmcgui.Dialog()
    dialog_title = "收藏夹同步检查"
    
    # 1. 定义并获取必要的文件路径
    userdata_path = xbmcvfs.translatePath("special://userdata/")
    fav_xml_path = os.path.join(userdata_path, "favourites.xml")
    fav_time_path = os.path.join(userdata_path, "favchangetime")

    # 2. 保留：核心前置检查 - 仅收藏夹为空/无效时退出，其余全部执行更新
    has_favourites = False
    if xbmcvfs.exists(fav_xml_path):
        try:
            tree = ET.parse(fav_xml_path)
            root = tree.getroot()
            if root.findall('favourite'):
                has_favourites = True
        except ET.ParseError:
            xbmc.log("favfenku: Error parsing favourites.xml. The file may be corrupted.", xbmc.LOGERROR)

    if not has_favourites:
        xbmc.log("favfenku: Favourites list is empty or file not found.", xbmc.LOGINFO)
        if show_dialog_notify:
            dialog.ok(dialog_title, "收藏夹为空或文件无效！\n未检测到可用的收藏内容。")
        return

    # ========== ✅【核心修改1：全部删除】所有 needs_update 判断逻辑 ==========
    # 删掉了：时间戳对比、首次运行判断、皮肤变量是否存在判断 等所有前置更新条件
    # ========== ✅【核心修改2：无条件强制执行更新】无任何判断，直接解析+赋值 ==========
    xbmc.log("favfenku: 强制执行收藏夹变量更新，无视文件修改状态", xbmc.LOGINFO)
    parse_and_set_skin_strings(fav_xml_path)

    # ========== ✅【核心修改3：强制更新时间戳文件】同步最新的修改时间 ==========
    current_mtime = os.path.getmtime(fav_xml_path)
    try:
        with open(fav_time_path, 'w') as f:
            f.write(str(current_mtime))
        xbmc.log("favfenku: 收藏夹变量更新完成，已同步最新修改时间", xbmc.LOGINFO)
    except IOError as e:
        xbmc.log(f"favfenku: Error writing to favchangetime file: {e}", xbmc.LOGERROR)
        if show_dialog_notify:
            dialog.ok(dialog_title, "⚠️ 收藏夹变量更新完成\n记录文件保存失败，不影响当前使用")

    # ========== ✅【核心修改4：无条件执行重载皮肤，无任何例外】 ==========
    # 无论是否写入时间戳成功、无论收藏夹是否变更，更新变量后必重载皮肤，生效最新数据
    xbmc.executebuiltin("Skin.Reload()")
    xbmc.log("favfenku: 皮肤已强制重载，收藏夹变量全部生效", xbmc.LOGINFO)

    # ========== 保留：带check参数时的成功弹窗通知 ==========
    if show_dialog_notify:
        dialog.ok(dialog_title, "✅ 收藏夹变量强制更新完成！\n皮肤已重载，所有收藏内容已生效。")

# 当脚本作为主程序运行时，执行main函数
if __name__ == '__main__':
    main()