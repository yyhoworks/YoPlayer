# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import json
import sqlite3
import os
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import threading
import time

LOG_PREFIX = "[TVJumpScript] "

RECORD_TYPE_START = "start"
RECORD_TYPE_END = "end"
CREDITS_COOLDOWN_DURATION = 10  # 片尾处理冷却时间（秒）
NEW_EPISODE_COOLDOWN_DURATION = 10  # 新剧集检测冷却时间（秒）

# 默认片尾时间配置
DEFAULT_CREDITS_END_SECONDS = 12  # 当没有找到片尾记录时，默认片尾时间（秒）
DEFAULT_CREDITS_TRIGGER_THRESHOLD = 15  # 当剩余时间小于这个阈值时，启用默认片尾逻辑（秒）

def format_seconds(seconds):
    """将秒数格式化为 HH:MM:SS 或 MM:SS 字符串。"""
    if seconds is None:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def show_notification(heading, message, icon=xbmcgui.NOTIFICATION_INFO, time=3000):
    """显示一个通知弹窗。如果 Skin.HasSetting(tvshowinfo) 为 true，则不显示。"""
    if not xbmc.getCondVisibility("Skin.HasSetting(tvshowjumpinfo)"):
        xbmcgui.Dialog().notification(heading, message, icon, time)

def show_force_notification(heading, message, icon=xbmcgui.NOTIFICATION_INFO, time=3000):
    """强制显示一个通知弹窗，不受Skin设置影响。专门用于记录和删除通知。"""
    xbmcgui.Dialog().notification(heading, message, icon, time)

def log(message, level=xbmc.LOGINFO):
    """将日志信息写入Kodi日志。"""
    xbmc.log(f"{LOG_PREFIX}{message}", level)

def format_xml(elem):
    """将XML元素格式化为带缩进的漂亮字符串。"""
    try:
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        xml_str = reparsed.toprettyxml(indent="  ")
        return "\n".join([line for line in xml_str.split("\n") if line.strip()])
    except Exception as e:
        log(f"XML格式化失败: {e}", xbmc.LOGERROR)
        raise

def translate_path(path):
    """将Kodi的特殊路径（如 special://home）转换为系统绝对路径。"""
    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        return xbmc.translatePath(path)

def get_xml_file_path():
    """获取记录文件 tvshowrecord.xml 的路径。"""
    is_linux = xbmc.getCondVisibility("System.Platform.Linux")
    build_version = xbmc.getInfoLabel("System.BuildVersion")
    is_coreelec = is_linux and "CoreELEC" in build_version
    
    xml_dir = "/storage/tvshows/" if is_coreelec else translate_path("special://home/userdata/tvshows/")
    
    if not xbmcvfs.exists(xml_dir):
        xbmcvfs.mkdirs(xml_dir)
    
    return os.path.join(xml_dir, "tvshowrecord.xml")

def get_database_path():
    """获取视频数据库文件的路径。"""
    db_path = translate_path("special://home/userdata/Database/MyVideos131.db")
    return db_path

def get_episode_info(dbid):
    """从数据库获取剧集信息（idShow, idSeason, c13）。"""
    db_path = get_database_path()
    if not xbmcvfs.exists(db_path):
        log(f"数据库文件不存在: {db_path}", xbmc.LOGERROR)
        return None, None, None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = """
        SELECT idShow, idSeason, c13
        FROM episode_view
        WHERE idEpisode = ?
        """
        cursor.execute(query, (dbid,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            id_show, id_season, c13 = result
            # 尝试将c13转换为整数
            try:
                episode_number = int(float(c13))
            except (ValueError, TypeError):
                episode_number = None
                log(f"c13字段无法转换为整数: {c13}")
            
            return id_show, id_season, episode_number
        else:
            log(f"在数据库中未找到 idEpisode={dbid} 的记录", xbmc.LOGERROR)
            return None, None, None
    except Exception as e:
        log(f"查询数据库失败: {e}", xbmc.LOGERROR)
        return None, None, None

def get_next_episode_info(id_show, id_season, current_episode_number):
    """从数据库获取下一集的信息。"""
    db_path = get_database_path()
    if not xbmcvfs.exists(db_path):
        log(f"数据库文件不存在: {db_path}", xbmc.LOGERROR)
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询下一集的idEpisode
        query = """
        SELECT idEpisode
        FROM episode_view
        WHERE idShow = ? AND idSeason = ? AND CAST(c13 AS INTEGER) = ?
        """
        next_episode_number = current_episode_number + 1
        cursor.execute(query, (id_show, id_season, next_episode_number))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return result[0]
        else:
            log(f"未找到下一集: idShow={id_show}, idSeason={id_season}, EpisodeNumber={next_episode_number}")
            return None
    except Exception as e:
        log(f"查询数据库失败: {e}", xbmc.LOGERROR)
        return None

def analyze_file_path(file_path):
    """分析文件路径结构，判断是否为电视剧"""
    if not file_path:
        return False
    
    # 获取文件名和路径
    file_name = os.path.basename(file_path)
    dir_path = os.path.dirname(file_path)
    
    # 检查文件名是否包含剧集编号
    # 匹配 E111 这种格式
    episode_pattern = re.compile(r'[Ee](\d{2,4})', re.IGNORECASE)
    if episode_pattern.search(file_name):
        return True
    
    # 检查路径中是否包含 Season 或 Season 缩写
    season_pattern = re.compile(r'[Ss]eason|Season|\b[Ss](\d{1,2})\b', re.IGNORECASE)
    if season_pattern.search(dir_path):
        return True
    
    # 检查文件夹名是否包含年份和 tmdb 标识（表明这是电视剧整理结构）
    folder_name = os.path.basename(dir_path)
    tmdb_pattern = re.compile(r'tmdb-\d+', re.IGNORECASE)
    year_pattern = re.compile(r'\((\d{4})\)|\[.*?(\d{4}).*?\]')
    
    if tmdb_pattern.search(folder_name) and year_pattern.search(folder_name):
        return True
    
    # 检查路径结构是否符合电视剧格式
    # 如 .../剧名/Season N/... 或 .../剧名/S01/...
    parent_dir = os.path.dirname(dir_path)
    grandparent_dir = os.path.dirname(parent_dir)
    
    # 检查父目录是否包含 Season 信息
    parent_basename = os.path.basename(parent_dir)
    if season_pattern.search(parent_basename):
        return True
    
    return False

def is_playing_episodes_cached():
    """判断当前是否正在播放剧集，使用缓存减少重复日志"""
    # Kodi 内置条件
    cond1 = xbmc.getCondVisibility("VideoPlayer.Content(Episodes)")
    
    # 从文件路径分析
    file_path = xbmc.getInfoLabel("Player.FilenameAndPath")
    cond2 = analyze_file_path(file_path)
    
    # 从标题分析
    title = xbmc.getInfoLabel("Player.Title")
    has_season = bool(re.search(r'S\d+', title, re.IGNORECASE))
    # 修改E+数字的匹配，允许1-4位数字
    has_episode = bool(re.search(r'E\d{1,4}', title, re.IGNORECASE))
    cond3 = has_season and has_episode
    
    # 从文件夹路径分析
    folder_path = xbmc.getInfoLabel("Player.Folderpath")
    last_dir = os.path.basename(os.path.normpath(folder_path)) if folder_path else ""
    cond4 = bool(re.search(r'\d+集', last_dir))
    
    result = cond1 or cond2 or cond3 or cond4
    
    return result

def is_playing_episodes():
    """判断当前是否正在播放剧集，带日志输出"""
    # Kodi 内置条件
    cond1 = xbmc.getCondVisibility("VideoPlayer.Content(Episodes)")
    
    # 从文件路径分析
    file_path = xbmc.getInfoLabel("Player.FilenameAndPath")
    cond2 = analyze_file_path(file_path)
    
    # 从标题分析
    title = xbmc.getInfoLabel("Player.Title")
    has_season = bool(re.search(r'S\d+', title, re.IGNORECASE))
    # 修改E+数字的匹配，允许1-4位数字
    has_episode = bool(re.search(r'E\d{1,4}', title, re.IGNORECASE))
    cond3 = has_season and has_episode
    
    # 从文件夹路径分析
    folder_path = xbmc.getInfoLabel("Player.Folderpath")
    last_dir = os.path.basename(os.path.normpath(folder_path)) if folder_path else ""
    cond4 = bool(re.search(r'\d+集', last_dir))
    
    result = cond1 or cond2 or cond3 or cond4
    
    if result:
        log(f"检测到电视剧内容: Kodi内置={cond1}, 路径分析={cond2}, 标题分析={cond3}, 文件夹分析={cond4}")
    else:
        log(f"未检测到电视剧内容: Kodi内置={cond1}, 路径分析={cond2}, 标题分析={cond3}, 文件夹分析={cond4}")
        log(f"文件路径: {file_path}")
        log(f"标题: {title}")
        log(f"文件夹: {folder_path}")
    
    return result

def parse_time_string(time_str):
    """将 "HH:MM:SS" 或 "MM:SS" 格式的字符串解析为总秒数。"""
    if not time_str:
        return 0
    match = re.match(r'^(?:(\d+):)?(\d+):(\d+)$', time_str)
    if not match:
        log(f"时间格式无效: '{time_str}'", xbmc.LOGERROR)
        return 0
    hours, minutes, seconds = match.groups()
    hours = int(hours) if hours else 0
    return hours * 3600 + int(minutes) * 60 + int(seconds)

def find_record_in_xml(xml_tree, folder_path, record_type, id_show=None, id_season=None):
    """在XML树中查找指定条件的记录值。"""
    if xml_tree is None:
        return None
        
    for record in xml_tree.getroot().findall("record"):
        # 检查是否是基于路径的记录
        if record.get("path") and record.get("path") == folder_path and record.get("type") == record_type:
            try:
                # 支持逗号分隔的多时间点格式，返回第一个值
                text_value = record.text
                if text_value and ',' in text_value:
                    time_values = [int(t.strip()) for t in text_value.split(',') if t.strip().isdigit()]
                    if time_values:
                        return time_values[0]  # 返回第一个时间点
                else:
                    return int(text_value) if text_value and text_value.isdigit() else None
            except (ValueError, TypeError, AttributeError):
                log(f"记录值错误: Path='{folder_path}', Type='{record_type}', Value='{record.text}'", xbmc.LOGERROR)
        # 检查是否是基于数据库ID的记录
        elif id_show is not None and id_season is not None:
            if (record.get("idShow") == str(id_show) and 
                record.get("idSeason") == str(id_season) and 
                record.get("type") == record_type):
                try:
                    # 支持逗号分隔的多时间点格式，返回第一个值
                    text_value = record.text
                    if text_value and ',' in text_value:
                        time_values = [int(t.strip()) for t in text_value.split(',') if t.strip().isdigit()]
                        if time_values:
                            return time_values[0]  # 返回第一个时间点
                    else:
                        return int(text_value) if text_value and text_value.isdigit() else None
                except (ValueError, TypeError, AttributeError):
                    log(f"记录值错误: idShow='{id_show}', idSeason='{id_season}', Type='{record_type}', Value='{record.text}'", xbmc.LOGERROR)
    return None

def find_all_start_records_in_xml(xml_tree, folder_path, id_show=None, id_season=None):
    """在XML树中查找指定条件的所有片头记录值。"""
    if xml_tree is None:
        return []
    
    results = []
    for record in xml_tree.getroot().findall("record"):
        # 检查是否是基于路径的记录
        if record.get("path") and record.get("path") == folder_path and record.get("type") == RECORD_TYPE_START:
            try:
                text_value = record.text
                if text_value:
                    # 解析可能包含多个时间的逗号分隔字符串
                    time_values = [int(t.strip()) for t in text_value.split(',') if t.strip().isdigit()]
                    results.extend(time_values)
            except (ValueError, TypeError, AttributeError):
                log(f"记录值错误: Path='{folder_path}', Type='{RECORD_TYPE_START}', Value='{record.text if hasattr(record, 'text') else 'None'}'", xbmc.LOGERROR)
        # 检查是否是基于数据库ID的记录
        elif id_show is not None and id_season is not None:
            if (record.get("idShow") == str(id_show) and 
                record.get("idSeason") == str(id_season) and 
                record.get("type") == RECORD_TYPE_START):
                try:
                    text_value = record.text
                    if text_value:
                        # 解析可能包含多个时间的逗号分隔字符串
                        time_values = [int(t.strip()) for t in text_value.split(',') if t.strip().isdigit()]
                        results.extend(time_values)
                except (ValueError, TypeError, AttributeError):
                    log(f"记录值错误: idShow='{id_show}', idSeason='{id_season}', Type='{RECORD_TYPE_START}', Value='{record.text if hasattr(record, 'text') else 'None'}'", xbmc.LOGERROR)
    return results

def execute_sub_script_delayed():
    """延迟3秒执行字幕脚本"""
    def delayed_execution():
        time.sleep(3)
        xbmc.executebuiltin("RunScript(special://skin/scripts/epsub.py,sub)")
    
    thread = threading.Thread(target=delayed_execution)
    thread.daemon = True
    thread.start()

def play_next_episode_db(dbid, id_show, id_season, current_episode_number):
    """使用数据库信息播放下一集。"""
    # 获取下一集信息
    next_dbid = get_next_episode_info(id_show, id_season, current_episode_number)
    
    if next_dbid is None:
        log("未找到下一集，可能是季末或剧终。")
        show_notification("提示", "当前剧集已全部播放完毕", xbmcgui.NOTIFICATION_INFO, 5000)
        return False
    
    # 先停止当前播放
    xbmc.Player().stop()
    time.sleep(0.5)  # 等待当前播放停止
    
    # 使用JSON-RPC播放下一集
    try:
        params = {
            "item": {
                "episodeid": next_dbid
            }
        }
        result = xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Player.Open",
            "params": params,
            "id": 1
        }))
        
        response = json.loads(result)
        if "error" in response:
            log(f"播放下一集失败: {response['error']['message']}", xbmc.LOGERROR)
            return False
        else:
            log(f"成功播放下一集 (DBID: {next_dbid})")
            execute_sub_script_delayed()
            return True
    except Exception as e:
        log(f"调用JSON-RPC播放下一集时出错: {e}", xbmc.LOGERROR)
        return False

def handle_credits_phase_db_silent(player_or_monitor, end_seconds, dbid, id_show, id_season, current_episode_number):
    """
    静默处理片尾逻辑，使用数据库信息播放下一集。
    """
    log(f"静默处理片尾阶段 (剩余时间 ≤ {end_seconds}s) - 数据库模式")
    
    if hasattr(player_or_monitor, '_start_credits_cooldown'):
        player_or_monitor._start_credits_cooldown()
    
    success = play_next_episode_db(dbid, id_show, id_season, current_episode_number)
    if not success:
        # 如果数据库方法失败，回退到文件系统方法
        play_next_episode_silent(player_or_monitor.player if hasattr(player_or_monitor, 'player') else player_or_monitor)

def play_next_episode_silent(player):
    """
    静默尝试播放下一集，直接采用文件导航方式。
    """
    # 获取当前播放的文件名和路径信息
    current_filename = xbmc.getInfoLabel("Player.Filename")
    folder_path = xbmc.getInfoLabel("Player.Folderpath")
    
    if not current_filename or not folder_path:
        log("无法获取当前播放的文件名或路径，无法执行备用方案。", xbmc.LOGERROR)
        return False
        
    log(f"静默尝试播放下一集: CurrentFile='{os.path.join(folder_path, current_filename)}'")
    
    # 先停止当前播放
    player.stop()
    time.sleep(0.5)  # 等待当前播放停止
    
    # 直接使用文件名匹配方案
    next_episode_path = get_next_episode_path(current_filename, folder_path)
    
    if next_episode_path:
        log(f"使用文件导航方案播放: {next_episode_path}")
        player.play(next_episode_path)
        execute_sub_script_delayed()
        return True
    else:
        log("文件导航方案失败，无法播放下一集。")
        show_notification("提示", "无法找到或播放下一集", xbmcgui.NOTIFICATION_INFO, 5000)
        return False

def get_next_episode_path(current_filename, folder_path):
    """
    根据当前文件名和文件夹路径，查找下一集的文件路径。
    采用多级策略，从最精确到最通用。
    """
    log(f"尝试查找下一集: CurrentFilename='{current_filename}', FolderPath='{folder_path}'")
    
    # --- 关键修正：分离文件名和扩展名 ---
    # 只对文件名主体部分进行分析，避免匹配到扩展名中的数字
    name_without_ext, ext = os.path.splitext(current_filename)
    log(f"分离文件名和扩展名: '{name_without_ext}', '{ext}'")
    
    # 定义视频文件扩展名列表
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.vob', '.iso']
    video_ext_lower = [ext.lower() for ext in video_extensions]

    # 从目录中获取所有文件
    dirs, all_files = xbmcvfs.listdir(folder_path)
    video_files = []
    for file in all_files:
        _, file_ext = os.path.splitext(file)
        if file_ext.lower() in video_ext_lower:
            video_files.append(file)
    log(f"目录中的视频文件: {video_files}")

    # --- 策略 1: 查找 SxxExx 或 Exx 格式 (最高优先级) ---
    sxxexx_match = re.search(r'S(\d+)E(\d+)', name_without_ext, re.IGNORECASE)
    if sxxexx_match:
        season_num = int(sxxexx_match.group(1))
        episode_num = int(sxxexx_match.group(2))
        next_episode_num = episode_num + 1
        episode_digits = len(sxxexx_match.group(2))
        next_pattern = re.compile(f"S{season_num:02d}E{next_episode_num:0{episode_digits}d}", re.IGNORECASE)
        log(f"查找模式: {next_pattern.pattern} (SxxExx格式)")
        
        # 优先查找相同扩展名的文件
        same_ext_files = [f for f in video_files if f.lower().endswith(ext.lower())]
        for filename in same_ext_files:
            if next_pattern.search(filename):
                next_file_path = os.path.join(folder_path, filename)
                log(f"找到相同扩展名的下一集: {next_file_path}")
                return next_file_path
        
        # 如果没找到相同扩展名的，再查找所有视频文件
        for filename in video_files:
            if next_pattern.search(filename):
                next_file_path = os.path.join(folder_path, filename)
                log(f"找到下一集: {next_file_path}")
                return next_file_path
        log("在 SxxExx/Exx 模式下未找到下一集。")

    else:
        exx_match = re.search(r'[^S]E(\d{1,4})', name_without_ext, re.IGNORECASE)
        if exx_match:
            episode_num = int(exx_match.group(1))
            next_episode_num = episode_num + 1
            episode_digits = len(exx_match.group(1))
            next_pattern = re.compile(f"[^S]E{next_episode_num:0{episode_digits}d}", re.IGNORECASE)
            log(f"查找模式: {next_pattern.pattern} (Exx格式)")
            
            # 优先查找相同扩展名的文件
            same_ext_files = [f for f in video_files if f.lower().endswith(ext.lower())]
            for filename in same_ext_files:
                if next_pattern.search(filename):
                    next_file_path = os.path.join(folder_path, filename)
                    log(f"找到相同扩展名的下一集: {next_file_path}")
                    return next_file_path
            
            # 如果没找到相同扩展名的，再查找所有视频文件
            for filename in video_files:
                if next_pattern.search(filename):
                    next_file_path = os.path.join(folder_path, filename)
                    log(f"找到下一集: {next_file_path}")
                    return next_file_path
            log("在 Exx 模式下未找到下一集。")
        else:
            next_pattern = None

    if next_pattern:
        return None  # 已经在上面的逻辑中处理了

    # --- 策略 2: 智能提取数字串 (兜底策略) ---
    log("未找到 SxxExx 或 Exx 格式，启动智能数字提取策略。")
    
    exclude_patterns = [
        re.compile(r'(19|20)\d{2}'),
        re.compile(r'\b(720|1080|2160|4320)\b'),
        re.compile(r'\b(H264|H265|x264|x265)\b')
    ]
    
    candidate_patterns = [
        re.compile(r'(集|EP|e|p)\s*(\d+)', re.IGNORECASE),
        re.compile(r'\b(\d+)\b')
    ]
    
    current_episode_str = None
    for pattern in candidate_patterns:
        matches = pattern.findall(name_without_ext) # 使用不含扩展名的文件名
        for match in matches:
            num_str = match[1] if isinstance(match, tuple) else match
            
            is_excluded = any(excl_pattern.search(num_str) for excl_pattern in exclude_patterns)
            if not is_excluded:
                current_episode_str = num_str
                log(f"成功提取到候选集数: '{current_episode_str}'")
                break
        if current_episode_str:
            break

    if not current_episode_str:
        log("未能从文件名中提取到有效的集数数字串。")
        return None

    try:
        current_episode_num = int(current_episode_str)
        next_episode_num = current_episode_num + 1
        next_episode_str = f"{next_episode_num:0{len(current_episode_str)}d}"
        
        log(f"尝试查找包含下一集数字 '{next_episode_str}' 的文件。")
        
        next_pattern = re.compile(re.escape(next_episode_str))
        
        # 优先查找相同扩展名的文件
        same_ext_files = [f for f in video_files if f.lower().endswith(ext.lower())]
        for filename in same_ext_files:
            if next_pattern.search(filename):
                next_file_path = os.path.join(folder_path, filename)
                log(f"通过智能策略找到相同扩展名的下一集: {next_file_path}")
                return next_file_path
        
        # 如果没找到相同扩展名的，再查找所有视频文件
        for filename in video_files:
            if next_pattern.search(filename):
                next_file_path = os.path.join(folder_path, filename)
                log(f"通过智能策略找到下一集: {next_file_path}")
                return next_file_path
        
        log(f"在文件夹中未找到包含数字 '{next_episode_str}' 的视频文件。")

    except ValueError:
        log(f"提取的数字串 '{current_episode_str}' 无法转换为整数。")

    return None

def handle_credits_phase_silent(player_or_monitor, end_seconds):
    """
    静默处理片尾逻辑，直接播放下一集。
    """
    log(f"静默处理片尾阶段 (剩余时间 ≤ {end_seconds}s) - 默认模式")
    
    if hasattr(player_or_monitor, '_start_credits_cooldown'):
        player_or_monitor._start_credits_cooldown()
    
    play_next_episode_silent(player_or_monitor.player if hasattr(player_or_monitor, 'player') else player_or_monitor)

def current_video_path(expected=None):
    """Read a live video identity; paused videos remain valid."""
    player = xbmc.Player()
    try:
        if not player.isPlayingVideo():
            return None
        path = player.getPlayingFile()
        if not path or (expected is not None and path != expected):
            return None
        return path if player.isPlayingVideo() else None
    except RuntimeError:
        return None


def show_credits_prompt(end_seconds, expected_path=None):
    """Publish only to the video that supplied this time observation."""
    path = current_video_path(expected_path)
    if path is None:
        return False
    # 已打开的对话框保持其令牌，让 1122 的自动确认完成；重复触发只刷新时间。
    if xbmc.getCondVisibility('Window.IsVisible(1122)'):
        return True
    window = xbmcgui.Window(11122)
    xbmc.executebuiltin(f"Skin.SetString(epend,{format_seconds(end_seconds)})")
    if current_video_path(path) is None:
        return False
    window.setProperty('YoPlayer.Infuse.Skip.Path', path)
    window.setProperty('YoPlayer.Infuse.Skip.Token', str(time.monotonic_ns()))
    xbmc.executebuiltin("ActivateWindow(1122)")
    return True


def handle_credits_phase_db_no_dialog(end_seconds, dbid, id_show, id_season, current_episode_number, expected_path=None):
    """
    不弹窗的片尾处理逻辑，使用数据库信息设置皮肤字符串。
    """
    log(f"片尾处理 - 设置皮肤字符串 (剩余时间 ≤ {end_seconds}s) - 数据库模式")
    
    return show_credits_prompt(end_seconds, expected_path)

def handle_credits_phase_no_dialog(end_seconds, expected_path=None):
    """
    不弹窗的片尾处理逻辑，设置皮肤字符串。
    """
    log(f"片尾处理 - 设置皮肤字符串 (剩余时间 ≤ {end_seconds}s) - 默认模式")
    
    return show_credits_prompt(end_seconds, expected_path)

# ==============================================================================
# 监控器：持续监控播放状态
# ==============================================================================
class ContinuousPlayMonitor(xbmc.Monitor):
    def __init__(self):
        super(ContinuousPlayMonitor, self).__init__()
        self.player = xbmc.Player()
        self.xml_path = get_xml_file_path()
        self.xml_tree = self._load_xml_tree()

        self.current_title = None
        self.current_file_path = None
        self.current_folder_path = None
        self.current_dbid = None
        self.current_id_show = None
        self.current_id_season = None
        self.current_episode_number = None
        self.start_seconds = None
        self.end_seconds = None
        self.has_handled_opening = False

        self.credits_cooldown_active = False
        self.credits_cooldown_end_time = 0
        self.new_episode_cooldown_active = False
        self.new_episode_cooldown_end_time = 0
        
        # 添加缓存变量以减少重复日志
        self.last_log_time = 0
        self.last_log_result = None

    def _load_xml_tree(self):
        """从文件加载XML树。"""
        if xbmcvfs.exists(self.xml_path):
            try:
                return ET.parse(xbmcvfs.File(self.xml_path))
            except Exception as e:
                log(f"加载XML文件失败: {e}", xbmc.LOGERROR)
                return None
        return None
    
    def _start_credits_cooldown(self):
        """启动片尾处理冷却期。"""
        self.credits_cooldown_active = True
        self.credits_cooldown_end_time = time.time() + CREDITS_COOLDOWN_DURATION
        log(f"片尾处理冷却已启动，将在 {CREDITS_COOLDOWN_DURATION} 秒后解除。")

    def _start_new_episode_cooldown(self):
        """启动新剧集检测冷却期。"""
        self.new_episode_cooldown_active = True
        self.new_episode_cooldown_end_time = time.time() + NEW_EPISODE_COOLDOWN_DURATION
        log(f"新剧集检测冷却已启动，将在 {NEW_EPISODE_COOLDOWN_DURATION} 秒后解除。")

    def _reinitialize_for_new_episode(self, new_title, new_folder_path, new_dbid):
        """当检测到新剧集时，重新初始化监控器状态。"""
        log(f"检测到新剧集: '{new_title}', 重新初始化。")
        
        self.xml_tree = self._load_xml_tree()
        
        self.current_title = new_title
        self.current_folder_path = new_folder_path
        self.current_dbid = new_dbid
        
        # 启动新剧集检测冷却机制，抑制片尾处理
        self._start_new_episode_cooldown()
        
        # 尝试从数据库获取信息
        if new_dbid and xbmc.getCondVisibility("VideoPlayer.Content(Episodes)"):
            self.current_id_show, self.current_id_season, self.current_episode_number = get_episode_info(new_dbid)
            log(f"数据库信息 - Show ID: {self.current_id_show}, Season ID: {self.current_id_season}, Episode Number: {self.current_episode_number}")
        else:
            self.current_id_show = None
            self.current_id_season = None
            self.current_episode_number = None
        
        # Emby owns its server marks and native skip prompt/seek chain. Keep
        # the existing no-mark continuous-play branch, without applying or
        # deleting old local marks to an Emby-bound episode.
        from infuse_watched import binding
        try:
            emby_owned = bool(new_dbid and binding('episode', new_dbid))
        except (RuntimeError, sqlite3.Error):
            emby_owned = True  # ambiguous ownership must not apply local marks
        if emby_owned:
            self.start_seconds = None
            self.end_seconds = None
            self.has_handled_opening = True
            return

        # 优先查找数据库ID记录，其次查找路径记录
        if self.current_id_show and self.current_id_season:
            self.start_seconds = find_record_in_xml(
                self.xml_tree, 
                self.current_folder_path, 
                RECORD_TYPE_START,
                self.current_id_show,
                self.current_id_season
            )
            self.end_seconds = find_record_in_xml(
                self.xml_tree, 
                self.current_folder_path, 
                RECORD_TYPE_END,
                self.current_id_show,
                self.current_id_season
            )
        else:
            self.start_seconds = find_record_in_xml(
                self.xml_tree, 
                self.current_folder_path, 
                RECORD_TYPE_START
            )
            self.end_seconds = find_record_in_xml(
                self.xml_tree, 
                self.current_folder_path, 
                RECORD_TYPE_END
            )
            
        self.has_handled_opening = False

        log(f"记录加载完成 - 片头: {format_seconds(self.start_seconds)} (已播放), 片尾: {format_seconds(self.end_seconds)} (剩余)")

        # 只在两种情况下显示记录不完整提示
        # 1. 没有任何记录
        # 2. 有记录但不是双时间点格式且缺少其中一部分
        start_times = []
        if self.current_id_show and self.current_id_season:
            start_times = find_all_start_records_in_xml(
                self.xml_tree, 
                self.current_folder_path, 
                self.current_id_show,
                self.current_id_season
            )
        else:
            start_times = find_all_start_records_in_xml(
                self.xml_tree, 
                self.current_folder_path
            )
        
        # 检查是否为双时间点格式
        is_dual_timestamp = len(start_times) == 2
        
        if not is_dual_timestamp and (self.start_seconds is None or self.end_seconds is None):
            log("检测到记录不完整，向用户发送提示。")
            missing_parts = []
            if self.start_seconds is None:
                missing_parts.append("片头")
            if self.end_seconds is None:
                missing_parts.append("片尾")
            
            message = f"未找到 {'和'.join(missing_parts)} 记录，请先用多功能键设置里的『片头片尾标记』快捷键标记。"
            show_notification("提示", message, xbmcgui.NOTIFICATION_INFO, 5000)

    def run(self):
        """监控器主循环。"""
        log("持续监控已启动。")
        
        while not self.abortRequested():
            observed_path = current_video_path()
            if observed_path is None or not is_playing_episodes_cached():
                log("播放停止或内容非剧集，退出监控。")
                break

            # 检查并结束冷却期
            if self.credits_cooldown_active and time.time() > self.credits_cooldown_end_time:
                self.credits_cooldown_active = False
                log("片尾处理冷却已结束。")

            if self.new_episode_cooldown_active and time.time() > self.new_episode_cooldown_end_time:
                self.new_episode_cooldown_active = False
                log("新剧集检测冷却已结束。")

            current_title = xbmc.getInfoLabel("Player.Title")
            current_folder_path = xbmc.getInfoLabel("Player.Folderpath")
            current_dbid_str = xbmc.getInfoLabel("VideoPlayer.DBID")
            current_dbid = int(current_dbid_str) if current_dbid_str.isdigit() else None
            
            # 分离：片头用已播放时间，片尾用剩余时间
            played_time_sec = parse_time_string(xbmc.getInfoLabel("Player.Time(hh:mm:ss)"))
            remaining_time_sec = parse_time_string(xbmc.getInfoLabel("Player.TimeRemaining(hh:mm:ss)"))
            
            # 获取总时长
            total_duration_sec = parse_time_string(xbmc.getInfoLabel("Player.Duration(hh:mm:ss)"))

            # Stop/next can replace time labels after the loop's first check.
            if current_video_path(observed_path) is None or total_duration_sec <= 0:
                self.waitForAbort(0.1)
                continue

            if current_title and (current_title != self.current_title or observed_path != self.current_file_path):
                self.current_file_path = observed_path
                self._reinitialize_for_new_episode(current_title, current_folder_path, current_dbid)
                time.sleep(1)
                continue

            # 片头判断：已播放时间 < 记录的片头秒数
            if not self.has_handled_opening and self.start_seconds is not None:
                # 检查是否为双片头标记模式
                start_times = []
                
                # 优先查找数据库ID记录，其次查找路径记录
                if self.current_id_show and self.current_id_season:
                    start_times = find_all_start_records_in_xml(
                        self.xml_tree, 
                        self.current_folder_path, 
                        self.current_id_show,
                        self.current_id_season
                    )
                else:
                    start_times = find_all_start_records_in_xml(
                        self.xml_tree, 
                        self.current_folder_path
                    )
                
                # 判断片头标记数量
                if len(start_times) == 2:
                    # 双片头标记模式
                    start_times_sorted = sorted(start_times)
                    small_time = start_times_sorted[0]  # 较小的片头时间点
                    large_time = start_times_sorted[1]  # 较大的片头时间点
                    
                    # 检查当前播放时间是否满足条件：等于较小的时间点或在两个时间点之间
                    if (abs(played_time_sec - small_time) <= 1 or 
                        (small_time < played_time_sec < large_time)):
                        
                        # 计算剩余跳过时间：较大时间点 - 当前时间
                        remaining_skip_time = max(0, large_time - played_time_sec)
                        
                        # 执行Skin.SetString操作
                        formatted_time = format_seconds(large_time)
                        xbmc.executebuiltin(f"Skin.SetString(epintro,{formatted_time})")
                        xbmc.executebuiltin(f"Skin.SetString(epintross,{small_time})")
                        xbmc.executebuiltin("ActivateWindow(1121)")
                        
                        self.has_handled_opening = True
                        log(f"双片头标记模式：已播放 {played_time_sec}s，标记范围 [{small_time}, {large_time}]，剩余跳过时间 {remaining_skip_time}s，执行跳转操作")
                    elif played_time_sec > large_time:
                        # 当前时间超过较大时间点，停止检测
                        self.has_handled_opening = True
                        log(f"双片头标记模式：已播放 {played_time_sec}s > 较大时间点 {large_time}s，停止片头检测")
                    else:
                        log(f"双片头标记模式：当前时间 {played_time_sec}s 不满足条件，等待合适的时机。范围:[{small_time}-{large_time}]")
                elif len(start_times) == 1:
                    # 单片头标记模式，按原有逻辑执行
                    if played_time_sec < self.start_seconds:
                        log(f"进入片头阶段 (已播放 {played_time_sec}s < 片头跳转 {self.start_seconds}s)")
                        
                        # 不再弹出确认窗，而是执行设定皮肤字符串的操作
                        formatted_time = format_seconds(self.start_seconds)
                        adjusted_seconds = max(0, self.start_seconds - 5)  # 片头秒数减去5秒
                        xbmc.executebuiltin(f"Skin.SetString(epintro,{formatted_time})")
                        xbmc.executebuiltin(f"Skin.SetString(epintross,{adjusted_seconds})")
                        xbmc.executebuiltin("ActivateWindow(1121)")
                        
                        self.has_handled_opening = True
                    elif played_time_sec > self.start_seconds:
                        # 当前时间超过片头时间，停止检测
                        self.has_handled_opening = True
                        log(f"单片头标记模式：已播放 {played_time_sec}s > 片头时间 {self.start_seconds}s，停止片头检测")
                else:
                    # 没有片头标记，跳过处理
                    log("没有找到片头标记，跳过片头处理")
                    self.has_handled_opening = True

            # 片尾判断：剩余时间 ≤ 记录的片尾秒数（核心修改）
            # 添加新剧集冷却检查
            if (not self.credits_cooldown_active and 
                not self.new_episode_cooldown_active):  # 新增：检查新剧集冷却
                
                # 检查是否有记录的片尾时间
                if self.end_seconds is not None:
                    # 有记录的片尾时间，使用原始逻辑
                    if remaining_time_sec <= self.end_seconds:
                        log(f"进入片尾阶段 (剩余 {remaining_time_sec}s ≤ 片尾触发 {self.end_seconds}s)")
                        
                        # 根据是否为剧集决定使用哪种片尾处理方法
                        if xbmc.getCondVisibility("VideoPlayer.Content(Episodes)") and self.current_dbid and self.current_id_show and self.current_id_season and self.current_episode_number:
                            handle_credits_phase_db_no_dialog(self.end_seconds, self.current_dbid, self.current_id_show, self.current_id_season, self.current_episode_number, expected_path=observed_path)
                        else:
                            handle_credits_phase_no_dialog(self.end_seconds, expected_path=observed_path)
                            
                        self.end_seconds = None
                else:
                    # 没有记录的片尾时间，检查是否接近片尾（剩余时间小于阈值）
                    if (total_duration_sec > 0 and 
                        remaining_time_sec <= DEFAULT_CREDITS_TRIGGER_THRESHOLD and 
                        remaining_time_sec >= 0):
                        
                        # 【优化逻辑】：检查是否启用了自动播放下一集 (Skin设置)
                        if xbmc.getCondVisibility("Skin.HasSetting(autoplaynext)"):
                            log(f"接近片尾但无记录，且开启了自动播放下一集，使用默认片尾逻辑 (剩余 {remaining_time_sec}s ≤ 阈值 {DEFAULT_CREDITS_TRIGGER_THRESHOLD}s)")
                            
                            # 使用默认片尾时间触发片尾处理
                            default_end_seconds = DEFAULT_CREDITS_END_SECONDS
                            
                            # 根据是否为剧集决定使用哪种片尾处理方法
                            if xbmc.getCondVisibility("VideoPlayer.Content(Episodes)") and self.current_dbid and self.current_id_show and self.current_id_season and self.current_episode_number:
                                handle_credits_phase_db_no_dialog(default_end_seconds, self.current_dbid, self.current_id_show, self.current_id_season, self.current_episode_number, expected_path=observed_path)
                            else:
                                handle_credits_phase_no_dialog(default_end_seconds, expected_path=observed_path)
                            
                            # 设置标志防止重复触发
                            self.end_seconds = default_end_seconds  # 临时设置，避免再次触发
                        else:
                            log(f"接近片尾但无记录，但未开启自动播放下一集 (Skin.HasSetting(autoplaynext)=false)，跳过自动下一集逻辑。")

            self.waitForAbort(1)  # 修改：将间隔调整为1秒
        
        log("持续监控已停止。")

# ==============================================================================
# 命令处理函数
# ==============================================================================
def handle_jump():
    """处理 'jump' 命令，启动持续监控。"""
    log("进入跳转模式。")
    
    # 执行Skin.SetString操作
    xbmc.executebuiltin("Skin.SetString(epend,)")
    xbmc.executebuiltin("Skin.SetString(epintro,)")
    xbmc.executebuiltin("Skin.SetString(epintross,)")
    
    if not is_playing_episodes():
        log("当前播放内容非剧集，无法启动监控。")
        return

    log("准备启动持续播放监控器。")
    monitor = ContinuousPlayMonitor()
    monitor.run()

def handle_end():
    """处理 'end' 命令，静默执行片尾处理逻辑。"""
    log("进入片尾处理模式。")
    
    if current_video_path() is None or not is_playing_episodes():
        log("当前播放内容非剧集，无法执行片尾处理。")
        show_notification("提示", "非剧集无法执行片尾处理", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    # 获取当前播放信息
    current_dbid_str = xbmc.getInfoLabel("VideoPlayer.DBID")
    current_dbid = int(current_dbid_str) if current_dbid_str.isdigit() else None
    current_folder_path = xbmc.getInfoLabel("Player.Folderpath")
    
    # 加载XML记录
    xml_path = get_xml_file_path()
    xml_tree = None
    if xbmcvfs.exists(xml_path):
        try:
            xml_tree = ET.parse(xbmcvfs.File(xml_path))
        except Exception as e:
            log(f"加载XML文件失败: {e}", xbmc.LOGERROR)
    
    # 尝试从数据库获取信息
    current_id_show, current_id_season, current_episode_number = None, None, None
    if current_dbid and xbmc.getCondVisibility("VideoPlayer.Content(Episodes)"):
        current_id_show, current_id_season, current_episode_number = get_episode_info(current_dbid)
        log(f"数据库信息 - Show ID: {current_id_show}, Season ID: {current_id_season}, Episode Number: {current_episode_number}")

    # 优先查找数据库ID记录，其次查找路径记录
    end_seconds = None
    if current_id_show and current_id_season:
        end_seconds = find_record_in_xml(
            xml_tree, 
            current_folder_path, 
            RECORD_TYPE_END,
            current_id_show,
            current_id_season
        )
    else:
        end_seconds = find_record_in_xml(
            xml_tree, 
            current_folder_path, 
            RECORD_TYPE_END
        )

    if end_seconds is None:
        # 如果没有找到片尾记录，使用默认片尾时间
        log(f"未找到片尾记录，使用默认片尾时间: {DEFAULT_CREDITS_END_SECONDS}s")
        end_seconds = DEFAULT_CREDITS_END_SECONDS

    log(f"静默执行片尾处理，片尾秒数: {end_seconds}s")
    
    # 根据是否为剧集决定使用哪种片尾处理方法
    player = xbmc.Player()
    if xbmc.getCondVisibility("VideoPlayer.Content(Episodes)") and current_dbid and current_id_show and current_id_season and current_episode_number:
        handle_credits_phase_db_silent(player, end_seconds, current_dbid, current_id_show, current_id_season, current_episode_number)
    else:
        handle_credits_phase_silent(player, end_seconds)

def handle_record():
    """处理 'record' 命令，记录当前位置为片头或片尾。"""
    log("进入记录模式。")
    record_owner = current_video_path()
    if record_owner is None:
        return
    if not is_playing_episodes():
        log("当前播放内容非剧集，无法记录。")
        show_notification("提示", "非剧集无法建立记录", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    total_duration_sec = parse_time_string(xbmc.getInfoLabel("Player.Duration(hh:mm:ss)"))
    
    if total_duration_sec == 0:
        log("总时长为0或解析失败，无法记录。", xbmc.LOGERROR)
        show_notification("错误", "无法获取或解析视频总时长", xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    
    # 先判断是片头还是片尾（基于已播放时间占比）
    temp_played_time = parse_time_string(xbmc.getInfoLabel("Player.Time(hh:mm:ss)"))
    time_ratio = temp_played_time / total_duration_sec
    
    record_type, record_name = (None, None)
    if time_ratio < 0.2:
        record_type, record_name = (RECORD_TYPE_START, "片头")
    elif time_ratio > 0.8:
        record_type, record_name = (RECORD_TYPE_END, "片尾")
    else:
        log("时间位置不在片头/片尾范围内，无法记录。")
        show_notification("提示", "您选择的时间不在片头和片尾范围内", xbmcgui.NOTIFICATION_INFO, 3000)
        return
    
    # 核心修改：片头记录已播放时间，片尾记录剩余时间
    if record_type == RECORD_TYPE_END:
        time_str = xbmc.getInfoLabel("Player.TimeRemaining(hh:mm:ss)")
        log(f"记录片尾 - 获取剩余时间: {time_str}")
    else:
        time_str = xbmc.getInfoLabel("Player.Time(hh:mm:ss)")
        log(f"记录片头 - 获取已播放时间: {time_str}")
    
    current_time_sec = parse_time_string(time_str)
    if current_time_sec == 0:
        log("解析时间失败，无法记录。", xbmc.LOGERROR)
        show_notification("错误", "解析时间失败，无法记录", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    folder_path = xbmc.getInfoLabel("Player.Folderpath")
    dbid_str = xbmc.getInfoLabel("VideoPlayer.DBID")
    dbid = int(dbid_str) if dbid_str.isdigit() else None
    
    # 根据是否为剧集决定记录方式
    if xbmc.getCondVisibility("VideoPlayer.Content(Episodes)") and dbid:
        # 使用数据库信息记录
        id_show, id_season, episode_number = get_episode_info(dbid)
        if not id_show or not id_season:
            log("无法获取数据库信息，回退到路径记录方式。", xbmc.LOGWARNING)
            use_path_based = True
        else:
            use_path_based = False
    else:
        use_path_based = True

    xml_path = get_xml_file_path()
    try:
        if xbmcvfs.exists(xml_path):
            tree = ET.parse(xbmcvfs.File(xml_path))
            root = tree.getroot()
        else:
            root = ET.Element("tvshowrecords")
            tree = ET.ElementTree(root)
        
        # 根据记录类型处理不同的逻辑
        if record_type == RECORD_TYPE_START:
            # 检查是否已存在片头记录
            existing_records = find_all_start_records_in_xml(tree, folder_path, id_show if not use_path_based else None, id_season if not use_path_based else None)
            
            if existing_records:
                # 已存在片头记录，弹出选择对话框
                dialog = xbmcgui.Dialog()
                choice = dialog.yesno(
                    "选择片头标记方式",
                    "已发现原有片头标记，请选择继续采用单片头标记？还是改为双片头标记？(适用于跳过\"中间片头\"的情况)",
                    nolabel="双片头标记",
                    yeslabel="单片头标记"
                )
                
                if choice:  # 用户选择"替换原有标记"
                    # 按照原逻辑进行替换
                    if use_path_based:
                        target_record = next((r for r in root.findall("record") 
                                            if r.get("path") == folder_path and r.get("type") == record_type), None)
                    else:
                        target_record = next((r for r in root.findall("record") 
                                            if r.get("idShow") == str(id_show) and 
                                               r.get("idSeason") == str(id_season) and 
                                               r.get("type") == record_type), None)
                    
                    record_updated = False
                    if target_record is not None:
                        old_seconds = target_record.text
                        target_record.text = str(current_time_sec)
                        record_updated = True
                        log(f"更新记录: {folder_path} - {record_type} from {old_seconds} to {current_time_sec}s.")
                    else:
                        new_record = ET.SubElement(root, "record")
                        if use_path_based:
                            new_record.set("path", folder_path)
                        else:
                            new_record.set("idShow", str(id_show))
                            new_record.set("idSeason", str(id_season))
                        new_record.set("type", record_type)
                        new_record.text = str(current_time_sec)
                        log(f"新增记录: {folder_path} - {record_type} at {current_time_sec}s.")
                    
                    formatted_xml = format_xml(root)
                    with xbmcvfs.File(xml_path, "w") as f:
                        f.write(formatted_xml.encode("utf-8"))
                    
                    formatted_time = format_seconds(current_time_sec)
                    # 修改这里：对片头记录使用强制通知
                    msg = f"已更新{record_name}记录 {formatted_time}" if record_updated else f"已建立{record_name}记录 {formatted_time}"
                    show_force_notification("提示", msg, xbmcgui.NOTIFICATION_INFO, 3000)
                    
                else:  # 用户选择"双片头标记"
                    # 在现有记录基础上添加新时间点
                    if use_path_based:
                        target_record = next((r for r in root.findall("record") 
                                            if r.get("path") == folder_path and r.get("type") == record_type), None)
                    else:
                        target_record = next((r for r in root.findall("record") 
                                            if r.get("idShow") == str(id_show) and 
                                               r.get("idSeason") == str(id_season) and 
                                               r.get("type") == record_type), None)
                    
                    if target_record is not None:
                        # 解析现有的时间值
                        existing_times = [int(t.strip()) for t in target_record.text.split(',') if t.strip().isdigit()]
                        
                        if len(existing_times) >= 2:
                            # 情况2：已有两个标记点，替换最接近的
                            closest_idx = 0
                            min_diff = abs(existing_times[0] - current_time_sec)
                            
                            for i in range(1, len(existing_times)):
                                diff = abs(existing_times[i] - current_time_sec)
                                if diff < min_diff or (diff == min_diff and existing_times[i] < existing_times[closest_idx]):
                                    min_diff = diff
                                    closest_idx = i
                            
                            existing_times[closest_idx] = current_time_sec
                            existing_times.sort()
                            target_record.text = ','.join(map(str, existing_times))
                            log(f"更新双片头记录 (替换最接近的时间点): {folder_path} - {record_type} to {target_record.text}.")
                        else:
                            # 情况1：只有一个标记点，添加新时间点
                            existing_times.append(current_time_sec)
                            existing_times.sort()
                            target_record.text = ','.join(map(str, existing_times))
                            log(f"更新双片头记录 (添加时间点): {folder_path} - {record_type} to {target_record.text}.")
                    else:
                        # 创建新的记录
                        new_record = ET.SubElement(root, "record")
                        if use_path_based:
                            new_record.set("path", folder_path)
                        else:
                            new_record.set("idShow", str(id_show))
                            new_record.set("idSeason", str(id_season))
                        new_record.set("type", record_type)
                        new_record.text = str(current_time_sec)
                        log(f"新增记录: {folder_path} - {record_type} at {current_time_sec}s.")
                    
                    formatted_xml = format_xml(root)
                    with xbmcvfs.File(xml_path, "w") as f:
                        f.write(formatted_xml.encode("utf-8"))
                    
                    formatted_time = format_seconds(current_time_sec)
                    # 显示更新后的所有时间点
                    all_times_str = ','.join([format_seconds(t) for t in sorted(existing_times)]) if 'existing_times' in locals() else format_seconds(current_time_sec)
                    show_force_notification("提示", f"已更新双片头记录 [{all_times_str}]", xbmcgui.NOTIFICATION_INFO, 3000)
            else:
                # 没有现有片头记录，按原逻辑处理
                if use_path_based:
                    target_record = next((r for r in root.findall("record") 
                                        if r.get("path") == folder_path and r.get("type") == record_type), None)
                else:
                    target_record = next((r for r in root.findall("record") 
                                        if r.get("idShow") == str(id_show) and 
                                           r.get("idSeason") == str(id_season) and 
                                           r.get("type") == record_type), None)
                
                record_updated = False
                if target_record is not None:
                    old_seconds = target_record.text
                    target_record.text = str(current_time_sec)
                    record_updated = True
                    log(f"更新记录: {folder_path} - {record_type} from {old_seconds} to {current_time_sec}s.")
                else:
                    new_record = ET.SubElement(root, "record")
                    if use_path_based:
                        new_record.set("path", folder_path)
                    else:
                        new_record.set("idShow", str(id_show))
                        new_record.set("idSeason", str(id_season))
                    new_record.set("type", record_type)
                    new_record.text = str(current_time_sec)
                    log(f"新增记录: {folder_path} - {record_type} at {current_time_sec}s.")
                
                formatted_xml = format_xml(root)
                with xbmcvfs.File(xml_path, "w") as f:
                    f.write(formatted_xml.encode("utf-8"))
                
                formatted_time = format_seconds(current_time_sec)
                # 修改这里：对片头记录使用强制通知
                msg = f"已更新{record_name}记录 {formatted_time}" if record_updated else f"已建立{record_name}记录 {formatted_time}"
                show_force_notification("提示", msg, xbmcgui.NOTIFICATION_INFO, 3000)
        else:
            # 片尾记录按原逻辑处理
            if use_path_based:
                target_record = next((r for r in root.findall("record") 
                                    if r.get("path") == folder_path and r.get("type") == record_type), None)
            else:
                target_record = next((r for r in root.findall("record") 
                                    if r.get("idShow") == str(id_show) and 
                                       r.get("idSeason") == str(id_season) and 
                                       r.get("type") == record_type), None)
            
            record_updated = False
            if target_record is not None:
                old_seconds = target_record.text
                target_record.text = str(current_time_sec)
                record_updated = True
                log(f"更新记录: {folder_path} - {record_type} from {old_seconds} to {current_time_sec}s.")
            else:
                new_record = ET.SubElement(root, "record")
                if use_path_based:
                    new_record.set("path", folder_path)
                else:
                    new_record.set("idShow", str(id_show))
                    new_record.set("idSeason", str(id_season))
                new_record.set("type", record_type)
                new_record.text = str(current_time_sec)
                log(f"新增记录: {folder_path} - {record_type} at {current_time_sec}s.")
            
            formatted_xml = format_xml(root)
            with xbmcvfs.File(xml_path, "w") as f:
                f.write(formatted_xml.encode("utf-8"))
            
            formatted_time = format_seconds(current_time_sec)
            # 片尾记录仍使用常规通知
            msg = f"已更新{record_name}记录 {formatted_time}" if record_updated else f"已建立{record_name}记录 {formatted_time}"
            show_notification("提示", msg, xbmcgui.NOTIFICATION_INFO, 3000)

            if record_type == RECORD_TYPE_END:
                log("成功记录片尾，检查当前播放位置。")
                # 记录片尾后，判断当前剩余时间是否≤记录值
                current_remaining_sec = parse_time_string(xbmc.getInfoLabel("Player.TimeRemaining(hh:mm:ss)"))
                if current_remaining_sec <= current_time_sec:
                    log("当前剩余时间已≤新记录的片尾时间，触发片尾处理。")
                    # 修复：记录片尾时不自动触发跳转，而是设置皮肤字符串
                    show_credits_prompt(current_time_sec, record_owner)
                    log(f"记录片尾后已设置皮肤字符串 epend={formatted_time} 并激活窗口 1122")

    except Exception as e:
        error_msg = f"处理记录失败: {e}"
        log(error_msg, xbmc.LOGERROR)
        show_notification("错误", error_msg, xbmcgui.NOTIFICATION_ERROR, 3000)

def handle_delete():
    """处理 'delete' 命令，删除当前剧集的记录。"""
    log("进入删除模式。")

    # 获取当前播放信息
    folder_path = xbmc.getInfoLabel("Player.Folderpath")
    dbid_str = xbmc.getInfoLabel("VideoPlayer.DBID")
    dbid = int(dbid_str) if dbid_str.isdigit() else None
    title = xbmc.getInfoLabel("Player.Title")

    # 加载XML记录
    xml_path = get_xml_file_path()
    xml_tree = None
    if xbmcvfs.exists(xml_path):
        try:
            xml_tree = ET.parse(xbmcvfs.File(xml_path))
        except Exception as e:
            log(f"加载XML文件失败: {e}", xbmc.LOGERROR)
            show_notification("错误", "加载记录文件失败", xbmcgui.NOTIFICATION_ERROR, 3000)
            return

    # 读取当前片头和片尾记录
    start_seconds = None
    end_seconds = None

    # 使用is_playing_episodes()函数来统一判断是否为剧集
    if is_playing_episodes():
        # 是剧集，按剧集模式处理
        log("检测到剧集内容，按剧集模式处理")
        
        if dbid:
            # 从数据库获取idShow和idSeason
            id_show, id_season, episode_number = get_episode_info(dbid)
            if not id_show or not id_season:
                log("无法从数据库获取剧集信息，回退到路径模式", xbmc.LOGWARNING)
                # 回退到路径模式
                start_seconds = find_record_in_xml(xml_tree, folder_path, RECORD_TYPE_START)
                end_seconds = find_record_in_xml(xml_tree, folder_path, RECORD_TYPE_END)
            else:
                start_seconds = find_record_in_xml(xml_tree, folder_path, RECORD_TYPE_START, id_show, id_season)
                end_seconds = find_record_in_xml(xml_tree, folder_path, RECORD_TYPE_END, id_show, id_season)
        else:
            # 没有DBID，使用路径模式
            log("无法获取DBID，使用路径模式")
            start_seconds = find_record_in_xml(xml_tree, folder_path, RECORD_TYPE_START)
            end_seconds = find_record_in_xml(xml_tree, folder_path, RECORD_TYPE_END)
    else:
        # 不是剧集，显示提示
        log("未检测到剧集内容，弹出提示")
        show_notification("提示", "非剧集不支持该功能", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    # 获取所有片头时间点
    start_times = []
    if dbid and is_playing_episodes():
        # 尝试使用数据库ID
        id_show, id_season, episode_number = get_episode_info(dbid)
        if id_show and id_season:
            start_times = find_all_start_records_in_xml(xml_tree, folder_path, id_show, id_season)
        else:
            # 数据库ID不可用，使用路径
            start_times = find_all_start_records_in_xml(xml_tree, folder_path)
    else:
        # 使用路径模式
        start_times = find_all_start_records_in_xml(xml_tree, folder_path)

    # 根据片头时间点数量确定显示内容
    if len(start_times) == 0:
        # 没有片头标记
        start_display = "未设置"
    elif len(start_times) == 1:
        # 单个片头标记
        start_display = format_seconds(start_times[0])
    elif len(start_times) == 2:
        # 双片头标记
        sorted_times = sorted(start_times)
        start_display = f"{format_seconds(sorted_times[0])}-{format_seconds(sorted_times[1])}"
    else:
        # 更多片头标记（理论上不应该出现）
        start_display = format_seconds(start_times[0])

    end_display = format_seconds(end_seconds) if end_seconds is not None else "未设置"

    # 显示确认对话框 - 修复引号问题
    dialog_text = f"当前剧集片头记录为：[COLOR FFFFA500]{start_display}[/COLOR]\n片尾记录为距离结束：[COLOR FFFFA500]{end_display}[/COLOR] \n是否删除片头片尾记录？\n选\"是\"立即删除，选\"否\"保持现状。"
    dialog = xbmcgui.Dialog()
    choice = dialog.yesno("确认删除", dialog_text)

    if not choice:  # 用户选择"否"，关闭对话框，不执行删除
        log("用户选择取消删除操作。")
        return

    # 用户选择"是"，执行删除逻辑
    log("用户确认删除记录。")

    # 检查XML文件是否存在
    if not xbmcvfs.exists(xml_path):
        log(f"记录文件 '{xml_path}' 不存在")
        show_notification("提示", "记录文件不存在", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    try:
        tree = ET.parse(xbmcvfs.File(xml_path))
        root = tree.getroot()

        # 根据是否为剧集决定删除方式
        if is_playing_episodes() and dbid:
            # 剧集模式：先尝试使用数据库ID查找和删除
            id_show, id_season, episode_number = get_episode_info(dbid)
            if id_show and id_season:
                records_to_delete = [
                    r for r in root.findall("record") 
                    if r.get("idShow") == str(id_show) and r.get("idSeason") == str(id_season)
                ]
            else:
                records_to_delete = []

            if not records_to_delete:
                log(f"未找到数据库ID记录，尝试按路径查找")
                # 如果数据库ID找不到记录，尝试按路径查找
                records_to_delete = [r for r in root.findall("record") if r.get("path") == folder_path]
                
                if not records_to_delete:
                    log(f"在XML文件中也未找到路径为 '{folder_path}' 的记录。")
                    show_notification("提示", "未找到该剧集的记录", xbmcgui.NOTIFICATION_INFO, 3000)
                    return
        else:
            # 路径模式：按文件夹路径查找和删除
            records_to_delete = [r for r in root.findall("record") if r.get("path") == folder_path]

        if not records_to_delete:
            log(f"在XML文件中未找到路径为 '{folder_path}' 的记录。")
            show_notification("提示", "未找到该剧集的记录", xbmcgui.NOTIFICATION_INFO, 3000)
            return

        for record in records_to_delete:
            root.remove(record)
            log(f"已从XML中删除记录: path={record.get('path')}, idShow={record.get('idShow')}, idSeason={record.get('idSeason')}, type={record.get('type')}")

        formatted_xml = format_xml(root)
        with xbmcvfs.File(xml_path, "w") as f:
            f.write(formatted_xml.encode("utf-8"))
        
        log("该剧集所有相关记录已成功删除。")
        show_force_notification("提示", "该剧集片头/片尾记录已删除", xbmcgui.NOTIFICATION_INFO, 3000)

    except Exception as e:
        error_msg = f"删除记录时发生错误: {e}"
        log(error_msg, xbmc.LOGERROR)
        show_notification("错误", error_msg, xbmcgui.NOTIFICATION_ERROR, 3000)


# ==============================================================================
# 脚本主入口
# ==============================================================================
if __name__ == "__main__":
    log("脚本开始执行。")

    if xbmc.getCondVisibility("Skin.HasSetting(tvshowjumpinfo)"):
        log("提示功能已禁用 (Skin.HasSetting(tvshowjumpinfo) is true)")
    else:
        log("提示功能已启用 (Skin.HasSetting(tvshowjumpinfo) is false)")

    args = sys.argv[1:]
    if not args:
        log("未提供任何参数。", xbmc.LOGERROR)
        sys.exit(0)

    command = args[0]
    if command == "record":
        handle_record()
    elif command == "jump":
        handle_jump()
    elif command == "end":
        handle_end()
    elif command == "delet":
        handle_delete()
    else:
        log(f"未知参数: {command}", xbmc.LOGERROR)
        show_notification("错误", f"未知的脚本参数: {command}", xbmcgui.NOTIFICATION_ERROR, 3000)

    log("脚本执行完成。")
