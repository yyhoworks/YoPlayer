# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import json
import time
import re
import xml.etree.ElementTree as ET

# 路径定义
PLAYLIST_DIR = "special://userdata/playlists/video/"
FAVOURITES_FILE = "special://userdata/favourites.xml"

# 默认初始的 xsp 文件内容
DEFAULT_CONTENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<smartplaylist type="movies">
    <name>分库名称</name>
    <match>all</match>
</smartplaylist>"""

def get_timestamp_files():
    """获取目录下所有以14位年月日时分秒时间戳命名的 .xsp 文件"""
    if not xbmcvfs.exists(PLAYLIST_DIR):
        return []
    dirs, files = xbmcvfs.listdir(PLAYLIST_DIR)
    # 匹配 YYYYMMDDHHMMSS.xsp 格式 (14位数字 + .xsp)
    return sorted([f for f in files if re.match(r'^\d{14}\.xsp$', f)])

def read_file(filepath):
    """安全读取 special:// 路径下的文件"""
    f = xbmcvfs.File(filepath, 'r')
    content = f.read()
    f.close()
    if isinstance(content, bytes):
        content = content.decode('utf-8')
    return content

def write_file(filepath, content):
    """安全写入 special:// 路径下的文件"""
    f = xbmcvfs.File(filepath, 'w')
    if isinstance(content, str):
        content = content.encode('utf-8')
    f.write(content)
    f.close()

def get_name_from_xsp(filepath):
    """读取 xsp 文件中的 <name> 标签内容"""
    content = read_file(filepath)
    try:
        root = ET.fromstring(content)
        name_elem = root.find('name')
        if name_elem is not None and name_elem.text:
            return name_elem.text.strip()
    except ET.ParseError:
        pass
    return "分库名称"

def check_favourites_contains(filename):
    """检查 favourites.xml 是否包含指定的文件名"""
    if xbmcvfs.exists(FAVOURITES_FILE):
        content = read_file(FAVOURITES_FILE)
        return filename in content
    return False

def execute_add_favourite(filename, title):
    """执行 Favourites.AddFavourite JSON-RPC 请求"""
    request = {
        "jsonrpc": "2.0",
        "method": "Favourites.AddFavourite",
        "params": {
            "title": title,
            "windowparameter": f"special://profile/playlists/video/{filename}",
            "type": "window",
            "window": "Videos"
        },
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(request))

def wait_for_editor_close():
    """监测 SmartPlaylistEditor 窗口，当其不可见（被关闭）时返回"""
    while xbmc.getCondVisibility('Window.IsActive(SmartPlaylistEditor)'):
        xbmc.sleep(500)

def main():
    dialog = xbmcgui.Dialog()
    
    # 主菜单选项 (Kodi 颜色标签标准语法为 [COLOR color]...[/COLOR])
    options = [
        "新增筛选列表加入分库",
        "修改已建立的筛选列表",
        "删除已建立的筛选列表(可多选)",
        "[COLOR red]删除所有筛选列表[/COLOR]"
    ]
    
    choice = dialog.select("筛选列表管理", options)
    if choice == -1:
        return
        
    # ================= 选项 1：新增筛选列表加入分库 =================
    if choice == 0:
        # 获取当前年月日时分秒时间戳
        timestamp = time.strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}.xsp"
        filepath = f"{PLAYLIST_DIR}{filename}"
        
        # 写入默认内容
        write_file(filepath, DEFAULT_CONTENT)
        
        # 打开智能播放列表编辑器
        xbmc.executebuiltin(f'ActivateWindow(SmartPlaylistEditor,"{filepath}")')
        
        # 延时5秒
        xbmc.sleep(5000)
        
        # 开始监测编辑器窗口是否关闭
        wait_for_editor_close()
        
        # 窗口关闭后读取文件内容
        content = read_file(filepath)
        
        if content.strip() == DEFAULT_CONTENT.strip():
            # 如果内容未修改，删除文件并关闭
            xbmcvfs.delete(filepath)
        else:
            # 如果内容已修改，读取名称并添加到收藏
            name = get_name_from_xsp(filepath)
            execute_add_favourite(filename, name)

    # ================= 选项 2：修改已建立的筛选列表 =================
    elif choice == 1:
        files = get_timestamp_files()
        if not files:
            dialog.ok("提示", "当前没有已建立的筛选列表。")
            return
            
        # 构建选项显示内容：时间戳-名称
        display_options = []
        for f in files:
            ts = f.replace('.xsp', '')
            name = get_name_from_xsp(f"{PLAYLIST_DIR}{f}")
            display_options.append(f"{ts}-{name}")
            
        idx = dialog.select("选择要修改的筛选列表", display_options)
        if idx == -1:
            return
            
        filename = files[idx]
        filepath = f"{PLAYLIST_DIR}{filename}"
        
        # 打开编辑器
        xbmc.executebuiltin(f'ActivateWindow(SmartPlaylistEditor,"{filepath}")')
        
        # 检查 favourites.xml 是否已包含该文件
        if check_favourites_contains(filename):
            # 如果已包含，直接关闭脚本
            return
            
        # 如果不包含，延时5秒后监测窗口关闭
        xbmc.sleep(5000)
        wait_for_editor_close()
        
        content = read_file(filepath)
        if content.strip() == DEFAULT_CONTENT.strip():
            xbmcvfs.delete(filepath)
        else:
            name = get_name_from_xsp(filepath)
            execute_add_favourite(filename, name)

    # ================= 选项 3：删除已建立的筛选列表(可多选) =================
    elif choice == 2:
        files = get_timestamp_files()
        if not files:
            dialog.ok("提示", "当前没有可删除的筛选列表。")
            return
            
        # 构建选项显示内容：时间戳-名称
        display_options = []
        for f in files:
            ts = f.replace('.xsp', '')
            name = get_name_from_xsp(f"{PLAYLIST_DIR}{f}")
            display_options.append(f"{ts}-{name}")
            
        selected_indices = dialog.multiselect("选择要删除的筛选列表", display_options)
        if not selected_indices:
            return
            
        deleted_count = 0
        
        for idx in selected_indices:
            filename = files[idx]
            filepath = f"{PLAYLIST_DIR}{filename}"
            
            if not check_favourites_contains(filename):
                # 如果收藏中不包含，直接删除文件
                xbmcvfs.delete(filepath)
                deleted_count += 1
            else:
                # 如果收藏中包含，读取名称并执行指定指令，然后删除文件
                name = get_name_from_xsp(filepath)
                execute_add_favourite(filename, name)
                xbmcvfs.delete(filepath)
                deleted_count += 1
                
        dialog.ok("完成", f"已删除筛选列表{deleted_count}个！")

    # ================= 选项 4：删除所有筛选列表 =================
    elif choice == 3:
        confirm = dialog.yesno(
            "确认删除", 
            "该操作会删除所有筛选列表，并且不可恢复，选择“是”确认删除，选择“否”取消操作"
        )
        if not confirm:
            return
            
        files = get_timestamp_files()
        if not files:
            dialog.ok("提示", "当前没有可删除的筛选列表。")
            return
            
        deleted_count = 0
        
        for filename in files:
            filepath = f"{PLAYLIST_DIR}{filename}"
            
            if not check_favourites_contains(filename):
                xbmcvfs.delete(filepath)
                deleted_count += 1
            else:
                name = get_name_from_xsp(filepath)
                execute_add_favourite(filename, name)
                xbmcvfs.delete(filepath)
                deleted_count += 1
                
        dialog.ok("完成", f"已删除筛选列表{deleted_count}个！")

if __name__ == '__main__':
    main()