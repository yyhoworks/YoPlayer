# -*- coding: utf-8 -*-
# KODI搜索脚本：适配全版本KODI（18及更早/19+）的最终可运行版本
# 修复：1. 列表项点击无反应；2. translatePath属性不存在；3. Unknown addon id错误
# 保留：路径记录 + ListItem.FilenameAndPath赋值
# 新增：1. 双参数触发逻辑；2. 自定义STRM路径（文件持久化，重启有效）；3. 全版本API兼容
# 修改：移除右下角提示弹窗，列表项添加[文件]/[文件夹]标识
import xbmc
import xbmcgui
import xbmcvfs
import sys
import os

# ========== 核心修复：兼容Kodi 18/19+的路径转换API ==========
def get_kodi_path(path):
    """跨版本路径转换：兼容Kodi 18及更早/19+"""
    if hasattr(xbmc, 'translatePath'):
        # Kodi 18及更早版本
        return xbmc.translatePath(path)
    else:
        # Kodi 19+版本（Matrix）
        return xbmcvfs.translatePath(path)

# 定义文件存储路径（跨平台+跨版本兼容）
USERDATA_PATH = get_kodi_path("special://userdata/")
STRM_PATH_FILE = xbmcvfs.makeLegalFilename(os.path.join(USERDATA_PATH, "strm_search_path.txt"))

def get_search_directory():
    """获取跨平台的搜索根目录（优先读取文件存储的自定义路径，永久生效）"""
    # 第一步：尝试读取文件中的自定义路径
    custom_path = ""
    if xbmcvfs.exists(STRM_PATH_FILE):
        # 读取文件内容（兼容旧版KODI的文件操作）
        file_handle = xbmcvfs.File(STRM_PATH_FILE, "r")
        try:
            custom_path = file_handle.read().strip()
        finally:
            file_handle.close()
    
    # 有自定义路径且路径存在，优先使用
    if custom_path and xbmcvfs.exists(custom_path):
        return xbmcvfs.makeLegalFilename(custom_path)
    
    # 无自定义路径，使用原预设路径
    if xbmc.getCondVisibility('system.platform.windows'):
        raw_path = 'C:\\storage\\videos\\strm\\'
    else:
        raw_path = '/storage/videos/strm/'
    return xbmcvfs.makeLegalFilename(raw_path)

def set_strm_folder_path():
    """弹出目录选择窗口，让用户设置STRM搜索根目录并永久保存到文件"""
    dialog = xbmcgui.Dialog()
    
    # 1. 获取当前路径（用于目录选择窗口的初始位置）
    current_path = get_search_directory()
    
    # 2. 弹出KODI原生目录选择窗口（全版本兼容）
    selected_path = dialog.browse(3, "选择STRM搜索根目录", "files", "", False, True, current_path)
    
    # 3. 处理用户选择（取消选择则返回空字符串）
    if not selected_path:
        dialog.ok("提示", "未选择任何目录，路径设置取消")
        return
    
    # 4. 验证路径合法性并永久保存到文件
    legal_path = xbmcvfs.makeLegalFilename(selected_path)
    # 写入文件（覆盖原有内容，兼容所有KODI版本）
    file_handle = xbmcvfs.File(STRM_PATH_FILE, "w")
    try:
        file_handle.write(legal_path)
        dialog.ok("设置成功", f"STRM搜索目录设置为：\n{legal_path}")
    except Exception as e:
        dialog.ok("设置失败", f"保存路径出错：{str(e)}")
        xbmc.log(f"Save STRM path error: {str(e)}", level=xbmc.LOGERROR)
    finally:
        file_handle.close()

def recursive_search(search_path, keyword):
    """递归搜索指定目录下包含关键词的文件和文件夹"""
    results = []
    dirs, files = xbmcvfs.listdir(search_path)
    
    # 处理文件夹
    for dir_name in dirs:
        dir_full_path = xbmcvfs.makeLegalFilename(os.path.join(search_path, dir_name))
        if keyword.lower() in dir_name.lower():
            list_item = xbmcgui.ListItem(label=dir_name, path=dir_full_path)
            # 赋值FilenameAndPath核心属性
            list_item.setProperty("FilenameAndPath", dir_full_path)
            list_item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
            # 标记类型（用于后续判断）
            list_item.setProperty("isFolder", "true")
            results.append((dir_full_path, list_item, "folder"))
        results.extend(recursive_search(dir_full_path, keyword))
    
    # 处理文件
    for file_name in files:
        file_full_path = xbmcvfs.makeLegalFilename(os.path.join(search_path, file_name))
        if keyword.lower() in file_name.lower():
            list_item = xbmcgui.ListItem(label=file_name, path=file_full_path)
            # 赋值FilenameAndPath核心属性
            list_item.setProperty("FilenameAndPath", file_full_path)
            list_item.setArt({'icon': 'DefaultVideo.png', 'thumb': 'DefaultVideo.png'})
            # 标记类型（用于后续判断）
            list_item.setProperty("isFolder", "false")
            results.append((file_full_path, list_item, "file"))
    
    return results

def handle_item_click(path, item_type):
    """处理列表项点击事件"""
    dialog = xbmcgui.Dialog()
    try:
        if item_type == "file":
            # 播放媒体文件（移除右下角提示）
            xbmc.executebuiltin(f'PlayMedia("{path}")')
        elif item_type == "folder":
            # 打开文件夹（移除右下角提示）
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{path}")')
    except Exception as e:
        dialog.ok("执行失败", f"操作失败：{str(e)}")
        xbmc.log(f"Item click error: {str(e)}", level=xbmc.LOGERROR)

def main():
    dialog = xbmcgui.Dialog()
    # 1. 获取搜索关键词
    search_keyword = dialog.input("搜索", type=xbmcgui.INPUT_ALPHANUM)
    if not search_keyword:
        return
    
    # 2. 检查搜索目录
    search_root = get_search_directory()
    if not xbmcvfs.exists(search_root):
        dialog.ok("错误", f"搜索目录不存在：\n{search_root}")
        return
    
    # 3. 执行搜索（移除右下角提示）
    search_results = recursive_search(search_root, search_keyword)
    
    # 4. 无结果处理
    if not search_results:
        dialog.ok("搜索结果", "未找到包含「{}」的文件或文件夹".format(search_keyword))
        return
    
    # 5. 记录所有路径到日志
    xbmc.log("=== 本次搜索结果路径列表 ===", level=xbmc.LOGINFO)
    for idx, (path, _, _) in enumerate(search_results, 1):
        xbmc.log(f"{idx}. {path}", level=xbmc.LOGINFO)
    
    # 6. 弹出选择对话框（全版本最稳定的交互方式）
    list_items = []
    for path, list_item, item_type in search_results:
        prefix = "[文件]" if item_type == "file" else "[文件夹]"
        original_label = list_item.getLabel()
        new_label = f"{prefix} {original_label}"
        list_item.setLabel(new_label)
        list_items.append(list_item)
    
    # 显示选择对话框，获取用户选择的索引
    selected_idx = dialog.select(f"搜索结果（共{len(list_items)}个）", list_items)
    
    # 7. 处理用户选择
    if selected_idx != -1:
        selected_path, _, selected_type = search_results[selected_idx]
        handle_item_click(selected_path, selected_type)

def handle_select_mode():
    """处理带select参数时的选择逻辑"""
    dialog = xbmcgui.Dialog()
    origin_window = xbmcgui.getCurrentWindowId()
    origin_path = xbmc.getInfoLabel('Container.FolderPath')
    can_filter_advanced = xbmc.getCondVisibility('Container.CanFilterAdvanced')
    can_filter = can_filter_advanced or xbmc.getCondVisibility('Container.CanFilter')
    if can_filter_advanced:
        filter_label = '高级筛选当前列表'
    elif can_filter and xbmc.getCondVisibility('Control.IsVisible(19)'):
        filter_label = '编辑当前列表筛选'
    elif can_filter:
        filter_label = '筛选当前列表（已有筛选时清除）'
    else:
        filter_label = '当前列表筛选（此处不可用）'
    # 插入"设置STRM文件夹路径"选项
    select_options = [
        "使用插件搜索媒体库",
        "搜索STRM文件目录(包含子目录)",
        "设置STRM文件夹路径",  # 新增选项
        "自带媒体库搜索功能(可搜索演员和剧情)",
        filter_label
    ]
    # 弹出选择窗口
    selected_idx = dialog.select("选择搜索类型", select_options)
    
    # 处理用户选择
    if selected_idx == 0:
        # 核心逻辑：第一项三级判断逻辑
        addon_id = "script.globalsearch"
        # 第一步：判断插件是否已启用
        if xbmc.getCondVisibility(f'System.AddonIsEnabled({addon_id})'):
            xbmc.executebuiltin(f'RunScript({addon_id})')
        else:
            # 第二步：插件未启用，判断是否已安装
            if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
                xbmc.executebuiltin(f'EnableAddon({addon_id})')
            else:
                # 第三步：插件未安装，执行安装
                xbmc.executebuiltin(f'InstallAddon({addon_id})')
    elif selected_idx == 1:
        # 第二项 原逻辑不变
        xbmc.executebuiltin('RunScript(special://skin/scripts/search.py,strm)')
    # 处理"设置STRM文件夹路径"选项
    elif selected_idx == 2:
        set_strm_folder_path()
    elif selected_idx == 3:
        # 原第三项变为第四项，逻辑不变
        xbmc.executebuiltin('SendClick(8)')
    elif selected_idx == 4:
        # Kodi's ACTION_FILTER owns both the filter keyboard and advanced dialog.
        # Control 19 is optional; the video skin intentionally has no edit 19.
        if (xbmcgui.getCurrentWindowId() != origin_window or
                xbmc.getInfoLabel('Container.FolderPath') != origin_path):
            dialog.ok('列表已变化', '请在当前列表重新打开筛选。')
        elif not can_filter or not (xbmc.getCondVisibility('Container.CanFilterAdvanced') or
                                    xbmc.getCondVisibility('Container.CanFilter')):
            dialog.ok('当前列表筛选', '此列表不支持筛选。')
        else:
            if (not xbmc.getCondVisibility('Container.CanFilterAdvanced') and
                    xbmc.getCondVisibility('Control.IsVisible(19)')):
                # Other callers (music/programs/favourites) retain their native
                # filter edit. Focus it; OK opens its own keyboard, Back returns.
                xbmc.executebuiltin('SetFocus(19)')
            else:
                xbmc.executebuiltin('Action(Filter,{})'.format(origin_window))

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if "select" in args:
        try:
            handle_select_mode()
        except Exception as e:
            dialog = xbmcgui.Dialog()
            xbmc.log(f"Select mode error: {str(e)}", level=xbmc.LOGERROR)
    elif "strm" in args:
        try:
            main()
        except Exception as e:
            dialog = xbmcgui.Dialog()
            dialog.ok("脚本出错", f"错误信息：{str(e)}")
            xbmc.log(f"Search script error: {str(e)}", level=xbmc.LOGERROR)
    else:
        sys.exit(0)
