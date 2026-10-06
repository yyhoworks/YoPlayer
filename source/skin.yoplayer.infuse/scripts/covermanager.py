import xbmc
import xbmcgui
import xbmcvfs
import json
import os
import time
import xml.etree.ElementTree as ET
import sys
import urllib.parse

# 常量定义
FAVOURITES_PATH = "special://userdata/favourites.xml"
THUMB_DIR = "special://userdata/Thumbnails/favthumb/"
SKIN_STRING_NAME = "favcover"
SCRIPT_FAVCOVER = "special://skin/scripts/favcover.py"
SCRIPT_FAVTHUMB = "special://skin/scripts/favthumb.py"

def log(msg):
    xbmc.log(f"[NewCoverScript] {msg}", level=xbmc.LOGINFO)

def get_skin_string():
    """获取当前Skin.String(favcover)的值"""
    return xbmc.getInfoLabel(f"Skin.String({SKIN_STRING_NAME})")

def execute_json_rpc(method, params):
    """执行JSON-RPC请求"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    json_payload = json.dumps(payload)
    response = xbmc.executeJSONRPC(json_payload)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        log(f"Failed to parse JSON response: {response}")
        return None

def parse_favourites():
    """解析favourites.xml，返回条目列表"""
    favourites = []
    # 修复：使用 xbmcvfs.translatePath 替代 xbmc.translatePath
    path = xbmcvfs.translatePath(FAVOURITES_PATH)
    
    if not xbmcvfs.exists(path):
        log("favourites.xml not found")
        return favourites

    try:
        # xbmcvfs.File 可以直接用于 ET.parse
        tree = ET.parse(xbmcvfs.File(path))
        root = tree.getroot()
        
        for fav in root.findall('favourite'):
            name = fav.get('name', '')
            thumb = fav.get('thumb', '')
            # 提取 ActivateWindow 中的路径
            # 格式: ActivateWindow(10025,"path",return)
            action = fav.text.strip() if fav.text else ""
            
            path_val = ""
            if action.startswith("ActivateWindow"):
                # 简单正则或字符串处理提取路径
                # 假设格式固定: ActivateWindow(10025,"path",return)
                start_idx = action.find('"')
                end_idx = action.rfind('"')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    path_val = action[start_idx+1:end_idx]
            
            if name and path_val:
                favourites.append({
                    'name': name,
                    'path': path_val,
                    'thumb': thumb
                })
    except Exception as e:
        log(f"Error parsing favourites.xml: {str(e)}")
        
    return favourites

def check_thumb_exists(thumb_path):
    """检查封面图文件是否存在"""
    if not thumb_path:
        return False
    # 修复：使用 xbmcvfs.translatePath
    translated_path = xbmcvfs.translatePath(thumb_path)
    return xbmcvfs.exists(translated_path)

def update_favourite_entry(name, path, old_thumb, new_thumb_rel):
    """
    更新收藏夹条目的缩略图
    """
    new_thumb_full = f"special://userdata/Thumbnails/favthumb/{new_thumb_rel}"
    
    # 第一次调用：带原封面图路径
    params1 = {
        "title": name,
        "windowparameter": path,
        "type": "window",
        "thumbnail": old_thumb if old_thumb else "",
        "window": "Videos"
    }
    log(f"Updating favourite (step 1): {name}")
    execute_json_rpc("Favourites.AddFavourite", params1)
    
    # 第二次调用：带新封面图路径
    params2 = {
        "title": name,
        "windowparameter": path,
        "type": "window",
        "thumbnail": new_thumb_full,
        "window": "Videos"
    }
    log(f"Updating favourite (step 2): {name} with new thumb {new_thumb_full}")
    execute_json_rpc("Favourites.AddFavourite", params2)

def wait_for_skin_string_change(initial_value, timeout=60):
    """
    等待Skin.String(favcover)发生变化
    返回新的值，如果超时则返回None
    """
    start_time = time.time()
    current_value = initial_value
    
    while time.time() - start_time < timeout:
        new_value = get_skin_string()
        if new_value != current_value and new_value != "":
            log(f"Skin string changed from '{initial_value}' to '{new_value}'")
            return new_value
        time.sleep(0.5) # 每0.5秒检查一次
        
    log("Timeout waiting for skin string change")
    return None

def process_single_favourite(fav_item):
    """处理单个收藏夹条目的封面生成"""
    name = fav_item['name']
    path = fav_item['path']
    old_thumb = fav_item['thumb']
    
    initial_skin_val = get_skin_string()
    
    # 执行 favcover.py
    log(f"Running favcover.py for: {name}")
    # 注意：RunScript 参数中的引号处理，确保路径正确传递
    xbmc.executebuiltin(f'RunScript("{SCRIPT_FAVCOVER}","{name}","{path}")')
    
    # 等待皮肤变量变化
    new_skin_val = wait_for_skin_string_change(initial_skin_val)
    
    if new_skin_val:
        # 更新收藏夹
        update_favourite_entry(name, path, old_thumb, new_skin_val)
        return True
    else:
        log(f"Failed to generate cover for {name}: Skin string did not change.")
        return False

def delete_all_thumbs():
    """删除所有封面图及残留文件"""
    # 修复：使用 xbmcvfs.translatePath
    thumb_dir_path = xbmcvfs.translatePath(THUMB_DIR)
    count = 0
    if xbmcvfs.exists(thumb_dir_path):
        # 列出目录内容
        dirs, files = xbmcvfs.listdir(thumb_dir_path)
        for file in files:
            file_path = os.path.join(thumb_dir_path, file)
            if xbmcvfs.delete(file_path):
                count += 1
            else:
                log(f"Failed to delete {file_path}")
        
    return count

# --- 新增: Simple Mode Logic ---

def handle_simple_mode():
    """
    当带有 simple 参数运行时执行此逻辑
    """
    log("Starting Simple Mode execution")
    
    # 1. 获取当前 ListItem 信息
    label = xbmc.getInfoLabel("ListItem.Label")
    filename_and_path = xbmc.getInfoLabel("ListItem.FileNameAndPath")
    
    log(f"Simple Mode - Label: {label}")
    log(f"Simple Mode - FileNameAndPath (Raw): {filename_and_path}")
    
    if not label or not filename_and_path:
        log("Simple Mode aborted: Missing Label or Path")
        xbmcgui.Dialog().ok("提示", "未获取到有效的ListItem信息！")
        return

    # 2. 解码 FileNameAndPath 并提取目标路径
    # 格式类似: favourites://ActivateWindow(10025,"folder_path",return)
    decoded_path = urllib.parse.unquote(filename_and_path)
    log(f"Simple Mode - Decoded Path: {decoded_path}")
    
    target_folder_path = ""
    if "ActivateWindow" in decoded_path:
        start_idx = decoded_path.find('"')
        end_idx = decoded_path.rfind('"')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            target_folder_path = decoded_path[start_idx+1:end_idx]
    
    if not target_folder_path:
        log("Simple Mode aborted: Could not extract folder path from decoded string")
        xbmcgui.Dialog().ok("提示", "无法从路径中提取有效的文件夹路径！")
        return
        
    log(f"Simple Mode - Extracted Target Folder: {target_folder_path}")

    # 3. 读取 favourites.xml 并筛选匹配条目
    all_favs = parse_favourites()
    matched_favs = []
    
    for fav in all_favs:
        # 匹配条件: name == label AND path == target_folder_path
        if fav['name'] == label and fav['path'] == target_folder_path:
            matched_favs.append(fav)
            
    if not matched_favs:
        log(f"Simple Mode aborted: No matching favourite found for Label='{label}' and Path='{target_folder_path}'")
        xbmcgui.Dialog().ok("提示", "未在收藏夹中找到匹配的条目！")
        return
        
    log(f"Simple Mode - Found {len(matched_favs)} matching entries.")

    # 4. 逐条执行操作并统计
    modified_count = 0
    
    for fav_item in matched_favs:
        name = fav_item['name']
        path = fav_item['path']
        old_thumb = fav_item['thumb']
        
        log(f"Processing match: {name}")
        
        # 记录当前的 skin string 状态，用于检测变化
        current_skin_before_run = get_skin_string()
        
        # 执行 RunScript
        log(f"Running favcover.py for: {name}")
        xbmc.executebuiltin(f'RunScript("{SCRIPT_FAVCOVER}","{name}","{path}")')
        
        # 监测 Skin.String(favcover) 是否变化
        new_skin_val = wait_for_skin_string_change(current_skin_before_run)
        
        if new_skin_val:
            log(f"Skin string updated to: {new_skin_val}")
            
            # 执行第一次 JSON-RPC：带原封面图路径
            params1 = {
                "title": name,
                "windowparameter": path,
                "type": "window",
                "thumbnail": old_thumb if old_thumb else "",
                "window": "Videos"
            }
            execute_json_rpc("Favourites.AddFavourite", params1)
            
            # 执行第二次 JSON-RPC：带新封面图路径
            new_thumb_full = f"special://userdata/Thumbnails/favthumb/{new_skin_val}"
            params2 = {
                "title": name,
                "windowparameter": path,
                "type": "window",
                "thumbnail": new_thumb_full,
                "window": "Videos"
            }
            execute_json_rpc("Favourites.AddFavourite", params2)
            
            modified_count += 1
        else:
            log(f"Warning: Skin string did not change for {name}, skipping update.")

    # 5. 弹出确认窗口并关闭
    xbmcgui.Dialog().ok("完成", f"已完成自动生成封面图 {modified_count} 个！")
    log("Simple Mode execution finished.")


# --- 主要逻辑函数 (原有逻辑) ---

def show_main_menu():
    """显示主选择窗口"""
    options = [
        "智能生成封面图",
        "选择封面图片文件夹匹配封面"
    ]
    
    dialog = xbmcgui.Dialog()
    select = dialog.select("主菜单", options)
    
    if select == 0:
        show_smart_generate_menu()
    elif select == 1:
        xbmc.executebuiltin(f'RunScript("{SCRIPT_FAVTHUMB}")')

def show_smart_generate_menu():
    """显示二级选择窗口：智能生成封面图"""
    options = [
        "选择分库生成封面图(可多选)",
        "全部分库自动生成封面图",
        "[COLOR red]删除所有封面图及其残余文件[/COLOR]"
    ]
    
    dialog = xbmcgui.Dialog()
    select = dialog.select("智能生成选项", options)
    
    if select == 0:
        handle_selective_generation()
    elif select == 1:
        handle_full_generation()
    elif select == 2:
        handle_delete_all()

def handle_selective_generation():
    """处理选择性生成"""
    favourites = parse_favourites()
    if not favourites:
        xbmcgui.Dialog().ok("提示", "未找到有效的收藏夹条目。")
        return
    
    # 构建选择列表
    items = []
    for fav in favourites:
        name = fav['name']
        has_thumb = check_thumb_exists(fav['thumb'])
        if has_thumb:
            label = f"{name} - [COLOR green]已有封面图[/COLOR]"
        else:
            label = f"{name} - [COLOR yellow]没有封面图[/COLOR]"
        items.append(label)
    
    dialog = xbmcgui.Dialog()
    # multiselect 返回选中项的索引列表
    selected_indices = dialog.multiselect("选择要生成封面的分库", items)
    
    if not selected_indices:
        return
    
    modified_count = 0
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create("正在生成封面", "处理中...")
    
    total = len(selected_indices)
    for idx, i in enumerate(selected_indices):
        if progress_dialog.iscanceled():
            break
        
        fav_item = favourites[i]
        progress_dialog.update(int((idx / total) * 100), f"正在处理: {fav_item['name']}")
        
        if process_single_favourite(fav_item):
            modified_count += 1
            
    progress_dialog.close()
    
    xbmcgui.Dialog().ok("完成", f"已完成自动生成封面图 {modified_count} 个！")

def handle_full_generation():
    """处理全部生成"""
    dialog = xbmcgui.Dialog()
    if not dialog.yesno("确认", "此操作会覆盖原有的封面图，是否继续？"):
        return
    
    favourites = parse_favourites()
    if not favourites:
        dialog.ok("提示", "未找到有效的收藏夹条目。")
        return
    
    modified_count = 0
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create("正在生成全部封面", "处理中...")
    
    total = len(favourites)
    for idx, fav_item in enumerate(favourites):
        if progress_dialog.iscanceled():
            break
        
        progress_dialog.update(int((idx / total) * 100), f"正在处理: {fav_item['name']}")
        
        if process_single_favourite(fav_item):
            modified_count += 1
            
    progress_dialog.close()
    
    dialog.ok("完成", f"已完成自动生成封面图 {modified_count} 个！")

def handle_delete_all():
    """处理删除所有封面"""
    dialog = xbmcgui.Dialog()
    if not dialog.yesno("确认", "此操作会删除所有分库的封面图，是否继续？"):
        return
    
    deleted_count = delete_all_thumbs()
    
    # 刷新皮肤以清除缓存引用
    xbmc.executebuiltin("ReloadSkin()")
    
    # 稍微等待一下让皮肤重载，虽然脚本可能随之终止，但对话框需要显示
    time.sleep(1) 
    
    dialog.ok("完成", "已删除全部封面图及残留文件！")

# 脚本入口
if __name__ == '__main__':
    # 检查是否带有 "simple" 参数
    # sys.argv 通常包含脚本路径作为第一个元素，后续为参数
    if len(sys.argv) > 1 and "simple" in sys.argv[1:]:
        handle_simple_mode()
    else:
        show_main_menu() 