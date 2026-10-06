import xbmc
import xbmcgui
import xbmcvfs
import os
import sqlite3
import time
import glob

# 配置项
VIDEO_EXTENSIONS = ('.iso', '.mkv', '.mp4', '.wmv', '.ts', '.avi', '.mov')
EXCLUDED_FOLDER_NAME = 'STEAM'

def log(msg):
    """输出详细日志到 Kodi 日志文件"""
    xbmc.log(f"[LibFolderScript] {msg}", level=xbmc.LOGINFO)

def normalize_path_separators(path):
    """
    统一路径分隔符为正斜杠，并规范网络协议头 (smb://, nfs://)
    """
    if not path:
        return ""
    
    # 1. 替换反斜杠
    p = path.replace('\\', '/')
    
    # 2. 清理多余的双斜杠，但保留协议头
    protocols = ['smb:', 'nfs:', 'upnp:', 'stack:', 'special:']
    is_network = False
    prefix = ""
    rest = p
    
    for proto in protocols:
        if p.lower().startswith(proto):
            is_network = True
            prefix_len = len(proto)
            raw_prefix = p[:prefix_len]
            remaining = p[prefix_len:]
            
            if remaining.startswith('//'):
                prefix = raw_prefix + "//"
                rest = remaining[2:]
            elif remaining.startswith('/'):
                prefix = raw_prefix + "//"
                rest = remaining[1:]
            else:
                prefix = raw_prefix + "//"
                rest = remaining
            
            break
            
    if is_network:
        while '//' in rest:
            rest = rest.replace('//', '/')
        return prefix + rest
    else:
        while '//' in p:
            p = p.replace('//', '/')
        return p

def get_latest_db_path():
    """获取最新的 MyVideos*.db 文件路径"""
    db_dir = xbmcvfs.translatePath('special://userdata/Database/')
    if not xbmcvfs.exists(db_dir):
        return None
    local_db_dir = xbmcvfs.translatePath('special://userdata/Database/')
    if not os.path.exists(local_db_dir):
        return None
    db_files = glob.glob(os.path.join(local_db_dir, 'MyVideos*.db'))
    if not db_files:
        return None
    try:
        latest_db = max(db_files, key=os.path.getmtime)
        return latest_db
    except Exception as e:
        log(f"获取DB失败: {e}")
        return None

def get_db_connection(db_path):
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        log(f"DB连接失败: {e}")
        return None

def get_paths_by_content(conn, content_type):
    cursor = conn.cursor()
    cursor.execute("SELECT idPath, strPath FROM path WHERE strContent = ?", (content_type,))
    return cursor.fetchall()

def get_movie_count_for_path(conn, str_path):
    cursor = conn.cursor()
    if not str_path.endswith('/') and not str_path.endswith('\\'):
        if '\\' in str_path:
            search_pattern = str_path + '\\%'
        else:
            search_pattern = str_path + '/%'
    else:
        search_pattern = str_path + '%'
        
    query = "SELECT COUNT(*) FROM movie WHERE c22 LIKE ?"
    cursor.execute(query, (search_pattern,))
    count = cursor.fetchone()[0]
    return count

def get_tvshow_stats_for_path(conn, path_row):
    # 修复：使用参数名 path_row 而不是未定义的 row
    str_path = path_row['strPath']
    cursor = conn.cursor()
    
    if not str_path.endswith('/') and not str_path.endswith('\\'):
        if '\\' in str_path:
            search_pattern = str_path + '\\%'
        else:
            search_pattern = str_path + '/%'
    else:
        search_pattern = str_path + '%'
        
    query_tv = "SELECT COUNT(*) FROM tvshow_view WHERE strPath LIKE ?"
    cursor.execute(query_tv, (search_pattern,))
    tvshow_count = cursor.fetchone()[0]
    
    query_ep = "SELECT COUNT(*) FROM episode WHERE c18 LIKE ?"
    cursor.execute(query_ep, (search_pattern,))
    episode_count = cursor.fetchone()[0]

    return tvshow_count, episode_count

class ScanProcessor:
    def __init__(self, conn, folder_path, content_type):
        self.conn = conn
        self.folder_path = folder_path if folder_path.endswith('/') else folder_path + '/'
        self.content_type = content_type
        
        # 统计结果
        self.total_files = 0
        self.movie_found_count = 0
        self.episode_found_count = 0
        self.not_found_files = []
        
        # 数据库索引缓存
        self.movie_paths_set = set()
        self.episode_paths_set = set()
        
        # 进度控制
        self.dialog = None
        self.root_subdirs = []
        self.total_root_dirs = 0

    def load_db_indices(self):
        """加载数据库路径索引到内存"""
        log("正在加载数据库索引到内存...")
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT c22 FROM movie")
        self.movie_paths_set = set(normalize_path_separators(row[0]) for row in cursor.fetchall())
        log(f"加载了 {len(self.movie_paths_set)} 个电影路径索引")

        cursor.execute("SELECT c18 FROM episode")
        self.episode_paths_set = set(normalize_path_separators(row[0]) for row in cursor.fetchall())
        log(f"加载了 {len(self.episode_paths_set)} 个剧集路径索引")

    def check_file(self, file_path):
        """检查单个文件是否在数据库中"""
        normalized_path = normalize_path_separators(file_path)
        self.total_files += 1
        
        if normalized_path in self.movie_paths_set:
            self.movie_found_count += 1
        elif normalized_path in self.episode_paths_set:
            self.episode_found_count += 1
        else:
            self.not_found_files.append(normalized_path)

    def scan_directory_recursive(self, current_dir, status_prefix=""):
        """递归扫描目录"""
        if self.dialog.iscanceled():
            return
            
        xbmc.sleep(2)
        
        try:
            dirs, files = xbmcvfs.listdir(current_dir)
        except Exception as e:
            log(f"读取目录失败 {current_dir}: {e}")
            return
            
        for f in files:
            if self.dialog.iscanceled(): return
            if f.lower().endswith(VIDEO_EXTENSIONS):
                full_path = f"{current_dir}{f}"
                self.check_file(full_path)
                msg = f"{status_prefix} > {f}\n已发现视频: {self.total_files}"
                self.dialog.update(-1, msg)
                
        valid_dirs = [d for d in dirs if d.upper() != EXCLUDED_FOLDER_NAME]
        for d in valid_dirs:
            if self.dialog.iscanceled(): return
            sub_dir = f"{current_dir}{d}/"
            self.scan_directory_recursive(sub_dir, status_prefix)

    def run_scan(self):
        """执行主扫描逻辑"""
        self.load_db_indices()
        
        try:
            root_dirs, root_files = xbmcvfs.listdir(self.folder_path)
            self.root_subdirs = [d for d in root_dirs if d.upper() != EXCLUDED_FOLDER_NAME]
            self.total_root_dirs = len(self.root_subdirs)
            log(f"找到 {self.total_root_dirs} 个一级子目录作为进度基准")
        except Exception as e:
            log(f"获取根目录列表失败: {e}")
            self.root_subdirs = []
            self.total_root_dirs = 0

        self.dialog = xbmcgui.DialogProgress()
        self.dialog.create("正在扫描刮削情况", "正在初始化...")
        
        for f in root_files:
            if self.dialog.iscanceled(): break
            if f.lower().endswith(VIDEO_EXTENSIONS):
                full_path = f"{self.folder_path}{f}"
                self.check_file(full_path)
                msg = f"正在扫描根目录文件: {f}\n已发现视频: {self.total_files}"
                self.dialog.update(0, msg)
                xbmc.sleep(2)

        for i, subdir_name in enumerate(self.root_subdirs):
            if self.dialog.iscanceled():
                break
                
            subdir_path = f"{self.folder_path}{subdir_name}/"
            percent = int(((i) / self.total_root_dirs) * 100) if self.total_root_dirs > 0 else 0
            
            msg = f"正在进入目录: {subdir_name}\n进度: {i+1}/{self.total_root_dirs} 个大目录"
            self.dialog.update(percent, msg)
            
            self.scan_directory_recursive(subdir_path, subdir_name)
            
        self.dialog.update(100, f"扫描完成\n共发现 {self.total_files} 个视频文件")
        xbmc.sleep(1000)
        self.dialog.close()
        
        self.show_results()

    def show_results(self):
        log(f"扫描完成. 电影: {self.movie_found_count}, 剧集: {self.episode_found_count}, 未入库: {len(self.not_found_files)}")
        
        unscraped_count = len(self.not_found_files)
        
        msg = (
            f"该文件夹视频文件数量为 [COLOR yellow]{self.total_files}[/COLOR] 个，"
            f"已扫描生入库的电影数量为 [COLOR green]{self.movie_found_count}[/COLOR] 个，"
            f"单集数量为 [COLOR green]{self.episode_found_count}[/COLOR] 个，"
            f"未入库的文件数量为 [COLOR red]{unscraped_count}[/COLOR] 个。"
            f"\n"
            f"点击“是”查看未刮削文件列表，点击“否”关闭该窗口。"
        )
        
        ret = xbmcgui.Dialog().yesno("扫描结果", msg)
        if ret:
            show_unscraped_list(self.not_found_files)

def show_unscraped_list(file_list):
    if not file_list:
        xbmcgui.Dialog().ok("提示", "所有文件均已入库！")
        return
        
    display_list = [os.path.basename(f) for f in file_list]
    index = xbmcgui.Dialog().select("未刮削文件列表 (选择以跳转目录)", display_list)
    
    if index != -1:
        selected_file = file_list[index]
        
        parts = selected_file.rsplit('/', 1)
        if len(parts) > 1:
            dir_path_kodi = parts[0]
            if not dir_path_kodi.endswith('/'):
                dir_path_kodi += '/'
        else:
            dir_path_kodi = selected_file
            
        log(f"准备跳转目录: {dir_path_kodi}")
        
        dir_path_kodi = normalize_path_separators(dir_path_kodi)
        
        if dir_path_kodi.startswith('nfs:') and not dir_path_kodi.startswith('nfs://'):
            dir_path_kodi = dir_path_kodi.replace('nfs:', 'nfs://', 1)
        elif dir_path_kodi.startswith('smb:') and not dir_path_kodi.startswith('smb://'):
            dir_path_kodi = dir_path_kodi.replace('smb:', 'smb://', 1)
            
        log(f"规范化后路径: {dir_path_kodi}")
        
        cmd = f'ActivateWindow(Videos, "{dir_path_kodi}", return)'
        log(f"执行命令: {cmd}")
        xbmc.executebuiltin(cmd)

def process_folder_scan(conn, folder_path, content_type):
    log(f"=== 开始处理文件夹扫描 ===")
    processor = ScanProcessor(conn, folder_path, content_type)
    processor.run_scan()

def main():
    log("=== 脚本启动 ===")
    db_path = get_latest_db_path()
    if not db_path:
        return
        
    conn = get_db_connection(db_path)
    if not conn:
        return
        
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM movie")
        movie_total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tvshow")
        tvshow_total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM episode")
        episode_total = cursor.fetchone()[0]
        
        opt_movies = f"已刮削电影文件夹 - [电影 [COLOR green]{movie_total}[/COLOR] 部]"
        opt_tvshows = f"已刮削剧集文件夹 - [剧集 [COLOR green]{tvshow_total}[/COLOR] 部，单集 [COLOR green]{episode_total}[/COLOR] 部]"
        
        options = [opt_movies, opt_tvshows]
        selection = xbmcgui.Dialog().select("请选择操作类型", options)
        
        if selection == 0:
            handle_movies(conn)
        elif selection == 1:
            handle_tvshows(conn)
            
    finally:
        conn.close()
        log("=== 脚本结束 ===")

def handle_movies(conn):
    paths = get_paths_by_content(conn, 'movies')
    if not paths:
        xbmcgui.Dialog().ok("提示", "数据库中没有找到标记为 'movies' 的路径。")
        return
        
    options = []
    path_data = []
    
    for row in paths:
        str_path = row['strPath']
        count = get_movie_count_for_path(conn, str_path)
        
        display_path = normalize_path_separators(str_path)
        label = f"{display_path} - [电影 [COLOR green]{count}[/COLOR] 部]"
        options.append(label)
        path_data.append(str_path) 
        
    idx = xbmcgui.Dialog().select("选择电影文件夹", options)
    if idx != -1:
        selected_path = path_data[idx]
        process_folder_scan(conn, selected_path, 'movies')

def handle_tvshows(conn):
    paths = get_paths_by_content(conn, 'tvshows')
    if not paths:
        xbmcgui.Dialog().ok("提示", "数据库中没有找到标记为 'tvshows' 的路径。")
        return
        
    options = []
    path_data = []
    
    for row in paths:
        str_path = row['strPath']
        # 修复：确保传入的是 row
        ts_count, ep_count = get_tvshow_stats_for_path(conn, row)
        
        display_path = normalize_path_separators(str_path)
        label = f"{display_path} - [剧集 [COLOR green]{ts_count}[/COLOR] 部，单集 [COLOR green]{ep_count}[/COLOR] 部]"
        options.append(label)
        path_data.append(str_path)
        
    idx = xbmcgui.Dialog().select("选择剧集文件夹", options)
    if idx != -1:
        selected_path = path_data[idx]
        process_folder_scan(conn, selected_path, 'tvshows')

if __name__ == '__main__':
    main()