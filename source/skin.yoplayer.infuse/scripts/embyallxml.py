# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import re
import json
import xml.etree.ElementTree as ET

# 定义常量
USERDATA_FAVOURITES = "special://userdata/favourites.xml"
ALL_XML_SUFFIX = "all.xml/"

def get_favourites_path():
    """获取 favourites.xml 的实际文件系统路径"""
    return xbmcvfs.translatePath(USERDATA_FAVOURITES)

def parse_favourites(filepath):
    """解析 favourites.xml 文件"""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        return tree, root
    except Exception as e:
        xbmc.log(f"[embyallxml] Error parsing XML: {str(e)}", xbmc.LOGERROR)
        return None, None

def extract_path_from_command(command_str):
    """从 ActivateWindow 命令中提取路径"""
    # 匹配 ActivateWindow(10025,"path",return) 或 ActivateWindow(10025,'path',return)
    match = re.search(r'ActivateWindow\s*\(\s*10025\s*,\s*["\']([^"\']+)["\']', command_str)
    if match:
        return match.group(1)
    return None

def is_folder_path(path):
    """简单判断是否为文件夹路径 (以 / 结尾)"""
    if not path:
        return False
    return path.endswith("/")

def add_favourite_via_jsonrpc(title, window_parameter, thumbnail):
    """
    通过 JSON-RPC 添加收藏夹项目
    注意: Kodi 的 Favourites.AddFavourite 主要用于添加新项目。
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "Favourites.AddFavourite",
        "params": {
            "title": title,
            "windowparameter": window_parameter,
            "type": "window",
            "thumbnail": thumbnail,
            "window": "Videos"
        },
        "id": 1
    }
    
    json_string = json.dumps(payload)
    response = xbmc.executeJSONRPC(json_string)
    
    # 可选：记录响应以便调试
    # xbmc.log(f"[embyallxml] AddFavourite Response for '{title}': {response}", xbmc.LOGDEBUG)
    
    # 简单检查是否包含错误关键字，实际使用中可能需要更复杂的解析
    if '"error"' in response.lower():
        xbmc.log(f"[embyallxml] Failed to add favourite: {title}. Response: {response}", xbmc.LOGWARNING)
        return False
    return True

def get_all_items(root):
    """获取所有 favourite 条目及其解析后的信息"""
    items = []
    for fav in root.findall('favourite'):
        name = fav.get('name', 'Unknown')
        thumb = fav.get('thumb', '')
        command = fav.text.strip() if fav.text else ""
        
        path = extract_path_from_command(command)
        # 只处理有效的文件夹路径
        if path and is_folder_path(path):
            items.append({
                'element': fav,
                'name': name,
                'path': path,
                'command': command,
                'thumb': thumb
            })
    return items

def process_add_logic(items, filter_func=None):
    """
    通用处理逻辑：添加 all.xml 变体
    filter_func: 用于筛选哪些项目需要处理的函数
    """
    modified_count = 0
    
    for item in items:
        # 如果提供了过滤函数，且当前项不满足条件，则跳过
        if filter_func and not filter_func(item):
            continue
            
        path = item['path']
        name = item['name']
        thumb = item['thumb']
        
        # 1. 添加原始路径的收藏 (根据需求描述)
        add_favourite_via_jsonrpc(name, path, thumb)
        
        # 2. 添加带有 all.xml/ 后缀的路径收藏
        new_path = path + ALL_XML_SUFFIX
        add_favourite_via_jsonrpc(name, new_path, thumb)
        
        modified_count += 1
        
    return modified_count

def process_remove_logic(items, filter_func=None):
    """
    通用处理逻辑：删除 all.xml 变体 (实际上是添加不带后缀的变体，根据需求描述)
    注意：需求描述中说“删除...则首先执行...AddFavourite(原路径)...再执行...AddFavourite(删除后缀后的路径)”
    这意味着对于以 all.xml/ 结尾的路径 P，我们要添加 P 和 P_without_suffix。
    """
    modified_count = 0
    
    for item in items:
        # 如果提供了过滤函数，且当前项不满足条件，则跳过
        if filter_func and not filter_func(item):
            continue
            
        path = item['path']
        name = item['name']
        thumb = item['thumb']
        
        # 计算删除后缀后的路径
        if path.endswith(ALL_XML_SUFFIX):
            clean_path = path[:-len(ALL_XML_SUFFIX)]
        else:
            clean_path = path # 理论上不会进入这里，因为filter会筛选

        # 1. 添加原始路径 (即带 all.xml/ 的那个，虽然名字可能让人困惑，但按需求执行)
        # 需求: "windowparameter": "视频文件或文件夹路径" (这里指原条目中的路径，即带all.xml的)
        add_favourite_via_jsonrpc(name, path, thumb)
        
        # 2. 添加删除后缀后的路径
        add_favourite_via_jsonrpc(name, clean_path, thumb)
        
        modified_count += 1
        
    return modified_count

def mode_add_all():
    """模式1：为所有分库路径添加“all.xml”"""
    filepath = get_favourites_path()
    tree, root = parse_favourites(filepath)
    if not root:
        return

    items = get_all_items(root)
    
    # 筛选条件：不是以 all.xml/ 结尾的
    def filter_add(item):
        return not item['path'].endswith(ALL_XML_SUFFIX)
        
    count = process_add_logic(items, filter_func=filter_add)
    
    dialog = xbmcgui.Dialog()
    dialog.ok("操作完成", f"已完成路径修改 {count} 个！")

def mode_remove_all():
    """模式2：删除所有分库路径的“all.xml”"""
    filepath = get_favourites_path()
    tree, root = parse_favourites(filepath)
    if not root:
        return

    items = get_all_items(root)
    
    # 筛选条件：是以 all.xml/ 结尾的
    def filter_remove(item):
        return item['path'].endswith(ALL_XML_SUFFIX)
        
    count = process_remove_logic(items, filter_func=filter_remove)
    
    dialog = xbmcgui.Dialog()
    dialog.ok("操作完成", f"已完成路径修改 {count} 个！")

def mode_select_add():
    """模式3：手动选择路径添加“all.xml”"""
    filepath = get_favourites_path()
    tree, root = parse_favourites(filepath)
    if not root:
        return

    items = get_all_items(root)
    
    # 候选项：不是以 all.xml/ 结尾的
    candidates = [item for item in items if not item['path'].endswith(ALL_XML_SUFFIX)]

    if not candidates:
        xbmcgui.Dialog().ok("提示", "所有文件夹路径已包含 all.xml/ 或没有符合条件的路径。")
        return

    # 构建选择列表
    select_list = [f"{item['name']} ({item['path']})" for item in candidates]
    
    dialog = xbmcgui.Dialog()
    selected_indices = dialog.multiselect("选择要添加 all.xml/ 的路径", select_list)

    if selected_indices:
        count = 0
        for index in selected_indices:
            item = candidates[index]
            path = item['path']
            name = item['name']
            thumb = item['thumb']
            
            # 执行添加逻辑
            add_favourite_via_jsonrpc(name, path, thumb)
            add_favourite_via_jsonrpc(name, path + ALL_XML_SUFFIX, thumb)
            count += 1
            
        dialog.ok("操作完成", f"已完成路径修改 {count} 个！")

def mode_select_remove():
    """模式4：手动选择路径删除“all.xml”"""
    filepath = get_favourites_path()
    tree, root = parse_favourites(filepath)
    if not root:
        return

    items = get_all_items(root)
    
    # 候选项：是以 all.xml/ 结尾的
    candidates = [item for item in items if item['path'].endswith(ALL_XML_SUFFIX)]

    if not candidates:
        xbmcgui.Dialog().ok("提示", "没有找到以 all.xml/ 结尾的路径。")
        return

    # 构建选择列表
    select_list = [f"{item['name']} ({item['path']})" for item in candidates]
    
    dialog = xbmcgui.Dialog()
    selected_indices = dialog.multiselect("选择要删除 all.xml/ 的路径", select_list)

    if selected_indices:
        count = 0
        for index in selected_indices:
            item = candidates[index]
            path = item['path']
            name = item['name']
            thumb = item['thumb']
            
            # 计算清理后的路径
            clean_path = path[:-len(ALL_XML_SUFFIX)]
            
            # 执行添加逻辑 (根据需求描述)
            add_favourite_via_jsonrpc(name, path, thumb)
            add_favourite_via_jsonrpc(name, clean_path, thumb)
            count += 1
            
        dialog.ok("操作完成", f"已完成路径修改 {count} 个！")

def main():
    # 主菜单选项
    options = [
        "为所有分库路径添加“all.xml”",
        "删除所有分库路径的“all.xml”",
        "手动选择路径添加“all.xml”(可多选)",
        "手动选择路径删除“all.xml”(可多选)"
    ]
    
    dialog = xbmcgui.Dialog()
    index = dialog.select("请选择操作模式", options)
    
    if index == -1:
        return # 用户取消
    
    if index == 0:
        mode_add_all()
    elif index == 1:
        mode_remove_all()
    elif index == 2:
        mode_select_add()
    elif index == 3:
        mode_select_remove()

if __name__ == '__main__':
    main()