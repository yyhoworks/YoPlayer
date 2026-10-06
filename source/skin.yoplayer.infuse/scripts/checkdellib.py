import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import os

def log_message(message, level=xbmc.LOGINFO):
    """记录日志消息"""
    xbmc.log(f"[checkdellib.py] {message}", level=level)

def get_database_path():
    """获取视频数据库路径"""
    try:
        database_path = xbmcvfs.translatePath('special://userdata/Database/MyVideos131.db')
        log_message(f"Initial database path: {database_path}")
        
        # 获取最新的MyVideos数据库文件
        db_dir = xbmcvfs.translatePath('special://userdata/Database/')
        log_message(f"Database directory: {db_dir}")
        
        if os.path.exists(db_dir):
            files = [f for f in os.listdir(db_dir) if f.startswith('MyVideos') and f.endswith('.db')]
            log_message(f"Found database files: {files}")
            
            if files:
                latest_db = max(files, key=lambda x: int(x.replace('MyVideos', '').replace('.db', '')))
                database_path = xbmcvfs.translatePath(f'special://userdata/Database/{latest_db}')
                log_message(f"Using latest database: {database_path}")
        else:
            log_message("Database directory does not exist", xbmc.LOGWARNING)
            
        return database_path
    except Exception as e:
        log_message(f"Error getting database path: {str(e)}", xbmc.LOGERROR)
        return xbmcvfs.translatePath('special://userdata/Database/MyVideos131.db')

def execute_sql_query(query, params=None):
    """执行SQL查询"""
    conn = None
    try:
        log_message(f"Executing SQL query: {query[:100]}...")
        if params:
            log_message(f"With parameters: {params}")
        
        db_path = get_database_path()
        log_message(f"Connecting to database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if query.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
            log_message(f"Query returned {len(result)} rows")
        else:
            conn.commit()
            result = cursor.rowcount
            log_message(f"Query affected {result} rows")
            
        return result
    except Exception as e:
        log_message(f"SQL Error: {str(e)}", xbmc.LOGERROR)
        return []
    finally:
        if conn:
            conn.close()
            log_message("Database connection closed")

def delete_movie_by_id(id_movie):
    """删除指定idMovie的电影记录"""
    try:
        log_message(f"Deleting movie with idMovie: {id_movie}")
        
        # 删除movie表中的记录
        movie_count = execute_sql_query(
            "DELETE FROM movie WHERE idMovie = ?", 
            (id_movie,)
        )
        log_message(f"Deleted {movie_count} movie records")
        
        # 尝试删除相关的path记录
        path_result = execute_sql_query(
            "SELECT strPath FROM movie WHERE idMovie = ?",
            (id_movie,)
        )
        
        if path_result:
            path = path_result[0][0] if isinstance(path_result[0], tuple) else path_result[0]
            path_count = execute_sql_query(
                "DELETE FROM path WHERE strPath = ?", 
                (path,)
            )
            log_message(f"Deleted {path_count} path records associated with movie")
        
        return movie_count
    except Exception as e:
        log_message(f"Error deleting movie: {str(e)}", xbmc.LOGERROR)
        return 0

def delete_episode_by_id(id_episode):
    """删除指定idEpisode的剧集记录"""
    try:
        log_message(f"Deleting episode with idEpisode: {id_episode}")
        
        # 删除episode表中的记录
        episode_count = execute_sql_query(
            "DELETE FROM episode WHERE idEpisode = ?", 
            (id_episode,)
        )
        log_message(f"Deleted {episode_count} episode records")
        
        return episode_count
    except Exception as e:
        log_message(f"Error deleting episode: {str(e)}", xbmc.LOGERROR)
        return 0

def delete_movie_by_idpath(id_path):
    """删除指定idPath下的所有电影记录"""
    try:
        log_message(f"Deleting movies for idPath: {id_path}")
        
        # 删除movie表中的记录
        movie_count = execute_sql_query(
            "DELETE FROM movie WHERE c23 = ?", 
            (id_path,)
        )
        log_message(f"Deleted {movie_count} movie records")
        
        # 删除path表中的记录
        path_count = execute_sql_query(
            "DELETE FROM path WHERE idPath = ?", 
            (id_path,)
        )
        log_message(f"Deleted {path_count} path records")
        
        return movie_count, path_count
    except Exception as e:
        log_message(f"Error deleting movies: {str(e)}", xbmc.LOGERROR)
        return 0, 0

def delete_tvshow_by_idshow(id_show):
    """删除指定idShow下的所有剧集记录"""
    try:
        log_message(f"Deleting TV show for idShow: {id_show}")
        
        # 获取episode表中对应idShow的记录数
        episode_count = execute_sql_query(
            "DELETE FROM episode WHERE idShow = ?", 
            (id_show,)
        )
        log_message(f"Deleted {episode_count} episode records")
        
        # 删除seasons表中的记录
        season_count = execute_sql_query(
            "DELETE FROM seasons WHERE idShow = ?", 
            (id_show,)
        )
        log_message(f"Deleted {season_count} season records")
        
        # 删除tvshow表中的记录
        tvshow_count = execute_sql_query(
            "DELETE FROM tvshow WHERE idShow = ?", 
            (id_show,)
        )
        log_message(f"Deleted {tvshow_count} tvshow records")
        
        return episode_count, season_count, tvshow_count
    except Exception as e:
        log_message(f"Error deleting TV shows: {str(e)}", xbmc.LOGERROR)
        return 0, 0, 0

def delete_season_by_idseason(id_season):
    """删除指定idSeason下的所有记录"""
    try:
        log_message(f"Deleting season for idSeason: {id_season}")
        
        # 删除episode表中对应idSeason的记录
        episode_count = execute_sql_query(
            "DELETE FROM episode WHERE idSeason = ?", 
            (id_season,)
        )
        log_message(f"Deleted {episode_count} episode records")
        
        # 删除seasons表中的记录
        season_count = execute_sql_query(
            "DELETE FROM seasons WHERE idSeason = ?", 
            (id_season,)
        )
        log_message(f"Deleted {season_count} season records")
        
        return episode_count, season_count
    except Exception as e:
        log_message(f"Error deleting season: {str(e)}", xbmc.LOGERROR)
        return 0, 0

def delete_movies_and_episodes_by_paths(movie_paths, tvshow_paths):
    """根据路径列表删除电影和剧集记录"""
    log_message(f"Deleting movies: {len(movie_paths)} paths, TV shows: {len(tvshow_paths)} paths")
    
    total_movie_deleted = 0
    total_tvshow_deleted = 0
    total_episode_deleted = 0
    
    # 删除电影
    for i, movie_path in enumerate(movie_paths):
        log_message(f"Processing movie path {i+1}/{len(movie_paths)}: {movie_path}")
        count = execute_sql_query(
            "DELETE FROM movie WHERE c22 = ?", 
            (movie_path,)
        )
        total_movie_deleted += count
        log_message(f"Deleted {count} movie records for path {movie_path}")
        
        # 同时删除相关的path记录
        path_count = execute_sql_query(
            "DELETE FROM path WHERE strPath = ?", 
            (movie_path,)
        )
        log_message(f"Deleted {path_count} path records for path {movie_path}")
    
    # 删除剧集
    for i, tvshow_path in enumerate(tvshow_paths):
        log_message(f"Processing TV show path {i+1}/{len(tvshow_paths)}: {tvshow_path}")
        
        # 获取相关的episode记录
        episodes = execute_sql_query(
            "SELECT DISTINCT idShow FROM episode WHERE c18 = ?", 
            (tvshow_path,)
        )
        
        for (id_show,) in episodes:
            log_message(f"Deleting TV show with idShow: {id_show}")
            episode_count, season_count, tvshow_count = delete_tvshow_by_idshow(id_show)
            total_episode_deleted += episode_count
            total_tvshow_deleted += tvshow_count
            log_message(f"Deleted {episode_count} episodes and {tvshow_count} TV shows")
    
    log_message(f"Total deleted - Movies: {total_movie_deleted}, TV Shows: {total_tvshow_deleted}, Episodes: {total_episode_deleted}")
    return total_movie_deleted, total_tvshow_deleted, total_episode_deleted

def refresh_container():
    """刷新当前容器"""
    log_message("Refreshing container")
    xbmc.executebuiltin('Container.Refresh')

def handle_file_deletion():
    """处理文件删除逻辑"""
    log_message("Handling file deletion based on DBType and DBID")
    
    # 获取DBType和DBID
    db_type = xbmc.getInfoLabel('ListItem.DBType')
    db_id = xbmc.getInfoLabel('ListItem.DBID')
    
    log_message(f"DBType: {db_type}, DBID: {db_id}")
    
    if not db_type or not db_id:
        log_message("DBType or DBID is empty, cannot proceed with file deletion")
        xbmcgui.Dialog().ok('错误', '无法获取项目类型或ID')
        return
    
    # 情况1：电影
    if db_type.lower() == 'movie':
        log_message("Handling movie deletion")
        
        # 验证数据库中是否存在该电影记录
        result = execute_sql_query(
            "SELECT idMovie, c00 FROM movie WHERE idMovie = ?", 
            (int(db_id),)
        )
        
        if not result:
            log_message("No movie record found with given ID")
            xbmcgui.Dialog().ok('提示', '未找到对应的电影记录')
            return
        
        # 弹出确认提示
        log_message("Showing confirmation dialog for movie deletion")
        confirm = xbmcgui.Dialog().yesno(
            '确认删除',
            '是否确认删除已刮削数据？\n选择"是"确认删除，选择"否"取消操作。'
        )
        
        log_message(f"Movie delete confirmation: {confirm}")
        
        if not confirm:
            log_message("User cancelled movie deletion")
            return  # 用户取消，返回上一选择窗口
        
        # 执行删除操作
        log_message("Starting movie deletion process")
        deleted_count = delete_movie_by_id(int(db_id))
        
        log_message(f"Movie deletion completed - Deleted {deleted_count} records")
        
        # 显示完成提示
        xbmcgui.Dialog().ok('删除成功', '已在删除所选文件刮削记录！')
        
        # 刷新容器
        refresh_container()
    
    # 情况2：剧集
    elif db_type.lower() == 'episode':
        log_message("Handling episode deletion")
        
        # 验证数据库中是否存在该剧集记录
        result = execute_sql_query(
            "SELECT idEpisode, c00 FROM episode WHERE idEpisode = ?", 
            (int(db_id),)
        )
        
        if not result:
            log_message("No episode record found with given ID")
            xbmcgui.Dialog().ok('提示', '未找到对应的剧集记录')
            return
        
        # 弹出确认提示
        log_message("Showing confirmation dialog for episode deletion")
        confirm = xbmcgui.Dialog().yesno(
            '确认删除',
            '是否确认删除已刮削数据？\n选择"是"确认删除，选择"否"取消操作。'
        )
        
        log_message(f"Episode delete confirmation: {confirm}")
        
        if not confirm:
            log_message("User cancelled episode deletion")
            return  # 用户取消，返回上一选择窗口
        
        # 执行删除操作
        log_message("Starting episode deletion process")
        deleted_count = delete_episode_by_id(int(db_id))
        
        log_message(f"Episode deletion completed - Deleted {deleted_count} records")
        
        # 显示完成提示
        xbmcgui.Dialog().ok('删除成功', '已在删除所选文件刮削记录！')
        
        # 刷新容器
        refresh_container()
    
    # 情况3：电视剧
    elif db_type.lower() == 'tvshow':
        log_message("Handling TV show deletion")
        
        # 验证数据库中是否存在该电视剧记录
        result = execute_sql_query(
            "SELECT idShow, c00 FROM tvshow WHERE idShow = ?", 
            (int(db_id),)
        )
        
        if not result:
            log_message("No TV show record found with given ID")
            xbmcgui.Dialog().ok('提示', '未找到对应的电视剧记录')
            return
        
        # 弹出确认提示
        log_message("Showing confirmation dialog for TV show deletion")
        confirm = xbmcgui.Dialog().yesno(
            '确认删除',
            '是否确认删除已刮削数据？\n选择"是"确认删除，选择"否"取消操作。'
        )
        
        log_message(f"TV show delete confirmation: {confirm}")
        
        if not confirm:
            log_message("User cancelled TV show deletion")
            return  # 用户取消，返回上一选择窗口
        
        # 执行删除操作
        log_message("Starting TV show deletion process")
        episode_count, season_count, tvshow_count = delete_tvshow_by_idshow(int(db_id))
        
        log_message(f"TV show deletion completed - Deleted {episode_count} episodes, {season_count} seasons, {tvshow_count} TV shows")
        
        # 显示完成提示
        xbmcgui.Dialog().ok('删除成功', '已在删除所选文件刮削记录！')
        
        # 刷新容器
        refresh_container()
    
    # 情况4：季
    elif db_type.lower() == 'season':
        log_message("Handling season deletion")
        
        # 验证数据库中是否存在该季记录
        result = execute_sql_query(
            "SELECT idSeason, name FROM seasons WHERE idSeason = ?", 
            (int(db_id),)
        )
        
        if not result:
            log_message("No season record found with given ID")
            xbmcgui.Dialog().ok('提示', '未找到对应的季记录')
            return
        
        # 弹出确认提示
        log_message("Showing confirmation dialog for season deletion")
        confirm = xbmcgui.Dialog().yesno(
            '确认删除',
            '是否确认删除已刮削数据？\n选择"是"确认删除，选择"否"取消操作。'
        )
        
        log_message(f"Season delete confirmation: {confirm}")
        
        if not confirm:
            log_message("User cancelled season deletion")
            return  # 用户取消，返回上一选择窗口
        
        # 执行删除操作
        log_message("Starting season deletion process")
        episode_count, season_count = delete_season_by_idseason(int(db_id))
        
        log_message(f"Season deletion completed - Deleted {episode_count} episodes, {season_count} seasons")
        
        # 显示完成提示
        xbmcgui.Dialog().ok('删除成功', '已在删除所选文件刮削记录！')
        
        # 刷新容器
        refresh_container()
    
    else:
        log_message(f"Unsupported DBType: {db_type}")
        xbmcgui.Dialog().ok('错误', f'不支持的项目类型: {db_type}')

def main():
    log_message("Script started")
    
    # 检查是否有参数
    import sys
    args = sys.argv
    log_message(f"Script arguments: {args}")
    
    if len(args) >= 2:
        if 'file' in args:
            log_message("Script called with file parameter")
            handle_file_deletion()
            return
        elif 'folder' in args:
            log_message("Script called with folder parameter")
        else:
            log_message("Script called with unknown parameter", xbmc.LOGWARNING)
            return
    else:
        log_message("Script called without parameters", xbmc.LOGINFO)
        return
    
    # 获取当前文件夹路径
    current_folder = xbmc.getInfoLabel('ListItem.FolderPath')
    log_message(f"Current folder path: {current_folder}")
    
    if not current_folder:
        log_message("Could not get current folder path", xbmc.LOGERROR)
        xbmcgui.Dialog().ok('错误', '无法获取当前文件夹路径')
        return
    
    # 主选择窗口
    log_message("Showing main selection dialog")
    choice = xbmcgui.Dialog().select(
        '刮削文件管理',
        [
            '查看本目录下已刮削文件夹(点击可删除)',
            '批量删除本目录下已刮削文件(可多选)'
        ]
    )
    
    log_message(f"User choice: {choice}")
    
    if choice == -1:  # 用户取消
        log_message("User cancelled operation")
        return
    
    if choice == 0:  # 查看并删除文件夹
        log_message("User selected option 0: View and delete folders")
        
        # 查询path表中符合条件的记录
        log_message("Querying path table for scraped folders")
        results = execute_sql_query(
            """
            SELECT idPath, strPath, strContent, strScraper 
            FROM path 
            WHERE strScraper IS NOT NULL AND strScraper != ''
            AND strPath LIKE ?
            """,
            (f'%{current_folder}%',)
        )
        
        log_message(f"Found {len(results)} scraped folders")
        
        if not results:
            log_message("No scraped folders found in current directory")
            xbmcgui.Dialog().ok('提示', '当前目录下没有已刮削的文件夹')
            return
        
        # 准备选择列表
        options = []
        for i, row in enumerate(results):
            id_path, str_path, content_type, scraper = row
            content_label = '[电影]' if content_type == 'movies' else '[剧集]'
            option_text = f'{content_label}-{str_path}'
            options.append(option_text)
            log_message(f"Option {i}: {option_text}")
        
        # 显示选择窗口
        log_message("Showing folder selection dialog")
        selected_index = xbmcgui.Dialog().select('选择要删除的已刮削文件夹', options)
        
        log_message(f"Selected index: {selected_index}")
        
        if selected_index == -1:  # 用户取消
            log_message("User cancelled folder selection")
            return
        
        # 获取选中的行信息
        selected_row = results[selected_index]
        id_path, str_path, content_type, scraper = selected_row
        content_label = '[电影]' if content_type == 'movies' else '[剧集]'
        log_message(f"Selected folder - Path: {str_path}, Type: {content_type}, ID: {id_path}")
        
        # 确认删除
        log_message("Showing confirmation dialog for folder deletion")
        confirm = xbmcgui.Dialog().yesno(
            '确认删除',
            f'是否确认删除所选文件夹所有已刮削电影？\n\n选择"是"确认删除，选择"否"取消操作。'
        )
        
        log_message(f"Delete confirmation: {confirm}")
        
        if not confirm:
            log_message("User cancelled deletion")
            return  # 用户取消，返回上级窗口
        
        # 执行删除操作
        log_message("Starting deletion process")
        if content_type == 'movies':
            # 子情况1.1：删除电影
            log_message("Deleting movie folder")
            movie_count, path_count = delete_movie_by_idpath(id_path)
            
            message = (f'已在媒体库中删除文件夹刮削记录[COLOR yellow]{path_count}[/COLOR]个，'
                      f'其中包含电影[COLOR yellow]{movie_count}[/COLOR]部。')
            log_message(f"Deletion completed - {message}")
            
            xbmcgui.Dialog().ok('删除成功', message)
            
            # 刷新容器
            refresh_container()
        
        elif content_type == 'tvshows':
            # 子情况1.2：删除剧集
            log_message("Deleting TV show folder")
            
            # 获取episode表中对应的idShow值
            id_shows = execute_sql_query(
                "SELECT DISTINCT idShow FROM episode WHERE c19 = ?", 
                (id_path,)
            )
            
            log_message(f"Found {len(id_shows)} TV show IDs to delete")
            
            total_episode_deleted = 0
            total_tvshow_deleted = 0
            total_season_deleted = 0
            
            for i, (id_show,) in enumerate(id_shows):
                log_message(f"Processing TV show {i+1}/{len(id_shows)} with idShow: {id_show}")
                episode_count, season_count, tvshow_count = delete_tvshow_by_idshow(id_show)
                total_episode_deleted += episode_count
                total_season_deleted += season_count
                total_tvshow_deleted += tvshow_count
                log_message(f"Deleted {episode_count} episodes, {season_count} seasons and {tvshow_count} TV shows for idShow {id_show}")
            
            # 删除path表中的记录
            path_count = execute_sql_query(
                "DELETE FROM path WHERE idPath = ?", 
                (id_path,)
            )
            log_message(f"Deleted {path_count} path records for folder")
            
            message = (f'已在媒体库中删除文件夹刮削记录[COLOR yellow]{path_count}[/COLOR]个！'
                      f'其中包含剧集[COLOR yellow]{total_tvshow_deleted}[/COLOR]部，'
                      f'单集[COLOR yellow]{total_episode_deleted}[/COLOR]集。')
            log_message(f"Deletion completed - {message}")
            
            xbmcgui.Dialog().ok('删除成功', message)
            
            # 刷新容器
            refresh_container()
    
    elif choice == 1:  # 批量删除文件
        log_message("User selected option 1: Batch delete files")
        
        # 筛选movie表中符合条件的记录
        log_message("Querying movie table for files in current folder")
        movie_results = execute_sql_query(
            """
            SELECT idMovie, c00, c22 
            FROM movie 
            WHERE c22 LIKE ?
            ORDER BY c16
            """,
            (f'%{current_folder}%',)
        )
        
        log_message(f"Found {len(movie_results)} movie files")
        
        # 筛选episode表中符合条件的记录并获取idShow
        log_message("Querying episode table for files in current folder")
        episode_id_shows = execute_sql_query(
            """
            SELECT DISTINCT idShow 
            FROM episode 
            WHERE c18 LIKE ?
            """,
            (f'%{current_folder}%',)
        )
        
        log_message(f"Found {len(episode_id_shows)} unique TV show IDs")
        
        # 根据获取的idShow筛选tvshow表
        tvshow_results = []
        if episode_id_shows:
            placeholders = ','.join(['?' for _ in episode_id_shows])
            query = f"""
            SELECT idShow, c00, c15 
            FROM tvshow 
            WHERE idShow IN ({placeholders})
            ORDER BY c15
            """
            tvshow_ids = [row[0] for row in episode_id_shows]
            log_message(f"Querying TV shows with IDs: {tvshow_ids}")
            tvshow_results = execute_sql_query(query, tvshow_ids)
        
        log_message(f"Found {len(tvshow_results)} TV show entries")
        
        # 准备选择列表
        all_options = []
        selection_data = []  # 存储选中项的数据
        
        # 添加电影选项
        for i, movie in enumerate(movie_results):
            id_movie, title, path = movie
            option_text = f'[电影]-{title}'
            all_options.append(option_text)
            selection_data.append(('movie', id_movie, path))
            log_message(f"Movie option {i}: {option_text}")
        
        # 添加剧集选项
        for i, tvshow in enumerate(tvshow_results):
            id_show, title, sort_title = tvshow
            option_text = f'[剧集]-{title}'
            all_options.append(option_text)
            selection_data.append(('tvshow', id_show, None))
            log_message(f"TV show option {len(movie_results)+i}: {option_text}")
        
        if not all_options:
            log_message("No scraped files found in current directory")
            xbmcgui.Dialog().ok('提示', '当前目录下没有已刮削的文件')
            return
        
        log_message(f"Showing multiselect dialog with {len(all_options)} options")
        
        # 显示多选窗口
        selected_indices = xbmcgui.Dialog().multiselect('选择要删除的已刮削文件', all_options)
        
        if selected_indices is None:  # 用户取消
            log_message("User cancelled file selection")
            return
        
        log_message(f"User selected {len(selected_indices)} items: {selected_indices}")
        
        # 确认删除
        log_message("Showing confirmation dialog for batch deletion")
        confirm = xbmcgui.Dialog().yesno(
            '确认删除',
            '是否确认删除您选择的已刮削电影/剧集？\n\n选择"是"确认删除，选择"否"取消操作。'
        )
        
        log_message(f"Batch delete confirmation: {confirm}")
        
        if not confirm:
            log_message("User cancelled batch deletion")
            return  # 用户取消，返回上级窗口
        
        # 统计删除数量
        total_movie_deleted = 0
        total_tvshow_deleted = 0
        total_episode_deleted = 0
        total_season_deleted = 0
        
        # 处理选中的项目
        log_message("Starting batch deletion process")
        for i, index in enumerate(selected_indices):
            item_type, item_id, path = selection_data[index]
            log_message(f"Processing item {i+1}/{len(selected_indices)} - Type: {item_type}, ID: {item_id}")
            
            if item_type == 'movie':
                # 子情况2.1：删除电影
                log_message(f"Deleting movie with ID: {item_id}")
                count = execute_sql_query(
                    "DELETE FROM movie WHERE idMovie = ?", 
                    (item_id,)
                )
                total_movie_deleted += count
                log_message(f"Deleted {count} movie records")
                
                # 删除相关的path记录
                if path:
                    path_count = execute_sql_query(
                        "DELETE FROM path WHERE strPath = ?", 
                        (path,)
                    )
                    log_message(f"Deleted {path_count} path records for movie")
            
            elif item_type == 'tvshow':
                # 子情况2.2：删除剧集
                log_message(f"Deleting TV show with ID: {item_id}")
                episode_count, season_count, tvshow_count = delete_tvshow_by_idshow(item_id)
                total_episode_deleted += episode_count
                total_season_deleted += season_count
                total_tvshow_deleted += tvshow_count
                log_message(f"Deleted {episode_count} episodes, {season_count} seasons and {tvshow_count} TV show records")
        
        # 计算总删除数量
        total_deleted = total_movie_deleted + total_tvshow_deleted
        
        message = (f'已删除文件刮削记录[COLOR yellow]{total_deleted}[/COLOR]个！'
                  f'其中包含电影[COLOR yellow]{total_movie_deleted}[/COLOR]部，'
                  f'剧集[COLOR yellow]{total_tvshow_deleted}[/COLOR]部，'
                  f'单集[COLOR yellow]{total_episode_deleted}[/COLOR]集。')
        log_message(f"Batch deletion completed - {message}")
        
        # 显示结果
        xbmcgui.Dialog().ok('批量删除完成', message)
        
        # 刷新容器
        refresh_container()
    
    log_message("Script finished successfully")

if __name__ == '__main__':
    main()