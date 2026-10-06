# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import xbmcvfs
import json
import os
import sqlite3
from datetime import datetime
import time

def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log(f"[HistoryRecordScript] {msg}", level)

def get_skin_setting():
    """获取历史记录数量限制，默认为50"""
    try:
        val = xbmc.getInfoLabel('Skin.String(historynum)')
        if val and val.isdigit():
            return int(val)
    except:
        pass
    return 50

def get_current_time_formatted():
    """
    使用time.strftime直接获取标准的24小时格式时间
    无需复杂的解析逻辑，直接从系统时间获取
    """
    # 直接使用time.strftime获取当前时间的24小时格式
    current_time = time.strftime("%H:%M:%S")
    current_date = time.strftime("%Y-%m-%d")
    return current_date, current_time

def get_file_id_from_db(filename):
    """
    从数据库中获取文件的 idFile
    逻辑：在files表中找strFilename，如果有多个取lastPlayed最新的，然后执行Skin.SetString(historyid, idFile)
    """
    db_path = xbmcvfs.translatePath('special://userdata/Database/MyVideos131.db')
    if not xbmcvfs.exists(db_path):
        return None
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 在files表中查找文件
        query = "SELECT idFile, lastPlayed FROM files WHERE strFilename = ?"
        cursor.execute(query, (filename,))
        rows = cursor.fetchall()
        
        if not rows:
            return None
            
        target_idFile = None
        
        if len(rows) == 1:
            target_idFile = rows[0][0]
        else:
            # 如果找到多行，选取 lastPlayed 最靠后的那一行
            latest_time = ""
            for row in rows:
                last_played = row[1] if row[1] else ""
                if last_played > latest_time:
                    latest_time = last_played
                    target_idFile = row[0]
        
        if target_idFile:
            # 2. 设置皮肤变量
            xbmc.executebuiltin(f'Skin.SetString(historyid,{target_idFile})')
            log(f"Set Skin.String(historyid) to: {target_idFile}")
            return target_idFile

    except Exception as e:
        log(f"Database Error: {e}", xbmc.LOGERROR)
    finally:
        if conn:
            conn.close()
            
    return None

def clean_old_records(data, limit):
    """删除最早的记录直到数量小于限制"""
    while len(data) > limit:
        earliest_idx = -1
        earliest_dt = None
        
        # 寻找最早的条目
        for i, item in enumerate(data):
            date_str = item.get('date', '')
            time_str = item.get('time', '')
            try:
                # 组合日期时间进行比对
                date_parts = date_str.split('-')
                time_parts = time_str.split(':')
                if len(date_parts) == 3 and len(time_parts) == 3:
                    year = int(date_parts[0])
                    month = int(date_parts[1])
                    day = int(date_parts[2])
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2])
                    dt = datetime(year, month, day, hour, minute, second)
                    if earliest_dt is None or dt < earliest_dt:
                        earliest_dt = dt
                        earliest_idx = i
            except (ValueError, TypeError):
                continue
        
        if earliest_idx != -1:
            log(f"Removing old record: {data[earliest_idx].get('title')}")
            data.pop(earliest_idx)
        else:
            # 如果无法解析时间，默认删除最后一个
            data.pop()
            break

def handle_exit_logic():
    """
    当带有"exit"参数运行脚本时的处理逻辑
    优化：
    1. 增加1秒延时
    2. 如果数据库中无bookmark记录，则清空JSON中的进度信息
    """
    log("Starting exit logic processing...")
    
    # --- 优化开始：延时1秒 (1000毫秒) ---
    log("Waiting 1 second before processing exit logic...")
    xbmc.sleep(800)
    log("Delay finished. Proceeding with exit logic.")
    # --- 优化结束 ---

    # 1. 获取Skin.String(historypath)的值
    log("Step 1: Getting history path from skin settings...")
    history_path = xbmc.getInfoLabel('Skin.String(historypath)')
    if not history_path:
        log("Skin.String(historypath) is empty. Cannot execute exit logic.", xbmc.LOGWARNING)
        return
    log(f"Got history path: {history_path}")

    # 2. 加载lastPlayed.json文件
    log("Step 2: Loading lastPlayed.json file...")
    json_path = xbmcvfs.translatePath('special://profile/addon_data/skin.yoplayer.infuse/lastPlayed.json')
    data = []
    if xbmcvfs.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            log(f"Successfully loaded JSON file. Total entries: {len(data)}")
        except Exception as e:
            log(f"Error reading JSON file: {e}", xbmc.LOGERROR)
            return
    else:
        log("JSON file does not exist", xbmc.LOGWARNING)
        return

    # 3. 在数据中查找匹配的条目
    log("Step 3: Searching for matching entry in JSON data...")
    target_index = -1
    for i, item in enumerate(data):
        # 检查条目中的'file'字段是否包含history_path
        if history_path in item.get('file', ''):
            target_index = i
            log(f"Found matching entry at index {i}: {item.get('title')}")
            log(f"Matched file path: {item.get('file')}")
            break # 找到第一个（最靠前的）就停止
    
    if target_index == -1:
        log("No matching entry found in JSON file", xbmc.LOGWARNING)
        return

    # 4. 获取Skin.String(historyid)的值
    log("Step 4: Getting history ID from skin settings...")
    history_id = xbmc.getInfoLabel('Skin.String(historyid)')
    if not history_id or not history_id.isdigit():
        log(f"historyid skin setting is not valid: '{history_id}'", xbmc.LOGWARNING)
        return
    history_id = int(history_id)
    log(f"Using history_id: {history_id}")

    # 5. 查询数据库中的bookmark表
    log("Step 5: Connecting to database and querying bookmark table...")
    db_path = xbmcvfs.translatePath('special://userdata/Database/MyVideos131.db')
    if not xbmcvfs.exists(db_path):
        log("Database file does not exist", xbmc.LOGWARNING)
        return
    
    conn = None
    try:
        log(f"Database path: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询bookmark表中idFile等于history_id的记录
        log(f"Executing query: SELECT timeInSeconds, totalTimeInSeconds FROM bookmark WHERE idFile = {history_id}")
        query = "SELECT timeInSeconds, totalTimeInSeconds FROM bookmark WHERE idFile = ?"
        cursor.execute(query, (history_id,))
        row = cursor.fetchone()
        
        # 6. 更新JSON数据中的resume_time和total_time字段
        log("Step 6: Updating JSON entry with bookmark data...")
        
        if row:
            # 情况A：找到了bookmark记录
            time_in_seconds = row[0] if row[0] is not None else 0
            total_time_in_seconds = row[1] if row[1] is not None else 0
            log(f"Retrieved bookmark data - timeInSeconds: {time_in_seconds}, totalTimeInSeconds: {total_time_in_seconds}")
            
            data[target_index]["resume_time"] = str(time_in_seconds)
            data[target_index]["total_time"] = str(total_time_in_seconds)
            
            log(f"Entry {target_index} updated with bookmark data:")
            log(f" New resume_time: {time_in_seconds}")
            log(f" New total_time: {total_time_in_seconds}")
        else:
            # 情况B：没有找到bookmark记录 (优化点：清空进度)
            log(f"No bookmark entry found for idFile: {history_id}. Clearing progress fields.")
            
            original_resume = data[target_index].get("resume_time", "not_set")
            original_total = data[target_index].get("total_time", "not_set")
            
            # 将进度字段清空
            data[target_index]["resume_time"] = ""
            data[target_index]["total_time"] = ""
            
            log(f"Entry {target_index} progress cleared:")
            log(f" Original resume_time: {original_resume} -> New resume_time: '' (Empty)")
            log(f" Original total_time: {original_total} -> New total_time: '' (Empty)")

        # 7. 保存更新后的JSON文件
        log("Step 7: Saving updated JSON file...")
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log("JSON file updated successfully after exit logic.")
            log("Exit logic completed successfully.")
        except Exception as e:
            log(f"Error saving JSON after exit logic: {e}", xbmc.LOGERROR)
            
    except Exception as e:
        log(f"Database error in exit logic: {e}", xbmc.LOGERROR)
    finally:
        if conn:
            conn.close()
            log("Database connection closed.")

def remove_title_prefix(title):
    """
    移除标题中从[COLOR yellow]开头至最后一个[/COLOR]结束的所有颜色标签前缀
    例如: "[COLOR yellow][06-29 12:18][/COLOR][COLOR white][非][/COLOR]Actual Title"
    -> "Actual Title"
    """
    import re
    # 匹配从 [COLOR yellow] 开始到字符串末尾的最后一个 [/COLOR] 为止的所有内容
    # 并将其替换为空字符串
    # 这样可以一次性移除所有嵌套或连续的颜色标签
    pattern = r'\[COLOR\s+yellow\].*\[/COLOR\]'
    cleaned_title = re.sub(pattern, '', title)
    return cleaned_title.strip()

def main():
    # 1. 检查参数
    import sys
    if len(sys.argv) < 2:
        log("Script called without arguments. Exiting.")
        return

    if sys.argv[1] == 'exit':
        handle_exit_logic()
        return
    elif sys.argv[1] != 'start':
        log("Script called with unknown argument. Exiting.")
        return

    log("Script started with 'start' parameter.")

    # 路径与文件准备
    json_path = xbmcvfs.translatePath('special://profile/addon_data/skin.yoplayer.infuse/lastPlayed.json')
    json_dir = os.path.dirname(json_path)
    
    if not xbmcvfs.exists(json_dir):
        xbmcvfs.mkdirs(json_dir)
        
    data = []
    if xbmcvfs.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            log(f"Loaded existing JSON file with {len(data)} entries.")
        except Exception as e:
            log(f"Error loading JSON file: {e}. Creating new empty list.")
            data = []
    else:
        # 文件不存在，创建空列表
        data = []
        log("Created new empty JSON data list.")

    # 获取播放器信息
    filename_and_path = xbmc.getInfoLabel('Player.Filenameandpath')
    filename = xbmc.getInfoLabel('Player.Filename')
    title = xbmc.getInfoLabel('Player.Title')
    
    if not filename_and_path:
        log("No file playing. Exiting.")
        return

    # 执行Skin.SetString(historypath, Player.Filenameandpath)
    xbmc.executebuiltin(f'Skin.SetString(historypath,{filename_and_path})')
    log(f"Set Skin.String(historypath) to: {filename_and_path}")

    # 获取限制并清理旧记录
    limit = get_skin_setting()
    log(f"History limit set to: {limit}")

    if len(data) > limit:
        clean_old_records(data, limit)
        log(f"After cleaning, JSON now has {len(data)} entries.")

    # 获取当前时间和日期（使用简化的time.strftime方法）
    current_date, current_time = get_current_time_formatted()
    log(f"Current date: {current_date}, Current time: {current_time}")

    # 第2步逻辑：判断内容类型并处理
    is_movie = xbmc.getCondVisibility('VideoPlayer.Content(Movies)')
    is_episode = xbmc.getCondVisibility('VideoPlayer.Content(Episodes)')
    
    # 查找当前文件是否已存在于记录中
    target_index = -1
    for i, item in enumerate(data):
        if filename_and_path in item.get('file', ''):
            target_index = i
            log(f"Found existing record at index {i}: {item.get('title')}")
            break

    # 移除标题前缀 - 应用到所有类型的内容
    cleaned_title = remove_title_prefix(title)
    
    # 构建新条目
    new_entry = {
        "title": cleaned_title,  # 使用处理过的标题
        "file": filename_and_path,
        "video": filename_and_path,
        "date": current_date,  # 使用简化的时间获取方法
        "time": current_time,  # 使用简化的时间获取方法
        "resume_time": " ",
        "total_time": " "
    }

    if is_movie:
        # 情况1：电影
        log("Processing movie content type.")
        new_entry.update({
            "source": "电影库",
            "id": int(xbmc.getInfoLabel('VideoPlayer.DBID') or 0),
            "type": "movie",
            "thumbnail": xbmc.getInfoLabel('Player.Art(poster)'),
            "fanart": xbmc.getInfoLabel('Player.Art(fanart)'),
            "show": " ",
            "season": "",
            "episode": ""
        })
    elif is_episode:
        # 情况2：剧集
        log("Processing episode content type.")
        tvshow_poster = xbmc.getInfoLabel('Player.Art(tvshow.poster)')
        poster = xbmc.getInfoLabel('Player.Art(poster)')
        thumbnail_to_use = tvshow_poster if tvshow_poster else poster
        
        new_entry.update({
            "source": "剧集库",
            "tvshowdbid": int(xbmc.getInfoLabel('VideoPlayer.TvShowDBID') or 0),
            "type": "episode",
            "thumbnail": thumbnail_to_use,
            "icon": xbmc.getInfoLabel('Player.Icon'),
            "show": xbmc.getInfoLabel('VideoPlayer.TVShowTitle'),
            "season": int(xbmc.getInfoLabel('VideoPlayer.Season') or 0),
            "episode": int(xbmc.getInfoLabel('VideoPlayer.Episode') or 0)
        })
    else:
        # 情况3：普通文件
        log("Processing file content type.")
        new_entry.update({
            "source": "文件",
            "id": 0,
            "type": "file",
            "thumbnail": xbmc.getInfoLabel('Player.Art(tvshow.poster)'),
            "fanart": xbmc.getInfoLabel('Player.Art(fanart)'),
            "show": xbmc.getInfoLabel('VideoPlayer.TVShowTitle'),
            "season": int(xbmc.getInfoLabel('VideoPlayer.Season') or 0),
            "episode": int(xbmc.getInfoLabel('VideoPlayer.Episode') or 0)
        })

    if target_index == -1:
        # 未找到现有记录，添加到开头
        log(f"Adding new record: {new_entry['title']}")
        data.insert(0, new_entry)
    else:
        # 找到了现有记录，更新它的信息
        log(f"Updating existing record: {new_entry['title']}")
        data[target_index].update({
            "title": new_entry["title"],  # 使用处理过的标题
            "date": new_entry["date"],  # 使用简化的时间获取方法
            "time": new_entry["time"],  # 使用简化的时间获取方法
            "season": new_entry.get("season"),
            "episode": new_entry.get("episode"),
            "show": new_entry.get("show"),
            "thumbnail": new_entry.get("thumbnail"),
            "icon": new_entry.get("icon"),
            "fanart": new_entry.get("fanart")
        })

    # 再次检查限制并清理（以防添加后超出限制）
    if len(data) > limit:
        clean_old_records(data, limit)
        log(f"After adding/updating, JSON now has {len(data)} entries after final cleanup.")

    # 保存文件
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log("JSON file saved successfully.")
    except Exception as e:
        log(f"Error saving JSON: {e}", xbmc.LOGERROR)

    # 获取数据库ID并设置皮肤变量
    file_id = get_file_id_from_db(filename)
    if file_id is None:
        log("Could not find file ID in database.", xbmc.LOGWARNING)

    log("Script finished with 'start' parameter.")

if __name__ == '__main__':
    main()