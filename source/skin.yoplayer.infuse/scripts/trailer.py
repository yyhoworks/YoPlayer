import xbmc
import xbmcgui
import xbmcvfs
import os
import time

def log(message):
    xbmc.log(f"[Trailer Script] {message}", xbmc.LOGINFO)

def get_skin_string(key):
    return xbmc.getInfoLabel(f"Skin.String({key})")

def set_skin_string(key, value):
    xbmc.executebuiltin(f"Skin.SetString({key},{value})")

def has_skin_setting(setting):
    return xbmc.getCondVisibility(f"Skin.HasSetting({setting})")

def get_listitem_info(info):
    return xbmc.getInfoLabel(f"ListItem.{info}")

def play_media(url):
    xbmc.executebuiltin(f"PlayMedia({url},1,noresume)")

def close_dialog(dialog_id):
    xbmc.executebuiltin(f"Dialog.Close({dialog_id})")

def is_video_file(filename):
    """判断是否为视频文件"""
    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.ts', '.iso', '.m2ts', '.vob', '.m2v', '.rmvb', '.asf', '.m3u8', '.mpd']
    _, ext = os.path.splitext(filename.lower())
    return ext in video_extensions

def should_check_filename(dbtype, listitem_filename, trailer_filename):
    """检查预告片文件名是否应包含列表项文件名"""
    if not dbtype or dbtype != 'movie':
        return True
    
    if not listitem_filename:
        return True
    
    # 提取列表项的文件名部分（不含扩展名）
    listitem_name_part = os.path.splitext(listitem_filename)[0]
    trailer_name_part = os.path.splitext(trailer_filename)[0]
    
    result = listitem_name_part.lower() in trailer_name_part.lower()
    log(f"文件名匹配检查: '{listitem_name_part}' in '{trailer_name_part}' = {result}")
    return result

def safe_listdir(path):
    """安全地列出目录内容，处理中文路径"""
    try:
        # 直接尝试列出，不预先检查路径存在性
        dirs, files = xbmcvfs.listdir(path)
        # 解码bytes对象
        decoded_dirs = []
        decoded_files = []
        
        for d in dirs:
            if isinstance(d, bytes):
                try:
                    decoded_dirs.append(d.decode('utf-8', errors='ignore'))
                except:
                    try:
                        decoded_dirs.append(d.decode('gbk', errors='ignore'))
                    except:
                        decoded_dirs.append(str(d))
            else:
                decoded_dirs.append(d)
        
        for f in files:
            if isinstance(f, bytes):
                try:
                    decoded_files.append(f.decode('utf-8', errors='ignore'))
                except:
                    try:
                        decoded_files.append(f.decode('gbk', errors='ignore'))
                    except:
                        decoded_files.append(str(f))
            else:
                decoded_files.append(f)
        
        return decoded_dirs, decoded_files
    except Exception as e:
        log(f"无法列出目录 '{path}': {e}")
        return [], []

def find_trailer_folder(base_path, search_order="current_parent"):
    """查找包含'trailer'或'预告'的文件夹"""
    log(f"在目录 '{base_path}' 中查找预告片文件夹")
    
    # 根据搜索顺序决定搜索路径列表
    if search_order == "current_parent":
        search_paths = [base_path, os.path.dirname(base_path)]
        search_names = ["项目本级目录", "上级目录"]
    else:  # current_child
        search_paths = [base_path, os.path.join(base_path)]
        search_names = ["项目本级目录", "下级目录"]
    
    for i, search_path in enumerate(search_paths):
        if i == 1 and search_order == "current_child":
            # 对于下级目录搜索，需要遍历当前目录的所有子目录
            dirs, _ = safe_listdir(base_path)
            for sub_dir in dirs:
                sub_path = os.path.join(base_path, sub_dir).replace('\\', '/')
                dirs_in_sub, files_in_sub = safe_listdir(sub_path)
                
                for item in dirs_in_sub:
                    if 'trailer' in item.lower() or '预告' in item:
                        folder_path = os.path.join(sub_path, item).replace('\\', '/')
                        log(f"在下级目录 '{sub_path}' 中找到匹配的文件夹: {folder_path}")
                        
                        # 检查该文件夹下是否有视频文件
                        sub_dirs, sub_files = safe_listdir(folder_path)
                        for file_item in sub_files:
                            if is_video_file(file_item):
                                full_path = os.path.join(folder_path, file_item).replace('\\', '/')
                                log(f"在预告片文件夹中找到视频文件: {full_path}")
                                return full_path
        else:
            # 当前目录或上级目录搜索
            dirs, files = safe_listdir(search_path)
            
            for item in dirs:
                if 'trailer' in item.lower() or '预告' in item:
                    folder_path = os.path.join(search_path, item).replace('\\', '/')
                    log(f"找到匹配的文件夹: {folder_path}")
                    
                    # 检查该文件夹下是否有视频文件
                    sub_dirs, sub_files = safe_listdir(folder_path)
                    for file_item in sub_files:
                        if is_video_file(file_item):
                            full_path = os.path.join(folder_path, file_item).replace('\\', '/')
                            log(f"在预告片文件夹中找到视频文件: {full_path}")
                            return full_path
    
    return None

def find_trailer_file(base_path, dbtype, filename, search_order="current_parent"):
    """查找包含'trailer'或'预告'的视频文件"""
    log(f"在目录 '{base_path}' 中查找预告片视频文件")
    
    # 根据搜索顺序决定搜索路径列表
    if search_order == "current_parent":
        search_paths = [base_path, os.path.dirname(base_path)]
        search_names = ["项目本级目录", "上级目录"]
    else:  # current_child
        search_paths = [base_path, base_path]  # 对于child，我们在当前目录及其子目录中搜索
        search_names = ["项目本级目录", "下级目录"]
    
    for i, search_path in enumerate(search_paths):
        if i == 1 and search_order == "current_child":
            # 对于下级目录搜索，需要遍历当前目录的所有子目录
            dirs, _ = safe_listdir(base_path)
            for sub_dir in dirs:
                sub_path = os.path.join(base_path, sub_dir).replace('\\', '/')
                dirs_in_sub, files_in_sub = safe_listdir(sub_path)
                
                for file_item in files_in_sub:
                    if is_video_file(file_item):
                        if 'trailer' in file_item.lower() or '预告' in file_item:
                            if should_check_filename(dbtype, filename, file_item):
                                full_path = os.path.join(sub_path, file_item).replace('\\', '/')
                                log(f"在下级目录中找到预告片文件: {full_path}")
                                return full_path
        else:
            # 当前目录或上级目录搜索
            dirs, files = safe_listdir(search_path)
            
            for file_item in files:
                if is_video_file(file_item):
                    if 'trailer' in file_item.lower() or '预告' in file_item:
                        if should_check_filename(dbtype, filename, file_item):
                            full_path = os.path.join(search_path, file_item).replace('\\', '/')
                            log(f"找到匹配的预告片文件: {full_path}")
                            return full_path
    
    return None

def get_project_path():
    """获取项目路径"""
    attempts = 0
    while attempts < 3:
        skin_path = get_skin_string('shortpath')
        if skin_path and skin_path.strip() != '':
            log(f"使用 Skin.String(shortpath): {skin_path}")
            return skin_path
        
        listitem_path = get_listitem_info('FileNameAndPath')
        if listitem_path and listitem_path.strip() != '':
            log(f"使用 ListItem.FileNameAndPath: {listitem_path}")
            return listitem_path
        
        log(f"路径获取失败，等待1秒后重试 ({attempts+1}/3)")
        time.sleep(1)
        attempts += 1
    
    log("尝试3次后仍未获取到路径")
    return None

def find_local(preview):
    """Lookup only; the caller rechecks ownership after potentially slow VFS IO."""
    if not preview.valid() or not has_skin_setting('foldertrailer'):
        return None
    project_dir = os.path.dirname(preview.path)
    order = 'current_parent' if preview.kind == 'episode' else 'current_child'
    result = find_trailer_folder(project_dir, order)
    if not preview.valid():
        return None
    return result or find_trailer_file(project_dir, preview.kind,
                                      os.path.basename(preview.path), order)


if __name__ == '__main__':
    from trailerurl import main
    main()
