# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import os
import sys
import re
import xml.etree.ElementTree as ET
import json
from urllib.parse import unquote

# ==================== 全局状态与辅助函数 (用于支持 library 参数) ====================
_SELECTED_FOLDER_PATH = None
_SELECTED_FOLDER_NAME = None

def get_item_folder_path():
    """获取当前项的文件夹路径，优先使用通过 library 参数选择的路径"""
    global _SELECTED_FOLDER_PATH
    if _SELECTED_FOLDER_PATH:
        return _SELECTED_FOLDER_PATH
    return xbmc.getInfoLabel('ListItem.FolderPath')

def get_item_folder_name():
    """获取当前项的文件夹名称"""
    global _SELECTED_FOLDER_NAME
    if _SELECTED_FOLDER_NAME:
        return _SELECTED_FOLDER_NAME
    path = get_item_folder_path()
    return os.path.basename(path.rstrip(os.sep)) if path else ""

def is_item_folder():
    """判断当前项是否为文件夹，优先使用全局状态"""
    global _SELECTED_FOLDER_PATH
    if _SELECTED_FOLDER_PATH:
        return True  # 通过 browse 选择的必然是文件夹
    return xbmc.getCondVisibility('ListItem.IsFolder')

# ==================== 平台感知的路径规范化 ====================
def normalize_path(path):
    """根据当前平台规范化路径，使用正确的分隔符并以分隔符结尾"""
    if not path:
        return path
    sep = os.sep  # Windows: '\', Linux/Android: '/'
    # 统一替换分隔符
    if sep == '\\':
        path = path.replace('/', '\\')
        # 清理多余的双反斜杠
        while '\\\\' in path:
            path = path.replace('\\\\', '\\')
    else:
        path = path.replace('\\', '/')
    # 确保以分隔符结尾
    if not path.endswith(sep):
        path += sep
    return path

# ==================== 原有辅助函数 ====================
def get_database_path():
    userdata_path = xbmcvfs.translatePath('special://userdata/')
    db_path = os.path.join(userdata_path, 'Database', 'MyVideos131.db')
    return db_path

def get_next_id_path(cursor):
    cursor.execute("SELECT MAX(idPath) FROM path")
    result = cursor.fetchone()
    if result[0] is not None:
        return result[0] + 1
    else:
        return 1

def wait_for_progress_dialog():
    xbmc.sleep(2000)
    while xbmc.getCondVisibility('Window.IsVisible(extendedprogressdialog)'):
        xbmc.sleep(500)

# 20GB 阈值 (字节)
SIZE_THRESHOLD = 20 * 1024 * 1024 * 1024

def check_use_folder_names(folder_path):
    try:
        files = xbmcvfs.listdir(folder_path)
        file_list = files[1]
        dir_list = files[0]
        
        # 检查文件
        for filename in file_list:
            # 构建完整路径以检查大小
            full_file_path = os.path.join(folder_path, filename)
            if is_episode_filename(full_file_path):
                return True
                
        # 检查目录
        for dirname in dir_list:
            if is_season_foldername(dirname):
                return True
        return False
    except Exception as e:
        xbmc.log(f"检查文件夹命名规则失败: {str(e)}", xbmc.LOGERROR)
        return False

def get_stack_videos_setting():
    userdata_path = xbmcvfs.translatePath('special://userdata/')
    settings_file = os.path.join(userdata_path, 'guisettings.xml')
    if not xbmcvfs.exists(settings_file):
        return None
    try:
        with xbmcvfs.File(settings_file, 'r') as f:
            content = f.read()
        if not content:
            return None
        root = ET.fromstring(content)
        for setting in root.iter('setting'):
            if setting.get('id') == 'myvideos.stackvideos':
                return setting.text.strip().lower() if setting.text else None
    except Exception as e:
        xbmc.log(f"读取 guisettings.xml 失败: {str(e)}", xbmc.LOGERROR)
    return None

def execute_json_rpc(method, params):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(payload))

# ==================== 正则表达式预编译 ====================
RE_EP = re.compile(r'[eE][pP]?\s*\d+', re.IGNORECASE)
RE_CN_EP = re.compile(r'第\s*\d+\s*集', re.IGNORECASE)
RE_SEASON = re.compile(r'^season\s*\d+', re.IGNORECASE)
RE_S = re.compile(r'^[sS]\s*\d+', re.IGNORECASE)
# 新增：匹配中文季文件夹，如 "1季", "第一季", "十二季", "10季" 等
# [\u4e00-\u9fa5]+ 匹配汉字数字, \d+ 匹配阿拉伯数字
RE_CN_SEASON = re.compile(r'^(\d+|[\u4e00-\u9fa5]+)\s*季', re.IGNORECASE)

def is_episode_filename(filepath):
    """
    判断是否为单集文件。
    1. 检查文件名是否包含剧集标识。
    2. 如果包含，检查文件大小。如果 > 20GB，视为电影（误判保护），返回 False。
    """
    filename = os.path.basename(filepath)
    
    # 第一步：正则匹配
    if not (RE_EP.search(filename) or RE_CN_EP.search(filename)):
        return False
        
    # 第二步：大小检查 (防误判)
    try:
        # 使用 xbmcvfs.File 获取文件大小，兼容性更好
        # 注意：xbmcvfs.File 需要在上下文管理器中使用或直接调用 size()
        vf = xbmcvfs.File(filepath)
        file_size = vf.size()
        vf.close()
        
        if file_size > SIZE_THRESHOLD:
            xbmc.log(f"[SmartScan] File '{filename}' matches episode pattern but is too large ({file_size} bytes). Treating as non-episode.", xbmc.LOGDEBUG)
            return False
    except Exception as e:
        # 如果无法获取大小（例如文件被锁定、权限问题或虚拟文件系统不支持），
        # 记录警告但不再抛出异常导致崩溃。
        # 策略：既然名字像剧集，且无法确认它很大，我们保守地认为它是剧集。
        xbmc.log(f"[SmartScan] Could not get file size for '{filename}': {e}", xbmc.LOGWARNING)
        pass
        
    return True

def is_season_foldername(dirname):
    """
    判断是否为季文件夹。
    支持: Season 1, S1, 1季, 第一季
    """
    return bool(RE_SEASON.match(dirname) or RE_S.match(dirname) or RE_CN_SEASON.match(dirname))

# ==================== 核心数据库操作辅助函数 (不包含UpdateLibrary) ====================
def update_path_db_for_tvshow(folder_path, use_folder_names_val):
    """仅更新数据库path表为tvshows，不触发扫描"""
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    folder_path = normalize_path(folder_path)
    
    cursor.execute("SELECT idPath FROM path WHERE strPath=?", (folder_path,))
    res = cursor.fetchone()
    if res:
        cursor.execute(
            "UPDATE path SET strContent='tvshows', strScraper='metadata.tvshows.tmdb.cn.optimization', scanRecursive=2147483647, useFolderNames=? WHERE idPath=?",
            (use_folder_names_val, res[0])
        )
    else:
        next_id = get_next_id_path(cursor)
        cursor.execute(
            "INSERT INTO path (idPath, strPath, strContent, strScraper, scanRecursive, useFolderNames) VALUES (?,?,?,?,?,?)",
            (next_id, folder_path, 'tvshows', 'metadata.tvshows.tmdb.cn.optimization', 2147483647, use_folder_names_val)
        )
    conn.commit()
    conn.close()

def update_path_db_for_movie(folder_path):
    """仅更新数据库path表为movies，不触发扫描"""
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    folder_path = normalize_path(folder_path)
    
    cursor.execute("SELECT idPath FROM path WHERE strPath=?", (folder_path,))
    res = cursor.fetchone()
    if res:
        cursor.execute(
            "UPDATE path SET strContent='movies', strScraper='metadata.tmdb.cn.optimization', scanRecursive=2147483647, useFolderNames=0 WHERE idPath=?",
            (res[0],)
        )
    else:
        next_id = get_next_id_path(cursor)
        cursor.execute(
            "INSERT INTO path (idPath, strPath, strContent, strScraper, scanRecursive, useFolderNames) VALUES (?,?,?,?,?,?)",
            (next_id, folder_path, 'movies', 'metadata.tmdb.cn.optimization', 2147483647, 0)
        )
    conn.commit()
    conn.close()

# ==================== 原有的完整扫描函数 (用于情况1和部分情况2的最终步骤) ====================
def update_and_scan_tv(folder_path):
    """完整的TV扫描：更新DB + UpdateLibrary + 等待 + 返回增量"""
    folder_path = normalize_path(folder_path)
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tvshow")
    tv_before = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM episode")
    ep_before = cursor.fetchone()[0]
    conn.close()

    use_folder = 1 if check_use_folder_names(folder_path) else 0
    
    # 更新DB
    update_path_db_for_tvshow(folder_path, use_folder)

    xbmc.executebuiltin(f'UpdateLibrary(video,{folder_path})')
    wait_for_progress_dialog()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tvshow")
    tv_after = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM episode")
    ep_after = cursor.fetchone()[0]
    conn.close()
    return tv_after - tv_before, ep_after - ep_before

def update_and_scan_movie(folder_path):
    """完整的Movie扫描：更新DB + UpdateLibrary + 等待 + 返回增量"""
    folder_path = normalize_path(folder_path)
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movie")
    movie_before = cursor.fetchone()[0]
    conn.close()

    # 更新DB
    update_path_db_for_movie(folder_path)

    xbmc.executebuiltin(f'UpdateLibrary(video,{folder_path})')
    wait_for_progress_dialog()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movie")
    movie_after = cursor.fetchone()[0]
    conn.close()
    return movie_after - movie_before

# ==================== 目录树生成逻辑 ====================
def build_subtree(path):
    """递归构建子树，不涉及进度条更新"""
    path = normalize_path(path)
    node = {
        "path": path,
        "name": os.path.basename(path.rstrip(os.sep)),
        "has_episodes": False,
        "has_seasons": False,
        "children": []
    }
    try:
        dirs, files = xbmcvfs.listdir(path)
    except:
        return node
        
    for f in files:
        full_file_path = os.path.join(path, f)
        if is_episode_filename(full_file_path):
            node["has_episodes"] = True
            break
            
    for d in dirs:
        if is_season_foldername(d):
            node["has_seasons"] = True
            break
            
    for d in dirs:
        sub_path = os.path.join(path, d)
        child_node = build_subtree(sub_path)
        node["children"].append(child_node)
        
    return node

# ==================== 智能识别主函数 (重写) ====================
def process_smart_scanning():
    is_folder = is_item_folder()
    
    # 获取初始数据库状态，用于最终统计
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tvshow")
    tv_initial = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM episode")
    ep_initial = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM movie")
    movie_initial = cursor.fetchone()[0]
    conn.close()

    # ---------- 情况1：选中文件 ----------
    if not is_folder:
        file_path = get_item_folder_path()
        filename = os.path.basename(file_path)
        
        if not is_episode_filename(file_path):
            # 不包含剧集标识，按电影处理
            process_movie_scanning()
        else:
            # 包含剧集标识
            parent_dir = normalize_path(os.path.dirname(file_path))
            grandparent_dir = normalize_path(os.path.dirname(parent_dir.rstrip(os.sep)))
            parent_name = os.path.basename(parent_dir.rstrip(os.sep))
            
            if is_season_foldername(parent_name):
                target = grandparent_dir
            else:
                target = parent_dir
            
            # 执行剧集扫描
            added_tv, added_ep = update_and_scan_tv(target)
            xbmcgui.Dialog().ok("剧集扫描完成", f"新增剧集 {added_tv} 部，新增单集 {added_ep} 集")
        return

    # ---------- 情况2：选中文件夹 ----------
    root_path = normalize_path(get_item_folder_path())
    root_name = os.path.basename(root_path.rstrip(os.sep))
    
    # 情况2.1：总文件夹名称是 Season/S/季 形式
    if is_season_foldername(root_name):
        # 获取上一级文件夹路径
        parent_path = normalize_path(os.path.dirname(root_path.rstrip(os.sep)))
        
        # 直接执行“以剧集类别扫描海报”的完整逻辑，但针对 parent_path
        db_path = get_database_path()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 1. 更新数据库
            use_folder_names_val = 1 if check_use_folder_names(parent_path) else 0
            cursor.execute("SELECT idPath, strContent, strScraper FROM path WHERE strPath=?", (parent_path,))
            result = cursor.fetchone()
            
            if result:
                path_id = result[0]
                cursor.execute(
                    "UPDATE path SET strContent='tvshows', strScraper='metadata.tvshows.tmdb.cn.optimization', scanRecursive=2147483647, useFolderNames=? WHERE idPath=?",
                    (use_folder_names_val, path_id)
                )
                conn.commit()
            else:
                next_id = get_next_id_path(cursor)
                cursor.execute(
                    "INSERT INTO path (idPath, strPath, strContent, strScraper, scanRecursive, useFolderNames) VALUES (?, ?, ?, ?, ?, ?)",
                    (next_id, parent_path, 'tvshows', 'metadata.tvshows.tmdb.cn.optimization', 2147483647, use_folder_names_val)
                )
                conn.commit()
            
            # 2. 记录扫描前数量
            cursor.execute("SELECT COUNT(*) FROM tvshow")
            initial_tvshow_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM episode")
            initial_episode_count = cursor.fetchone()[0]
            
            # 3. 执行扫描
            xbmc.executebuiltin(f'UpdateLibrary(video,{parent_path})')
            wait_for_progress_dialog()
            
            # 4. 记录扫描后数量并弹窗
            cursor.execute("SELECT COUNT(*) FROM tvshow")
            final_tvshow_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM episode")
            final_episode_count = cursor.fetchone()[0]
            
            new_tvshows_count = final_tvshow_count - initial_tvshow_count
            new_episodes_count = final_episode_count - initial_episode_count
            
            conn.close()
            xbmcgui.Dialog().ok("扫描完成", f"本次扫描新增剧集{new_tvshows_count}部，新增单集{new_episodes_count}集！")
            
        except Exception as e:
            xbmc.log(f"电视剧扫描数据库操作失败: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "数据库操作失败")
        
        return

    # 情况2.2：总文件夹名称不是 Season/S/季 形式
    # 1. 生成目录树
    autotype_path = os.path.join(xbmcvfs.translatePath('special://userdata/addon_data/skin.yoplayer.infuse'), 'autotype.json')
    # 确保目录存在
    addon_data_dir = xbmcvfs.translatePath('special://userdata/addon_data/skin.yoplayer.infuse')
    if not xbmcvfs.exists(addon_data_dir):
        xbmcvfs.mkdirs(addon_data_dir)

    # 获取根目录的一级子项数量，用于进度条分母
    try:
        root_dirs, root_files = xbmcvfs.listdir(root_path)
        total_primary_items = len(root_dirs) + len(root_files)
    except:
        total_primary_items = 0

    progress = xbmcgui.DialogProgress()
    progress.create("智能分类处理", "正在自动分类处理文件...")
    
    # 构建完整的树结构
    full_tree = {
        "path": root_path,
        "name": root_name,
        "has_episodes": False,
        "has_seasons": False,
        "children": []
    }
    
    # 检查根目录自身属性
    for f in root_files:
        full_file_path = os.path.join(root_path, f)
        if is_episode_filename(full_file_path):
            full_tree["has_episodes"] = True
            break
    for d in root_dirs:
        if is_season_foldername(d):
            full_tree["has_seasons"] = True
            break

    processed_count = 0
    
    # 遍历一级子项
    all_primary_items = []
    for d in root_dirs:
        all_primary_items.append(('dir', d))
    for f in root_files:
        all_primary_items.append(('file', f))
        
    for item_type, item_name in all_primary_items:
        item_path = os.path.join(root_path, item_name)
        
        # 构建子树
        if item_type == 'dir':
            subtree = build_subtree(item_path)
            full_tree["children"].append(subtree)
        # 文件不需要子树，但为了进度条计数，我们依然遍历它
        
        processed_count += 1
        pct = int(processed_count / total_primary_items * 100) if total_primary_items > 0 else 100
        status_msg = f"{item_name}\n[{processed_count}/{total_primary_items}]"
        progress.update(pct, status_msg)
        
    # 保存 JSON
    try:
        with open(autotype_path, 'w', encoding='utf-8') as f:
            json.dump(full_tree, f, ensure_ascii=False, indent=2)
    except Exception as e:
        xbmc.log(f"Failed to write autotype.json: {e}", xbmc.LOGERROR)
        progress.close()
        xbmcgui.Dialog().ok("错误", "无法生成目录树文件")
        return

    progress.close()

    # 2. 读取目录树并处理
    try:
        with open(autotype_path, 'r', encoding='utf-8') as f:
            tree_data = json.load(f)
    except Exception as e:
        xbmcgui.Dialog().ok("错误", "无法读取目录树文件")
        return

    # 递归处理逻辑
    def process_tree_node_with_parent_context(node, parent_has_seasons):
        current_path = node["path"]
        has_seasons = node["has_seasons"]
        has_episodes = node["has_episodes"]
        
        if has_seasons:
            # 情况2.2.1
            use_folder_names_val = 1 if check_use_folder_names(current_path) else 0
            update_path_db_for_tvshow(current_path, use_folder_names_val)
            # 跳过子节点
            return 
        
        if has_episodes:
            if parent_has_seasons:
                # 按照情况2.2.1处理
                use_folder_names_val = 1 if check_use_folder_names(current_path) else 0
                update_path_db_for_tvshow(current_path, use_folder_names_val)
                # 跳过子节点
                return
            else:
                # 情况2.2.2: 上级无seasons
                use_folder_names_val = 1 if check_use_folder_names(current_path) else 0
                update_path_db_for_tvshow(current_path, use_folder_names_val)
                # 继续检查子节点
        
        # 递归子节点
        for child in node.get("children", []):
            process_tree_node_with_parent_context(child, has_seasons)

    # 启动处理
    process_tree_node_with_parent_context(tree_data, False)

    # 3. 所有文件夹检查完毕后，根据总文件夹的特征执行相应的扫描逻辑
    # 修复Bug：如果总文件夹直接包含剧集文件或季文件夹，则执行剧集扫描；否则执行电影扫描
    if tree_data.get("has_episodes") or tree_data.get("has_seasons"):
        update_and_scan_tv(root_path)
    else:
        update_and_scan_movie(root_path)
    
    # 4. 统计最终结果
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tvshow")
    tv_final = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM episode")
    ep_final = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM movie")
    movie_final = cursor.fetchone()[0]
    conn.close()
    
    # 计算增量
    delta_tv = tv_final - tv_initial
    delta_ep = ep_final - ep_initial
    delta_movie = movie_final - movie_initial
    
    msg = f"本次扫描新增电影 {delta_movie} 部，新增剧集 {delta_tv} 部，新增单集 {delta_ep} 集！"
    xbmcgui.Dialog().ok("扫描完成", msg)


# ==================== 原有处理函数（保持不变，供情况1调用） ====================
def process_movie_scanning():
    is_folder = is_item_folder()
    if is_folder:
        folder_path = normalize_path(get_item_folder_path())
        db_path = get_database_path()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT idPath, strContent, strScraper FROM path WHERE strPath=?", (folder_path,))
            result = cursor.fetchone()
            if result:
                cursor.execute(
                    "UPDATE path SET strContent='movies', strScraper='metadata.tmdb.cn.optimization', scanRecursive=2147483647, useFolderNames=0 WHERE idPath=?",
                    (result[0],)
                )
                conn.commit()
                cursor.execute("SELECT COUNT(*) FROM movie")
                initial_movie_count = cursor.fetchone()[0]
                xbmc.executebuiltin(f'UpdateLibrary(video,{folder_path})')
                wait_for_progress_dialog()
                cursor.execute("SELECT COUNT(*) FROM movie")
                final_movie_count = cursor.fetchone()[0]
                new_movies_count = final_movie_count - initial_movie_count
                xbmcgui.Dialog().ok("扫描完成", f"本次扫描新增电影{new_movies_count}部！")
            else:
                next_id = get_next_id_path(cursor)
                cursor.execute(
                    "INSERT INTO path (idPath, strPath, strContent, strScraper, scanRecursive, useFolderNames) VALUES (?, ?, ?, ?, ?, ?)",
                    (next_id, folder_path, 'movies', 'metadata.tmdb.cn.optimization', 2147483647, 0)
                )
                conn.commit()
                cursor.execute("SELECT COUNT(*) FROM movie")
                initial_movie_count = cursor.fetchone()[0]
                xbmc.executebuiltin(f'UpdateLibrary(video,{folder_path})')
                wait_for_progress_dialog()
                cursor.execute("SELECT COUNT(*) FROM movie")
                final_movie_count = cursor.fetchone()[0]
                new_movies_count = final_movie_count - initial_movie_count
                xbmcgui.Dialog().ok("扫描完成", f"本次扫描新增电影{new_movies_count}部！")
            conn.close()
        except Exception as e:
            xbmc.log(f"数据库操作失败: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "数据库操作失败")
    else:
        file_path = get_item_folder_path()
        directory_path = normalize_path(os.path.dirname(file_path))
        db_path = get_database_path()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT idPath, strContent, strScraper, useFolderNames FROM path WHERE strPath=?", (directory_path,))
            result = cursor.fetchone()
            if result:
                cursor.execute(
                    "UPDATE path SET strContent='movies', strScraper='metadata.tmdb.cn.optimization', scanRecursive=2147483647, useFolderNames=0 WHERE idPath=?",
                    (result[0],)
                )
                conn.commit()
                xbmc.executebuiltin('Dialog.Close(all,true)')
                xbmc.executebuiltin('Skin.SetString(strmhide,1)')
                if xbmc.getCondVisibility('Skin.HasSetting(simpletmdb)'):
                    xbmc.sleep(300)
                    xbmc.executebuiltin('Action(ContextMenu)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('setfocus(6001)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(up)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Skin.SetString(strmhide,"")')
                else:
                    xbmc.sleep(300)
                    xbmc.executebuiltin('Action(ContextMenu)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('setfocus(6000)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(up)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Skin.SetString(strmhide,"")')
            else:
                next_id = get_next_id_path(cursor)
                cursor.execute(
                    "INSERT INTO path (idPath, strPath, strContent, strScraper, scanRecursive, useFolderNames) VALUES (?, ?, ?, ?, ?, ?)",
                    (next_id, directory_path, 'movies', 'metadata.tmdb.cn.optimization', 2147483647, 0)
                )
                conn.commit()
                xbmc.executebuiltin('Dialog.Close(all,true)')
                xbmc.executebuiltin('Skin.SetString(strmhide,1)')
                if xbmc.getCondVisibility('Skin.HasSetting(simpletmdb)'):
                    xbmc.sleep(300)
                    xbmc.executebuiltin('Action(ContextMenu)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('setfocus(6000)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(up)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(up)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Skin.SetString(strmhide,"")')
                else:
                    xbmc.sleep(300)
                    xbmc.executebuiltin('Action(ContextMenu)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('setfocus(6000)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(up)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Action(select)')
                    xbmc.sleep(200)
                    xbmc.executebuiltin('Skin.SetString(strmhide,"")')
            conn.close()
        except Exception as e:
            xbmc.log(f"数据库操作失败: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "数据库操作失败")

def process_tvshow_scanning():
    is_folder = is_item_folder()
    if not is_folder:
        xbmcgui.Dialog().ok("提示", "不支持单集文件扫描海报，请返回上级目录执行该操作！")
        show_main_menu()
        return
    folder_path = normalize_path(get_item_folder_path())
    db_path = get_database_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT idPath, strContent, strScraper FROM path WHERE strPath=?", (folder_path,))
        result = cursor.fetchone()
        use_folder_names_val = 1 if check_use_folder_names(folder_path) else 0
        if result:
            path_id = result[0]
            cursor.execute(
                "UPDATE path SET strContent='tvshows', strScraper='metadata.tvshows.tmdb.cn.optimization', scanRecursive=2147483647, useFolderNames=? WHERE idPath=?",
                (use_folder_names_val, path_id)
            )
            conn.commit()
        else:
            next_id = get_next_id_path(cursor)
            cursor.execute(
                "INSERT INTO path (idPath, strPath, strContent, strScraper, scanRecursive, useFolderNames) VALUES (?, ?, ?, ?, ?, ?)",
                (next_id, folder_path, 'tvshows', 'metadata.tvshows.tmdb.cn.optimization', 2147483647, use_folder_names_val)
            )
            conn.commit()
        cursor.execute("SELECT COUNT(*) FROM tvshow")
        initial_tvshow_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM episode")
        initial_episode_count = cursor.fetchone()[0]
        xbmc.executebuiltin(f'UpdateLibrary(video,{folder_path})')
        wait_for_progress_dialog()
        cursor.execute("SELECT COUNT(*) FROM tvshow")
        final_tvshow_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM episode")
        final_episode_count = cursor.fetchone()[0]
        new_tvshows_count = final_tvshow_count - initial_tvshow_count
        new_episodes_count = final_episode_count - initial_episode_count
        xbmcgui.Dialog().ok("扫描完成", f"本次扫描新增剧集{new_tvshows_count}部，新增单集{new_episodes_count}集！")
        conn.close()
    except Exception as e:
        xbmc.log(f"电视剧扫描数据库操作失败: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", "数据库操作失败")

def check_folder_scan_status():
    xbmc.executebuiltin('RunScript(special://skin/scripts/foldertmdb.py)')

def manage_poster_data():
    folder_path = get_item_folder_path()
    xbmc.executebuiltin(f'RunScript(special://skin/scripts/checkdellib.py,folder)')

# ==================== 主菜单 ====================
def show_main_menu():
    is_folder = is_item_folder()
    dialog = xbmcgui.Dialog()
    if is_folder:
        options = [
            "智能识别类别扫描海报",
            "以电影类别扫描海报",
            "以剧集类别扫描海报",
            "规范化重命名文件/文件夹",
            "查看本文件夹扫描情况",
            "查看/删除已刮削海报数据"
        ]
    else:
        options = [
            "智能识别类别扫描海报",
            "以电影类别扫描海报",
            "以剧集类别扫描海报",
            "规范化重命名文件/文件夹"
        ]
    selected = dialog.select("请选择扫描类型", options)
    if selected == 0:
        process_smart_scanning()
    elif selected == 1:
        process_movie_scanning()
    elif selected == 2:
        process_tvshow_scanning()
    elif selected == 3:
        # 手动重命名文件/文件夹
        xbmc.executebuiltin('RunScript(special://skin/scripts/renametv.py)')
    elif selected == 4 and is_folder:
        check_folder_scan_status()
    elif selected == 5 and is_folder:
        manage_poster_data()
    else:
        return

# ==================== 入口逻辑（保持不变） ====================
def run_original_logic():
    show_main_menu()

def cleanup_and_exit():
    xbmc.executebuiltin('Skin.SetString(bdmvoff,"")')
    execute_json_rpc("Settings.SetSettingValue", {"setting": "myvideos.stackvideos", "value": False})

def set_manage_stack(value):
    """Checked setter for the temporary manage guard only."""
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc':'2.0', 'id':1, 'method':'Settings.SetSettingValue',
            'params':{'setting':'myvideos.stackvideos','value':value}})))
    except (ValueError, TypeError) as error:
        raise RuntimeError('无法确认视频堆叠设置是否写入成功') from error
    if not isinstance(response, dict) or 'error' in response or response.get('result') is not True:
        raise RuntimeError('Kodi 未接受视频堆叠设置')

def run_manage_preserving_settings():
    """Restore the actual pre-entry settings even when the menu cancels/errors."""
    previous_bdmv = xbmc.getInfoLabel('Skin.String(bdmvoff)')
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue',
            'params': {'setting': 'myvideos.stackvideos'}})))
        previous_stack = response['result']['value']
        if not isinstance(previous_stack, bool):
            raise ValueError('unexpected stackvideos value')
    except (ValueError, KeyError, TypeError):
        xbmcgui.Dialog().ok('操作未开始', '无法读取当前视频堆叠设置，未修改设置。请稍后重试。')
        return
    changed_bdmv = False
    changed_stack = False
    operation_error = None
    restore_errors = []
    try:
        if not previous_stack:
            if previous_bdmv != '1':
                changed_bdmv = True
                xbmc.executebuiltin('Skin.SetString(bdmvoff,1)')
            changed_stack = True
            set_manage_stack(True)
            xbmc.sleep(300)
            xbmc.executebuiltin('Container.Refresh')
        run_original_logic()
    except Exception as error:
        operation_error = error
    finally:
        # Attempt both restorations independently; one failure must not skip the
        # other. Keep the historical setting keys and scanning implementation.
        try:
            if changed_bdmv:
                xbmc.executebuiltin('Skin.SetString(bdmvoff,{})'.format(json.dumps(previous_bdmv,ensure_ascii=False)))
        except Exception as error:
            restore_errors.append('bdmvoff')
        try:
            if changed_stack:
                set_manage_stack(previous_stack)
        except Exception as error:
            restore_errors.append('myvideos.stackvideos')
    if restore_errors:
        xbmcgui.Dialog().ok('原设置未完全恢复', '请检查：{}。\n原 bdmvoff={}，原视频堆叠={}。'
                            .format('、'.join(restore_errors),previous_bdmv or '空',str(previous_stack).lower()))
        raise RuntimeError('管理操作后原设置未完全恢复：'+', '.join(restore_errors))
    if operation_error is not None:
        xbmcgui.Dialog().ok('操作未完成', '操作遇到错误，临时设置已恢复。请检查 Kodi 日志后重试。')
        raise operation_error

def main():
    global _SELECTED_FOLDER_PATH, _SELECTED_FOLDER_NAME
    
    if len(sys.argv) > 1 and sys.argv[1] == 'library':
        dialog = xbmcgui.Dialog()
        
        # 1. 弹出选择窗口，让用户选择来源类型
        source_options = [
            "从挂载网盘中选择",
            "从局域网NAS/SMB/NFS/webdav路径选择"
        ]
        source_selected = dialog.select("请选择文件夹来源", source_options)
        
        if source_selected == -1:
            return  # 用户取消了选择
            
        # 2. 根据选择打开对应的文件夹选择窗口
        selected_path = ""
        if source_selected == 0:
            # 从挂载网盘中选择，使用 'files' shares
            selected_path = dialog.browse(0, "请选择要扫描的文件夹", 'files', '', False, False)
        elif source_selected == 1:
            # 从局域网NAS/SMB/NFS/webdav路径选择，使用空 shares 以显示所有网络源
            selected_path = dialog.browse(0, "请选择要扫描的文件夹", '', '', False, False)
            
        if not selected_path:
            return  # 用户取消了文件夹选择
            
        # 3. 记录路径和截取最后一级文件夹名称
        _SELECTED_FOLDER_PATH = normalize_path(selected_path)
        _SELECTED_FOLDER_NAME = os.path.basename(_SELECTED_FOLDER_PATH.rstrip(os.sep))
        
        # 4. 弹出主选择窗口并执行后续逻辑
        show_main_menu()
        
    elif len(sys.argv) > 1 and sys.argv[1] == 'manage':
        run_manage_preserving_settings()
    else:
        pass

if __name__ == "__main__":
    main()
