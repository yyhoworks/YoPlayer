import xbmc
import xbmcaddon
import xbmcvfs
import json
import sqlite3
import re
from urllib.parse import quote_plus
import time
import urllib.request
import urllib.error

def log_debug(message):
    """调试日志"""
    xbmc.log(f"[DEBUG] maoyan_script: {message}", xbmc.LOGDEBUG)

def log_info(message):
    """信息日志"""
    xbmc.log(f"[INFO] maoyan_script: {message}", xbmc.LOGINFO)

def log_error(message):
    """错误日志"""
    xbmc.log(f"[ERROR] maoyan_script: {message}", xbmc.LOGERROR)

def get_info_value(info_tag):
    """获取KODI info标签的值"""
    value = xbmc.getInfoLabel(info_tag)
    log_debug(f"获取 {info_tag}: {value}")
    return value

def translate_path(path):
    """路径转换函数，兼容新旧版本"""
    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        # 旧版本KODI使用xbmc.translatePath
        return xbmc.translatePath(path)

def download_file(url, timeout=5):
    """下载文件内容，带请求头和超时设置"""
    log_debug(f"开始下载: {url} (超时: {timeout}s)")
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.maoyan.com/',
                'Origin': 'https://www.maoyan.com',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache'
            }
        )
        response = urllib.request.urlopen(req, timeout=timeout)
        data = response.read()
        log_debug(f"下载成功，数据长度: {len(data)}")
        return data.decode('utf-8')
    except urllib.error.HTTPError as e:
        log_error(f"HTTP错误: {e.code} - {e.reason}")
        log_error(f"URL: {url}")
        return None
    except urllib.error.URLError as e:
        log_error(f"URL错误: {e.reason}")
        log_error(f"URL: {url}")
        return None
    except Exception as e:
        log_error(f"下载失败: {str(e)}")
        log_error(f"URL: {url}")
        return None

def find_trailer_url(data):
    """从数据中查找预告片URL"""
    log_debug("开始查找预告片URL")
    try:
        # 尝试查找 vd 或 videourl 字段
        log_debug("查找 vd 或 videourl 字段")
        match = re.search(r'"(vd|videourl)"\s*:\s*"([^"]+)"', data, re.IGNORECASE)
        if match:
            log_debug(f"找到 vd/videourl 匹配: {match.group(2)[:100]}...")
            return match.group(2)
        
        # 如果没找到，查找vod.pipi.cn开头的视频文件
        log_debug("查找vod.pipi.cn开头的视频文件")
        video_extensions = ['.mp4', '.mkv', '.flv', '.avi', '.mov', '.wmv', '.webm']
        for ext in video_extensions:
            pattern = r'https://vod\.pipi\.cn/[^\s"]*' + ext.replace('.', r'\.')
            matches = re.findall(pattern, data, re.IGNORECASE)
            if matches:
                log_debug(f"找到vod.pipi.cn视频文件匹配: {matches[0][:100]}...")
                return matches[0]
        
        log_debug("未找到预告片URL")
        return None
    except Exception as e:
        log_error(f"查找预告片URL失败: {str(e)}")
        return None

def find_closest_date(results, target_date):
    """查找最接近日期的结果"""
    log_debug(f"查找最接近日期，目标日期: {target_date}")
    try:
        if not target_date or len(target_date) < 4:
            log_debug("目标日期为空或不足4位，返回第一个结果")
            return results[0] if results else None
        
        target_year = int(target_date[:4])
        log_debug(f"目标年份: {target_year}")
        
        closest_result = None
        min_diff = float('inf')
        
        for i, result in enumerate(results):
            release = result.get('release', '')
            log_debug(f"结果 {i}: release='{release}'")
            
            if release and len(release) >= 4:
                try:
                    year_str = release[:4]
                    if year_str.isdigit():
                        year = int(year_str)
                        diff = abs(year - target_year)
                        log_debug(f"  年份: {year}, 差值: {diff}")
                        if diff < min_diff:
                            min_diff = diff
                            closest_result = result
                            log_debug(f"  新的最接近结果，差值: {diff}")
                except ValueError:
                    log_debug(f"  无法解析年份: {year_str}")
                    continue
        
        log_debug(f"最接近的结果差值: {min_diff}")
        return closest_result if closest_result else (results[0] if results else None)
    except Exception as e:
        log_error(f"查找最接近日期失败: {str(e)}")
        return None

def fallback_to_bili():
    """执行备用脚本"""
    log_info("执行备用脚本 bili.py")
    xbmc.executebuiltin('RunScript(special://skin/scripts/bili.py,info)')

def update_database_trailer(db_type, db_id, trailer_url):
    """更新数据库中的预告片URL"""
    log_debug(f"更新数据库，类型: {db_type}, ID: {db_id}, URL: {trailer_url}")
    
    try:
        db_path = translate_path('special://userdata/Database/MyVideos131.db')
        log_debug(f"数据库路径: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if db_type == 'tvshow':
            # 更新tvshow表的c16字段
            cursor.execute("UPDATE tvshow SET c16 = ? WHERE idShow = ?", (trailer_url, db_id))
        elif db_type == 'movie':
            # 更新movie表的c19字段
            cursor.execute("UPDATE movie SET c19 = ? WHERE idMovie = ?", (trailer_url, db_id))
        
        conn.commit()
        conn.close()
        log_debug("数据库更新成功")
    except Exception as e:
        log_error(f"数据库更新失败: {str(e)}")

def case1_get_trailer_url_from_db(db_episode_id):
    """情况1：从数据库获取预告片URL"""
    log_debug(f"情况1：从数据库获取预告片URL，episode_id: {db_episode_id}")
    
    try:
        db_path = translate_path('special://userdata/Database/MyVideos131.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询剧集对应的剧集ID
        cursor.execute("SELECT idShow FROM episode WHERE idEpisode = ?", (db_episode_id,))
        show_id_result = cursor.fetchone()
        
        if not show_id_result:
            log_error("未找到对应的剧集ID")
            conn.close()
            return None
        
        show_id = show_id_result[0]
        log_debug(f"找到剧集ID: {show_id}")
        
        # 查询剧集信息
        cursor.execute("SELECT c00, c05, c16 FROM tvshow WHERE idShow = ?", (show_id,))
        show_info = cursor.fetchone()
        
        if not show_info:
            log_error("未找到剧集信息")
            conn.close()
            return None
        
        title = show_info[0] if show_info[0] else ""
        year = show_info[1] if show_info[1] else ""
        existing_trailer = show_info[2] if show_info[2] else ""
        
        conn.close()
        log_info(f"获取到剧集信息 - 标题: {title}, 年份: {year}, 现有预告片: {existing_trailer}")
        
        # 检查现有预告片是否为vod.pipi.cn开头
        if existing_trailer and existing_trailer.startswith('https://vod.pipi.cn'):
            log_info("现有预告片已为vod.pipi.cn开头，直接使用")
            return existing_trailer
        else:
            log_info("现有预告片不是vod.pipi.cn开头，需要获取新的")
            
            # 搜索新的预告片
            search_url = f"https://apis.netstart.cn/maoyan/search/movies?keyword={quote_plus(title)}"
            search_data = download_file(search_url, timeout=5)
            
            if not search_data:
                log_error("搜索API调用失败")
                return None
            
            try:
                search_json = json.loads(search_data)
                
                # 尝试不同的数据路径
                if 'data' in search_json and 'movies' in search_json['data']:
                    search_results = search_json['data']['movies'].get('list', [])
                elif 'data' in search_json and isinstance(search_json['data'], list):
                    search_results = search_json['data']
                elif 'movies' in search_json:
                    search_results = search_json['movies'].get('list', [])
                elif 'data' in search_json:
                    search_results = search_json['data']
                else:
                    # 尝试查找可能包含电影列表的字段
                    possible_fields = ['subjects', 'items', 'list', 'results', 'movies']
                    search_results = []
                    for field in possible_fields:
                        if field in search_json:
                            if isinstance(search_json[field], list):
                                search_results = search_json[field]
                                break
                    
                    if not search_results:
                        # 如果根元素是数组
                        if isinstance(search_json, list):
                            search_results = search_json
                        else:
                            search_results = []
            except json.JSONDecodeError as e:
                log_error(f"JSON解析失败: {str(e)}")
                return None
            
            if not search_results:
                log_error("未找到搜索结果")
                return None
            
            log_info(f"找到 {len(search_results)} 个搜索结果")
            
            if len(search_results) == 1:
                # 单个结果
                movie_item = search_results[0]
                movie_id = movie_item.get('id')
            else:
                # 多个结果，根据年份匹配
                matched_result = None
                for result in search_results:
                    release = result.get('release', '')
                    if release.startswith(year[:4]) if year else False:
                        matched_result = result
                        break
                
                if not matched_result:
                    # 查找最接近年份的结果
                    matched_result = find_closest_date(search_results, year)
                
                if matched_result:
                    movie_id = matched_result.get('id')
            
            if not movie_id:
                log_error("无法获取电影ID")
                return None
            
            # 获取电影详情
            detail_url = f"https://apis.netstart.cn/maoyan/movie/detail?movieId={movie_id}"
            detail_data = download_file(detail_url, timeout=5)
            
            if not detail_data:
                log_error("详情API调用失败")
                return None
            
            # 查找预告片URL
            trailer_url = find_trailer_url(detail_data)
            
            if not trailer_url:
                log_error("未找到预告片URL")
                return None
            
            log_info(f"找到预告片URL: {trailer_url}")
            return trailer_url
    except Exception as e:
        log_error(f"情况1数据库操作失败: {str(e)}")
        return None

def case2_get_trailer_url_from_kodi():
    """情况2：从KODI获取预告片URL"""
    log_debug("情况2：从KODI获取预告片URL")
    
    # 检查ListItem.Trailer是否为vod.pipi.cn开头
    existing_trailer = get_info_value('ListItem.Trailer')
    log_info(f"现有预告片: {existing_trailer}")
    
    if existing_trailer and existing_trailer.startswith('https://vod.pipi.cn'):
        log_info("现有预告片已为vod.pipi.cn开头，直接使用")
        return existing_trailer
    else:
        log_info("现有预告片不是vod.pipi.cn开头，需要获取新的")
        
        # 获取项目信息
        title = get_info_value('ListItem.Label')
        year = get_info_value('ListItem.Premiered')
        db_id = get_info_value('ListItem.DBID')
        
        if not title or title == "":
            log_error("无法获取标题信息")
            return None
        
        log_info(f"搜索标题: {title}, 年份: {year}")
        
        # 搜索预告片
        search_url = f"https://apis.netstart.cn/maoyan/search/movies?keyword={quote_plus(title)}"
        search_data = download_file(search_url, timeout=5)
        
        if not search_data:
            log_error("搜索API调用失败")
            return None
        
        try:
            search_json = json.loads(search_data)
            
            # 尝试不同的数据路径
            if 'data' in search_json and 'movies' in search_json['data']:
                search_results = search_json['data']['movies'].get('list', [])
            elif 'data' in search_json and isinstance(search_json['data'], list):
                search_results = search_json['data']
            elif 'movies' in search_json:
                search_results = search_json['movies'].get('list', [])
            elif 'data' in search_json:
                search_results = search_json['data']
            else:
                # 尝试查找可能包含电影列表的字段
                possible_fields = ['subjects', 'items', 'list', 'results', 'movies']
                search_results = []
                for field in possible_fields:
                    if field in search_json:
                        if isinstance(search_json[field], list):
                            search_results = search_json[field]
                            break
                
                if not search_results:
                    # 如果根元素是数组
                    if isinstance(search_json, list):
                        search_results = search_json
                    else:
                        search_results = []
        except json.JSONDecodeError as e:
            log_error(f"JSON解析失败: {str(e)}")
            return None
        
        if not search_results:
            log_error("未找到搜索结果")
            return None
        
        log_info(f"找到 {len(search_results)} 个搜索结果")
        
        if len(search_results) == 1:
            # 单个结果
            movie_item = search_results[0]
            movie_id = movie_item.get('id')
        else:
            # 多个结果，根据年份匹配
            matched_result = None
            for result in search_results:
                release = result.get('release', '')
                if release.startswith(year[:4]) if year else False:
                    matched_result = result
                    break
            
            if not matched_result:
                # 查找最接近年份的结果
                matched_result = find_closest_date(search_results, year)
            
            if matched_result:
                movie_id = matched_result.get('id')
        
        if not movie_id:
            log_error("无法获取电影ID")
            return None
        
        # 获取电影详情
        detail_url = f"https://apis.netstart.cn/maoyan/movie/detail?movieId={movie_id}"
        detail_data = download_file(detail_url, timeout=5)
        
        if not detail_data:
            log_error("详情API调用失败")
            return None
        
        # 查找预告片URL
        trailer_url = find_trailer_url(detail_data)
        
        if not trailer_url:
            log_error("未找到预告片URL")
            return None
        
        log_info(f"找到预告片URL: {trailer_url}")
        return trailer_url

def play_and_monitor_trailer(trailer_url, db_type=None, db_id=None):
    """播放并监控预告片"""
    log_info(f"开始播放预告片: {trailer_url}")
    xbmc.executebuiltin(f'PlayMedia({trailer_url},1,noresume)')
    
    # 检查是否正常播放
    log_debug("等待预告片开始播放")
    max_wait_time = 10  # 最大等待10秒
    wait_count = 0
    while wait_count < max_wait_time * 10:  # 每0.1秒检查一次
        is_playing = xbmc.Player().isPlayingVideo()
        if is_playing:
            log_debug("预告片开始播放")
            break
        time.sleep(0.1)
        wait_count += 1
    
    if not xbmc.Player().isPlayingVideo():
        log_debug("预告片未能正常播放")
        return False
    
    # 设置预告片播放状态和URL
    log_debug("设置预告片播放状态")
    xbmc.executebuiltin('Skin.SetString(notrailer,0)')
    xbmc.executebuiltin(f'Skin.SetString(trailerurl,{trailer_url})')
    
    # 根据类型更新数据库
    if db_type and db_id:
        update_database_trailer(db_type, db_id, trailer_url)
    
    # 检测是否循环播放
    has_trailer_loop = xbmc.getCondVisibility('Skin.HasSetting(trailerloop)')
    log_debug(f"trailerloop 设置: {has_trailer_loop}")
    
    if not has_trailer_loop:
        # 不循环播放，监测播放状态
        log_debug("开始监测播放状态（非循环模式）")
        while xbmc.Player().isPlayingVideo():
            time.sleep(1)
        
        log_debug("播放结束，设置预告片状态为停止并关闭对话框")
        xbmc.executebuiltin('Skin.SetString(notrailer,1)')
        xbmc.executebuiltin('Dialog.Close(1130)')
        log_info("非循环模式完成")
        return True
    else:
        # 循环播放
        log_debug("开始循环播放模式")
        loop_counter = 0
        while True:
            loop_counter += 1
            log_debug(f"循环播放第 {loop_counter} 次")
            
            while xbmc.Player().isPlayingVideo():
                time.sleep(1)
            
            time.sleep(1)  # 延迟1秒
            
            is_window_visible = xbmc.getCondVisibility('Window.IsVisible(1130)')
            log_debug(f"窗口1130可见: {is_window_visible}")
            
            if is_window_visible:
                log_debug("窗口1130可见，重新播放预告片")
                # 重新播放
                xbmc.executebuiltin(f'PlayMedia({trailer_url},1,noresume)')
                
                # 再次等待播放开始
                wait_count = 0
                while wait_count < max_wait_time * 10:
                    if xbmc.Player().isPlayingVideo():
                        log_debug("重新播放开始")
                        break
                    time.sleep(0.1)
                    wait_count += 1
            else:
                log_debug("窗口1130不可见，退出循环")
                # 窗口不可见，退出
                break
    
    log_info("脚本执行完成")
    return True

def main():
    log_info("脚本开始执行")
    
    # 检查是否有info参数
    import sys
    args = sys.argv
    log_debug(f"命令行参数: {args}")
    if len(args) < 2 or args[1] != 'info':
        log_info("参数不是 'info'，退出")
        return
    
    try:
        # 获取当前项目类型
        dbtype = get_info_value('ListItem.DBTYPE')
        log_info(f"当前项目类型: {dbtype}")
        
        trailer_url = None
        
        if dbtype == 'episode':
            # 情况1：剧集
            log_info("处理剧集类型")
            episode_id = get_info_value('ListItem.DBID')
            if not episode_id:
                log_error("无法获取剧集DBID")
                fallback_to_bili()
                return
            
            # 情况1.1和1.2：获取预告片URL
            trailer_url = case1_get_trailer_url_from_db(episode_id)
            
            if not trailer_url:
                log_error("无法获取预告片URL")
                fallback_to_bili()
                return
            
            # 情况1的后续逻辑：播放和监控预告片
            # 获取剧集ID用于更新数据库
            db_path = translate_path('special://userdata/Database/MyVideos131.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 查询剧集对应的剧集ID
            cursor.execute("SELECT idShow FROM episode WHERE idEpisode = ?", (episode_id,))
            show_id_result = cursor.fetchone()
            
            if show_id_result:
                show_id = show_id_result[0]
                # 更新数据库
                cursor.execute("UPDATE tvshow SET c16 = ? WHERE idShow = ?", (trailer_url, show_id))
                conn.commit()
                log_info("更新tvshow表的c16字段")
            conn.close()
            
            # 播放和监控预告片
            success = play_and_monitor_trailer(trailer_url, 'tvshow', show_id)
            if not success:
                fallback_to_bili()
        else:
            # 情况2：非剧集
            log_info("处理非剧集类型")
            
            # 情况2.1和2.2：获取预告片URL
            trailer_url = case2_get_trailer_url_from_kodi()
            
            if not trailer_url:
                log_error("无法获取预告片URL")
                fallback_to_bili()
                return
            
            # 情况2的后续逻辑：播放和监控预告片
            # 根据类型更新数据库
            db_id = get_info_value('ListItem.DBID')
            success = play_and_monitor_trailer(trailer_url, dbtype, db_id)
            if not success:
                fallback_to_bili()
    
    except Exception as e:
        log_error(f"脚本执行过程中发生异常: {str(e)}")
        fallback_to_bili()

if __name__ == '__main__':
    main()