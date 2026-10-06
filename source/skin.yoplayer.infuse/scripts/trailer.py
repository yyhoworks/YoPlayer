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
                sub_path = os.path.join(base_path, sub_dir).replace('\\', '/').replace('//', '/')
                dirs_in_sub, files_in_sub = safe_listdir(sub_path)
                
                for item in dirs_in_sub:
                    if 'trailer' in item.lower() or '预告' in item:
                        folder_path = os.path.join(sub_path, item).replace('\\', '/').replace('//', '/')
                        log(f"在下级目录 '{sub_path}' 中找到匹配的文件夹: {folder_path}")
                        
                        # 检查该文件夹下是否有视频文件
                        sub_dirs, sub_files = safe_listdir(folder_path)
                        for file_item in sub_files:
                            if is_video_file(file_item):
                                full_path = os.path.join(folder_path, file_item).replace('\\', '/').replace('//', '/')
                                log(f"在预告片文件夹中找到视频文件: {full_path}")
                                return full_path
        else:
            # 当前目录或上级目录搜索
            dirs, files = safe_listdir(search_path)
            
            for item in dirs:
                if 'trailer' in item.lower() or '预告' in item:
                    folder_path = os.path.join(search_path, item).replace('\\', '/').replace('//', '/')
                    log(f"找到匹配的文件夹: {folder_path}")
                    
                    # 检查该文件夹下是否有视频文件
                    sub_dirs, sub_files = safe_listdir(folder_path)
                    for file_item in sub_files:
                        if is_video_file(file_item):
                            full_path = os.path.join(folder_path, file_item).replace('\\', '/').replace('//', '/')
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
                sub_path = os.path.join(base_path, sub_dir).replace('\\', '/').replace('//', '/')
                dirs_in_sub, files_in_sub = safe_listdir(sub_path)
                
                for file_item in files_in_sub:
                    if is_video_file(file_item):
                        if 'trailer' in file_item.lower() or '预告' in file_item:
                            if should_check_filename(dbtype, filename, file_item):
                                full_path = os.path.join(sub_path, file_item).replace('\\', '/').replace('//', '/')
                                log(f"在下级目录中找到预告片文件: {full_path}")
                                return full_path
        else:
            # 当前目录或上级目录搜索
            dirs, files = safe_listdir(search_path)
            
            for file_item in files:
                if is_video_file(file_item):
                    if 'trailer' in file_item.lower() or '预告' in file_item:
                        if should_check_filename(dbtype, filename, file_item):
                            full_path = os.path.join(search_path, file_item).replace('\\', '/').replace('//', '/')
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

def main():
    try:
        # 检查是否带有info参数
        import sys
        if len(sys.argv) < 2 or sys.argv[1] != 'info':
            log("脚本需要info参数")
            return
        
        log("开始执行预告片脚本")
        
        # 检查Skin.HasSetting(foldertrailer)
        if not has_skin_setting('foldertrailer'):
            log("Skin.HasSetting(foldertrailer) 为否，执行备选脚本")
            xbmc.executebuiltin("RunScript(special://skin/scripts/bili.py,info)")
            return
        
        # 获取项目路径
        project_path = get_project_path()
        if not project_path:
            log("未能获取项目路径，执行备选脚本")
            xbmc.executebuiltin("RunScript(special://skin/scripts/bili.py,info)")
            return
        
        log(f"项目路径: {project_path}")
        
        # 获取项目所在目录
        project_dir = os.path.dirname(project_path)
        log(f"项目目录: {project_dir}")
        
        # 获取数据库类型和文件名
        dbtype = get_listitem_info('DBTYPE')
        filename = get_listitem_info('FileName')
        log(f"DBTYPE: {dbtype}, FileName: {filename}")
        
        trailer_url = None
        
        if dbtype == 'episode':
            # 情况1：剧集类型
            log("检测到剧集类型，按 episode 规则查找")
            
            # 1. 查找预告片文件夹 (项目本级目录 -> 上级目录)
            log("按顺序在项目本级目录、上级目录查找预告片文件夹...")
            trailer_url = find_trailer_folder(project_dir, "current_parent")
            if trailer_url:
                log(f"找到预告片文件夹中的视频: {trailer_url}")
            else:
                # 2. 查找预告片视频文件 (项目本级目录 -> 上级目录)
                log("按顺序在项目本级目录、上级目录查找预告片视频文件...")
                trailer_url = find_trailer_file(project_dir, dbtype, filename, "current_parent")
                if trailer_url:
                    log(f"找到预告片视频文件: {trailer_url}")
        else:
            # 情况2：非剧集类型（电影等）
            log("检测到非剧集类型，按非 episode 规则查找")
            
            # 1. 查找预告片文件夹 (项目本级目录 -> 下级目录)
            log("按顺序在项目本级目录、下级目录查找预告片文件夹...")
            trailer_url = find_trailer_folder(project_dir, "current_child")
            if trailer_url:
                log(f"找到预告片文件夹中的视频: {trailer_url}")
            else:
                # 2. 查找预告片视频文件 (项目本级目录 -> 下级目录)
                log("按顺序在项目本级目录、下级目录查找预告片视频文件...")
                trailer_url = find_trailer_file(project_dir, dbtype, filename, "current_child")
                if trailer_url:
                    log(f"找到预告片视频文件: {trailer_url}")
        
        if not trailer_url:
            log("未找到预告片，执行备选脚本")
            xbmc.executebuiltin("RunScript(special://skin/scripts/bili.py,info)")
            return
        
        log(f"最终确定预告片URL: {trailer_url}")
        
        # 播放预告片
        play_media(trailer_url)
        
        # 检测预告片是否正常播放
        playback_started = False
        for i in range(10):  # 等待最多5秒检测播放状态
            if xbmc.Player().isPlayingVideo():
                playback_started = True
                break
            time.sleep(0.5)
        
        if not playback_started:
            log("预告片未正常播放，执行备选脚本")
            xbmc.executebuiltin("RunScript(special://skin/scripts/bili.py,info)")
            return
        
        # 设置notrailer为0
        set_skin_string('notrailer', '0')
        
        # 检查是否循环播放
        is_loop_enabled = has_skin_setting('trailerloop')
        log(f"循环播放设置: {is_loop_enabled}")
        
        if not is_loop_enabled:
            # 不循环播放，监测播放结束
            log("非循环模式，监测播放结束...")
            while xbmc.Player().isPlayingVideo():
                time.sleep(0.5)
            
            # 播放结束后设置notrailer为1并关闭对话框
            set_skin_string('notrailer', '1')
            close_dialog(1130)
            log("非循环模式结束")
        else:
            # 循环播放模式
            log("循环模式，持续监测播放状态...")
            while True:
                # 等待当前播放结束
                while xbmc.Player().isPlayingVideo():
                    time.sleep(0.5)
                
                # 检查窗口是否可见
                if xbmc.getCondVisibility("Window.IsVisible(1130)"):
                    log("窗口可见，重新播放预告片")
                    play_media(trailer_url)
                else:
                    # 窗口不可见，退出循环
                    log("窗口不可见，退出循环")
                    break
            
            log("循环模式结束")
        
        log("脚本执行完成")
        
    except Exception as e:
        log(f"脚本执行异常: {str(e)}")
        import traceback
        log(f"详细错误信息: {traceback.format_exc()}")
        xbmc.executebuiltin("RunScript(special://skin/scripts/bili.py,info)")

if __name__ == "__main__":
    main()