import xbmc
import xbmcvfs
import os

def log(msg):
    xbmc.log("havetrailer.py: %s" % msg, level=xbmc.LOGDEBUG)

def main():
    # 首先执行 Skin.SetString(havetrailer,"")
    xbmc.executebuiltin('Skin.SetString(havetrailer,)')

    # 获取 shortpath 值
    shortpath = xbmc.getInfoLabel('Skin.String(shortpath)')
    log('shortpath: %s' % shortpath)
    
    # 判断 shortpath 是否为空
    if shortpath and shortpath.strip() != '':
        project_path = shortpath
    else:
        project_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
    
    log('project_path: %s' % project_path)
    
    if not project_path:
        log('No project path found, exiting')
        return
    
    # 获取文件所在目录
    if xbmcvfs.exists(project_path):
        if xbmcvfs.Stat(project_path).st_mode() & 0o040000:  # Check if it's a directory
            current_dir = project_path
        else:
            current_dir = os.path.dirname(project_path)
    else:
        log('Project path does not exist: %s' % project_path)
        return

    log('current_dir: %s' % current_dir)

    # 检查当前目录是否有名为 trailer 或 预告 的子目录（不区分大小写）
    dirs = xbmcvfs.listdir(current_dir)[0]  # Get directories only
    trailer_folder_found = False
    
    for dir_name in dirs:
        lower_dir_name = dir_name.lower()
        if 'trailer' in lower_dir_name or '预告' in lower_dir_name:
            # 检查该目录下是否有视频文件
            trailer_dir_path = os.path.join(current_dir, dir_name)
            if os.path.sep == '/':
                trailer_dir_path = trailer_dir_path.replace('\\', '/')
            else:
                trailer_dir_path = trailer_dir_path.replace('/', '\\')
            
            try:
                files_in_trailer_dir = xbmcvfs.listdir(trailer_dir_path)[1]  # Get files only
            except:
                continue  # Skip if we can't read the directory
                
            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.3g2', '.asf', '.f4v', '.rm', '.rmvb', '.ts', '.m2ts', '.vob', '.ogv', '.mp3', '.wav', '.flac', '.aac']
            
            for file_name in files_in_trailer_dir:
                ext = os.path.splitext(file_name)[1].lower()
                if ext in video_extensions:
                    log('Found trailer folder with video files: %s' % trailer_dir_path)
                    xbmc.executebuiltin('Skin.SetString(havetrailer,1)')
                    return

    # 如果是剧集，还需检查上级目录
    parent_dir = os.path.dirname(current_dir)
    log('parent_dir: %s' % parent_dir)
    
    # 检查上级目录是否有 trailer 或 预告 文件夹
    if parent_dir and parent_dir != current_dir:
        try:
            parent_dirs = xbmcvfs.listdir(parent_dir)[0]
        except:
            parent_dirs = []
            
        for dir_name in parent_dirs:
            lower_dir_name = dir_name.lower()
            if 'trailer' in lower_dir_name or '预告' in lower_dir_name:
                # 检查该目录下是否有视频文件
                trailer_dir_path = os.path.join(parent_dir, dir_name)
                if os.path.sep == '/':
                    trailer_dir_path = trailer_dir_path.replace('\\', '/')
                else:
                    trailer_dir_path = trailer_dir_path.replace('/', '\\')
                
                try:
                    files_in_trailer_dir = xbmcvfs.listdir(trailer_dir_path)[1]
                except:
                    continue  # Skip if we can't read the directory
                    
                video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.3g2', '.asf', '.f4v', '.rm', '.rmvb', '.ts', '.m2ts', '.vob', '.ogv', '.mp3', '.wav', '.flac', '.aac']
                
                for file_name in files_in_trailer_dir:
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext in video_extensions:
                        log('Found trailer folder in parent dir with video files: %s' % trailer_dir_path)
                        xbmc.executebuiltin('Skin.SetString(havetrailer,1)')
                        return

    # 在当前目录查找包含 trailer 或 预告 的视频文件，且文件名包含 ListItem.FileName（不含扩展名）
    listitem_filename = xbmc.getInfoLabel('ListItem.FileName')
    log('listitem_filename: %s' % listitem_filename)
    if listitem_filename:
        listitem_basename = os.path.splitext(listitem_filename)[0]
        log('listitem_basename: %s' % listitem_basename)
        
        try:
            all_files = xbmcvfs.listdir(current_dir)[1]  # Get files only
        except:
            all_files = []
            
        for file_name in all_files:
            lower_file_name = file_name.lower()
            ext = os.path.splitext(file_name)[1].lower()
            if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp', '.3g2', '.asf', '.f4v', '.rm', '.rmvb', '.ts', '.m2ts', '.vob', '.ogv', '.mp3', '.wav', '.flac', '.aac']:
                if ('trailer' in lower_file_name or '预告' in lower_file_name) and listitem_basename in file_name:
                    log('Found trailer file: %s' % file_name)
                    xbmc.executebuiltin('Skin.SetString(havetrailer,1)')
                    return

    # 如果以上条件都不满足，则直接退出脚本（不做任何操作）

if __name__ == '__main__':
    main()