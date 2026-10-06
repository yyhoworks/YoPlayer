import os
import sys
import re
import sqlite3
import fnmatch
import xbmc
import xbmcgui
import xbmcvfs

# ===================== 通用工具函数 =====================
def get_db_path():
    """获取最新的MyVideos*.db的绝对路径（兼容跨平台）"""
    try:
        userdata_path = xbmcvfs.translatePath("special://userdata")
    except AttributeError:
        userdata_path = xbmc.translatePath("special://userdata")
    
    database_dir = os.path.join(userdata_path, "Database")
    
    if not os.path.exists(database_dir):
        return None
        
    latest_db = None
    latest_time = 0
    
    # 遍历Database目录，寻找MyVideos*.db并获取修改时间最新的文件
    for filename in os.listdir(database_dir):
        if fnmatch.fnmatch(filename, 'MyVideos*.db'):
            file_path = os.path.join(database_dir, filename)
            if os.path.isfile(file_path):
                try:
                    mod_time = os.path.getmtime(file_path)
                    if mod_time > latest_time:
                        latest_time = mod_time
                        latest_db = file_path
                except Exception:
                    pass
                    
    return latest_db

def get_media_count(media_type):
    """获取媒体库总数（Movies/Tvshows）"""
    if media_type == "movie":
        count_str = xbmc.getInfoLabel("Window(Home).Property(Movies.Count)")
    elif media_type == "tvshow":
        count_str = xbmc.getInfoLabel("Window(Home).Property(Tvshows.Count)")
    else:
        return 0
    try:
        return int(count_str) if count_str.strip() else 0
    except ValueError:
        return 0

def show_error_dialog(msg):
    """通用错误弹窗"""
    xbmc.log(f"脚本错误: {msg}", xbmc.LOGERROR)
    xbmcgui.Dialog().ok("错误", msg)

# ===================== 无参数 - 主选择逻辑（优化选项顺序+新增海报清理选项） =====================
def main_menu():
    """无参数时显示主选择菜单"""
    # 调整选项顺序，插入第三选项“删除重复、无效海报数据”
    options = [
        "清理失效电影数据",
        "清理失效剧集数据",
        "删除重复、无效海报数据",  # 新增选项（索引2）
        "批量删除海报数据",        # 原索引2，现索引3
        "海报图片本地化",          # 原索引3，现索引4
        "[COLOR red]删除整个媒体库(包括所有电影/剧集)[/COLOR]"  # 原索引4，现索引5
    ]
    selected = xbmcgui.Dialog().select("媒体库清理工具", options)
    
    if selected == 0:
        xbmc.executebuiltin(f"RunScript(special://skin/scripts/clearlibrary.py,movie)")
    elif selected == 1:
        xbmc.executebuiltin(f"RunScript(special://skin/scripts/clearlibrary.py,tvshow)")
    elif selected == 2:
        # 执行新增的删除重复、无效海报数据
        xbmc.executebuiltin(f"RunScript(special://skin/scripts/clearlibrary.py,poster)")
    elif selected == 3:
        xbmc.executebuiltin(f"RunScript(special://skin/scripts/deletlib.py)")
    elif selected == 4:
        xbmc.executebuiltin(f"RunScript(special://skin/scripts/localposter.py,select)")
    elif selected == 5:
        xbmc.executebuiltin(f"RunScript(special://skin/scripts/clearlibrary.py,all)")

# ===================== movie参数 - 电影清理逻辑（原逻辑保持不变） =====================
def clean_movie_data():
    """处理movie参数：检查并删除失效电影记录"""
    db_path = get_db_path()
    if not db_path:
        show_error_dialog("未找到MyVideos数据库文件！")
        return

    has_deleted = False
    conn = None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT idMovie, c00, strPath, strFileName FROM movie_view")
        movie_records = cursor.fetchall()
        total_movies = len(movie_records) if len(movie_records) > 0 else get_media_count("movie")
        if total_movies == 0:
            xbmcgui.Dialog().ok("提示", "电影库为空，无需检查！")
            return

        progress = xbmcgui.DialogProgress()
        progress.create("检查失效电影数据", "正在初始化检查...")
        invalid_movies = []

        for idx, (movie_id, c00, strPath, strFileName) in enumerate(movie_records):
            if progress.iscanceled():
                progress.close()
                xbmcgui.Dialog().ok("提示", "检查已取消！")
                return

            percent = int((idx + 1) / total_movies * 100)
            current_info = f"{c00} - {strPath}"
            progress_info = f"当前检查进度{percent}% - 当前检查[{idx+1}/{total_movies}]"
            progress.update(percent, f"{current_info}{chr(10)}{progress_info}")

            folder_exists = strPath and xbmcvfs.exists(strPath)
            file_exists = False

            if folder_exists and strFileName:
                full_file_path = os.path.join(strPath, strFileName)
                translated_full_path = xbmcvfs.translatePath(full_file_path)
                file_exists = xbmcvfs.exists(translated_full_path)
                
            if not folder_exists or not file_exists:
                invalid_movies.append((movie_id, c00, strPath, strFileName))

            xbmc.sleep(10)

        progress.close()

        if not invalid_movies:
            xbmcgui.Dialog().ok("完成", "未发现失效的电影数据！")
            return

        while True:
            delete_options = ["删除所有失效的电影数据"]
            for _, c00, strPath, _ in invalid_movies:
                delete_options.append(f"{c00} - {strPath}")

            if len(delete_options) == 1 and not invalid_movies:
                break

            selected_del = xbmcgui.Dialog().select("选择要删除的失效电影数据", delete_options)
            if selected_del == -1:
                break

            if selected_del == 0:
                if xbmcgui.Dialog().yesno("确认", "确定要删除所有失效的电影数据吗？该操作不可逆！"):
                    deleted_count = 0
                    for movie_id, _, _, _ in invalid_movies:
                        cursor.execute("DELETE FROM movie WHERE idMovie = ?", (movie_id,))
                        deleted_count += 1
                    conn.commit()
                    xbmcgui.Dialog().ok("完成", f"成功删除{deleted_count}条失效电影数据！")
                    invalid_movies = []
                    has_deleted = True
                else:
                    xbmcgui.Dialog().ok("提示", "批量删除已取消！")
            else:
                target_idx = selected_del - 1
                if 0 <= target_idx < len(invalid_movies):
                    movie_id, c00, strPath, _ = invalid_movies[target_idx]
                    if xbmcgui.Dialog().yesno("确认", f"确定要删除【{c00} - {strPath}】吗？该操作不可逆！"):
                        cursor.execute("DELETE FROM movie WHERE idMovie = ?", (movie_id,))
                        conn.commit()
                        xbmcgui.Dialog().ok("完成", f"成功删除：{c00} - {strPath}")
                        del invalid_movies[target_idx]
                        has_deleted = True
                    else:
                        xbmcgui.Dialog().ok("提示", "单个删除已取消！")

    except Exception as e:
        show_error_dialog(f"删除操作失败: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
        if has_deleted:
            xbmc.executebuiltin("ReloadSkin()")
            xbmc.executebuiltin("SetFocus(9000)")
            xbmc.log("执行ReloadSkin()后，设置焦点到9000控件", xbmc.LOGINFO)

# ===================== tvshow参数 - 剧集清理逻辑（原逻辑保持不变） =====================
def clean_tvshow_data():
    """处理tvshow参数：检查并删除失效剧集/季/单集记录"""
    db_path = get_db_path()
    if not db_path:
        show_error_dialog("未找到MyVideos数据库文件！")
        return

    has_deleted = False
    conn = None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT idShow, c00, strPath FROM tvshow_view")
        tvshow_records = cursor.fetchall()
        cursor.execute("SELECT idSeason, showTitle, name, strPath FROM season_view")
        season_records = cursor.fetchall()
        cursor.execute("SELECT idEpisode, c00, c18 FROM episode_view")
        episode_records = cursor.fetchall()
        
        total_tvshows = len(tvshow_records) + len(season_records) if (len(tvshow_records)+len(season_records))>0 else get_media_count("tvshow")
        total_episodes = len(episode_records) if len(episode_records)>0 else get_media_count("episode")
        total_items = total_tvshows + total_episodes
        if total_items == 0:
            xbmcgui.Dialog().ok("提示", "剧集库为空，无需检查！")
            return

        progress = xbmcgui.DialogProgress()
        progress.create("检查失效剧集数据", "正在初始化检查...")
        invalid_tv_data = []
        current_idx = 0

        for show_id, c00, strPath in tvshow_records:
            if progress.iscanceled():
                progress.close()
                xbmcgui.Dialog().ok("提示", "检查已取消！")
                return
            current_idx += 1
            percent = int(current_idx / total_items * 100)
            progress.update(percent, f"检查剧集：{c00} - {strPath}{chr(10)}当前检查进度{percent}% - [{current_idx}/{total_items}]")
            if strPath and not xbmcvfs.exists(strPath):
                invalid_tv_data.append(("show", show_id, f"[剧集]{c00} - {strPath}", strPath, c00, "", ""))
            xbmc.sleep(10)

        for season_id, showTitle, name, strPath in season_records:
            if progress.iscanceled():
                progress.close()
                xbmcgui.Dialog().ok("提示", "检查已取消！")
                return
            current_idx += 1
            percent = int(current_idx / total_items * 100)
            progress.update(percent, f"检查季：{showTitle} {name} - {strPath}{chr(10)}当前检查进度{percent}% - [{current_idx}/{total_items}]")
            if strPath and not xbmcvfs.exists(strPath):
                invalid_tv_data.append(("season", season_id, f"[季]{showTitle} {name} - {strPath}", strPath, showTitle, name, ""))
            xbmc.sleep(10)

        for ep_id, c00, c18 in episode_records:
            if progress.iscanceled():
                progress.close()
                xbmcgui.Dialog().ok("提示", "检查已取消！")
                return
            current_idx += 1
            percent = int(current_idx / total_items * 100)
            progress.update(percent, f"检查单集：{c00} - {c18}{chr(10)}当前检查进度{percent}% - [{current_idx}/{total_items}]")
            if c18 and not xbmcvfs.exists(c18):
                invalid_tv_data.append(("episode", ep_id, f"[单集]{c00} - {c18}", c18, "", "", c00))
            xbmc.sleep(10)

        progress.close()

        if not invalid_tv_data:
            xbmcgui.Dialog().ok("完成", "未发现失效的剧集/季/单集数据！")
            return

        while True:
            delete_options = ["删除所有失效的剧集数据"]
            for _, _, display_name, _, _, _, _ in invalid_tv_data:
                delete_options.append(display_name)

            if len(delete_options) == 1 and not invalid_tv_data:
                break

            selected_del = xbmcgui.Dialog().select("选择要删除的失效剧集/季/单集数据", delete_options)
            if selected_del == -1:
                break

            if selected_del == 0:
                if xbmcgui.Dialog().yesno("确认", "确定要删除所有失效的剧集/季/单集数据吗？该操作不可逆！"):
                    deleted_count = 0
                    for data_type, data_id, _, _, _, _, _ in invalid_tv_data:
                        if data_type == "show":
                            cursor.execute("DELETE FROM tvshow WHERE idShow = ?", (data_id,))
                        elif data_type == "season":
                            cursor.execute("DELETE FROM seasons WHERE idSeason = ?", (data_id,))
                        elif data_type == "episode":
                            cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (data_id,))
                        deleted_count += 1
                    conn.commit()
                    xbmcgui.Dialog().ok("完成", f"成功删除{deleted_count}条失效剧集/季/单集数据！")
                    invalid_tv_data = []
                    has_deleted = True
                else:
                    xbmcgui.Dialog().ok("提示", "批量删除已取消！")
            else:
                target_idx = selected_del - 1
                if 0 <= target_idx < len(invalid_tv_data):
                    data_type, data_id, display_name, _, _, _, _ = invalid_tv_data[target_idx]
                    if xbmcgui.Dialog().yesno("确认", f"确定要删除【{display_name}】吗？该操作不可逆！"):
                        if data_type == "show":
                            cursor.execute("DELETE FROM tvshow WHERE idShow = ?", (data_id,))
                        elif data_type == "season":
                            cursor.execute("DELETE FROM seasons WHERE idSeason = ?", (data_id,))
                        elif data_type == "episode":
                            cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (data_id,))
                        conn.commit()
                        xbmcgui.Dialog().ok("完成", f"成功删除：{display_name}")
                        del invalid_tv_data[target_idx]
                        has_deleted = True
                    else:
                        xbmcgui.Dialog().ok("提示", "单个删除已取消！")

    except Exception as e:
        show_error_dialog(f"删除操作失败: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
        if has_deleted:
            xbmc.executebuiltin("ReloadSkin()")
            xbmc.executebuiltin("SetFocus(9000)")
            xbmc.log("执行ReloadSkin()后，设置焦点到9000控件", xbmc.LOGINFO)

# ===================== 新增 poster参数 - 删除重复、无效海报数据逻辑 =====================
def clean_duplicate_invalid_posters():
    """处理poster参数：分三阶段清理重复和无效的海报数据"""
    db_path = get_db_path()
    if not db_path:
        show_error_dialog("未找到MyVideos数据库文件！")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ================= 阶段一：处理重复数据 =================
        dup_deleted_count = 0
        
        # 查找 c22 字段内容重复的行（排除空值）
        cursor.execute("SELECT c22 FROM movie WHERE c22 IS NOT NULL AND c22 != '' GROUP BY c22 HAVING COUNT(*) > 1")
        duplicate_c22s = [row[0] for row in cursor.fetchall()]
        
        if duplicate_c22s:
            files_to_delete = set()
            
            for c22 in duplicate_c22s:
                # 获取该 c22 对应的所有 idFile
                cursor.execute("SELECT idFile FROM movie WHERE c22 = ?", (c22,))
                id_files = [row[0] for row in cursor.fetchall()]
                
                if len(id_files) > 1:
                    # 到 files 表单查找这些 idFile 的 dateAdded
                    placeholders = ','.join(['?'] * len(id_files))
                    cursor.execute(f"SELECT idFile, dateAdded FROM files WHERE idFile IN ({placeholders})", id_files)
                    file_dates = cursor.fetchall()
                    
                    # 过滤出有 dateAdded 的记录，并按时间降序排序
                    valid_files = [f for f in file_dates if f[1]]
                    if valid_files:
                        valid_files.sort(key=lambda x: x[1], reverse=True)
                        keep_id = valid_files[0][0] # 保留时间最晚的
                        
                        # 其余的加入待删除集合
                        for f_id, _ in valid_files[1:]:
                            files_to_delete.add(f_id)
                    else:
                        # 如果都没有 dateAdded，默认保留第一个，删除其他的
                        keep_id = id_files[0]
                        for f_id in id_files[1:]:
                            files_to_delete.add(f_id)
                            
            if files_to_delete:
                files_to_delete_list = list(files_to_delete)
                placeholders = ','.join(['?'] * len(files_to_delete_list))
                
                # 删除 files 表单中的重复行
                cursor.execute(f"DELETE FROM files WHERE idFile IN ({placeholders})", files_to_delete_list)
                # 删除 movie 表单中对应的行
                cursor.execute(f"DELETE FROM movie WHERE idFile IN ({placeholders})", files_to_delete_list)
                dup_deleted_count = cursor.rowcount
                
        # ================= 阶段二：处理无效数据 =================
        invalid_deleted_count = 0
        
        # 查找包含 BDMV/STREAM/数字.m2ts 的行（不区分大小写）
        cursor.execute("SELECT idFile, c22 FROM movie")
        all_movies = cursor.fetchall()
        
        # 使用正则匹配 BDMV/STREAM/数字.m2ts
        pattern = re.compile(r'BDMV/STREAM/\d+\.m2ts', re.IGNORECASE)
        invalid_id_files = []
        
        for id_file, c22 in all_movies:
            if c22 and pattern.search(c22):
                invalid_id_files.append(id_file)
                
        if invalid_id_files:
            placeholders = ','.join(['?'] * len(invalid_id_files))
            # 删除 files 表单中的无效行
            cursor.execute(f"DELETE FROM files WHERE idFile IN ({placeholders})", invalid_id_files)
            # 删除 movie 表单中对应的行
            cursor.execute(f"DELETE FROM movie WHERE idFile IN ({placeholders})", invalid_id_files)
            invalid_deleted_count = cursor.rowcount

        # 提交所有数据库更改
        conn.commit()
        
        # ================= 阶段三：结果展示 =================
        xbmcgui.Dialog().ok(
            "清理完成", 
            f"已删除重复电影海报数据 {dup_deleted_count} 部，删除无效电影海报数据 {invalid_deleted_count} 部。"
        )
        
        # 如果发生了删除操作，刷新皮肤并重置焦点
        if dup_deleted_count > 0 or invalid_deleted_count > 0:
            xbmc.executebuiltin("ReloadSkin()")
            xbmc.executebuiltin("SetFocus(9000)")
            xbmc.log("执行ReloadSkin()后，设置焦点到9000控件", xbmc.LOGINFO)

    except Exception as e:
        show_error_dialog(f"清理重复/无效海报数据失败: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# ===================== 原all参数 - 全量清理逻辑（原逻辑保持不变） =====================
def clean_all_library():
    """原有的全量删除媒体库逻辑"""
    has_deleted = False

    try:
        userdata_path = xbmcvfs.translatePath("special://userdata")
    except AttributeError:
        userdata_path = xbmc.translatePath("special://userdata")

    database_dir = os.path.join(userdata_path, "Database")
    source_db = xbmcvfs.translatePath("special://skin/scripts/MyVideos131.db")
    target_db = os.path.join(database_dir, "MyVideos131.db")

    try:
        if not xbmcgui.Dialog().yesno(
            "警告",
            "该操作将删除全部的电影和剧集的海报信息，并且不可逆！\n 您确定要继续吗？",
            nolabel="我再想想",
            yeslabel="确认删除"
        ):
            xbmcgui.Dialog().ok("提示", "操作已取消")
            return

        deleted_files = []
        if os.path.exists(database_dir):
            for filename in os.listdir(database_dir):
                if "MyVideos" in filename:
                    file_path = os.path.join(database_dir, filename)
                    if os.path.isfile(file_path) and os.access(file_path, os.W_OK):
                        os.remove(file_path)
                        deleted_files.append(filename)
        
        if deleted_files:
            xbmcgui.Dialog().ok("完成", f"已成功删除以下文件：\n{chr(10).join(deleted_files)}\n\n电影和剧集海报已清除！")
            has_deleted = True
            
            if xbmcvfs.exists(source_db):
                if xbmcvfs.copy(source_db, target_db):
                    xbmc.log(f"成功复制备用数据库：{source_db} -> {target_db}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"复制数据库失败：{source_db} 无法复制到 {target_db}", xbmc.LOGERROR)
            else:
                xbmc.log(f"备用数据库源文件不存在：{source_db}", xbmc.LOGERROR)
            
            xbmc.sleep(500)
            
            if xbmc.getCondVisibility("!Library.HasContent(Movies)"):
                xbmc.executebuiltin("Skin.SetString(movielib,0)")
            if xbmc.getCondVisibility("!Library.HasContent(TVShows)"):
                xbmc.executebuiltin("Skin.SetString(tvshowlib,0)")
        else:
            xbmcgui.Dialog().ok("提示", "你的媒体资料库是空的，无需进行清理。")
        
        if has_deleted:
            xbmc.executebuiltin("ReloadSkin()")
            xbmc.executebuiltin("SetFocus(9000)")
            xbmc.log("执行ReloadSkin()后，设置焦点到9000控件", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"清理/复制媒体库失败: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"操作失败: {str(e)}\n\n请查看Kodi日志获取详细信息")
        if has_deleted:
            xbmc.executebuiltin("ReloadSkin()")
            xbmc.executebuiltin("SetFocus(9000)")
            xbmc.log("执行ReloadSkin()后，设置焦点到9000控件", xbmc.LOGINFO)

# ===================== 主入口逻辑 =====================
if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    if not args:
        main_menu()
    else:
        param = args[0].lower()
        if param == "all":
            clean_all_library()
        elif param == "movie":
            clean_movie_data()
        elif param == "tvshow":
            clean_tvshow_data()
        elif param == "poster":
            # 新增的 poster 参数处理
            clean_duplicate_invalid_posters()
        else:
            show_error_dialog(f"无效参数：{param}\n支持的参数：all/movie/tvshow/poster")