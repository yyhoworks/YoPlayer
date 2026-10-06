import sys
import xbmc
import xbmcaddon
import xbmcgui
import sqlite3
from urllib.parse import unquote, urlparse
import binascii
import threading
import time
import re

def is_url_format(path_string):
    """
    检查字符串是否为URL格式
    支持检测 http, https, ftp, smb, nfs, upnp 等协议格式
    以及 emby_addon_mode 路径格式
    """
    if not path_string:
        return False
    
    # 检查是否为 emby_addon_mode 格式
    if path_string.startswith("/emby_addon_mode"):
        return True
    
    # 常见协议模式
    url_pattern = re.compile(
        r'^[a-zA-Z][a-zA-Z0-9+.-]*://',  # 通用协议模式
        re.IGNORECASE
    )
    
    return bool(url_pattern.match(path_string))

def decode_nextgen_url(url: str, decode_percent: bool = False) -> str:
    """
    解码 NextGen URL，提取原始文件路径。
    decode_percent: 是否对结果或原始URL进行urldecode解码
    返回解码后的文件路径字符串，失败则根据 decode_percent 返回原始URL或解码后的原始URL。
    """
    if not url:
        return url

    # 如果不是URL格式，直接返回原字符串
    if not is_url_format(url):
        return url

    original_url = url

    # 定义失败返回逻辑: 如果开启了解码，则返回解码后的原始URL，否则返回原始URL
    def get_fallback():
        return unquote(original_url) if decode_percent else original_url

    # 1. 清理预处理
    if url.startswith("/emby_addon_mode"):
        # 处理 emby_addon_mode 格式
        url = url.replace("/emby_addon_mode", "")
    elif '://' in url:
        try:
            # http://127.0.0.1:57342/http/... -> 移除主机部分
            p = urlparse(url)
            url = p.path
        except:
            pass

    # 移除通用前缀
    is_http = False
    if url.startswith("/http/"):
        is_http = True
        url = url.replace("/http", "")
    elif url.startswith("/dynamic/"):
        url = url.replace("/dynamic", "")

    # 2. 识别类型
    parts = url.strip('/').split('/')
    if not parts: return get_fallback()
    filename = parts[-1]

    is_audio = "/audio/" in url or filename.startswith("a-") or filename.startswith("emby-themes-audio-")
    is_picture = "/picture/" in url
    is_video = not (is_audio or is_picture) # 引用 metadata.py 的简单假设
    
    raw_path = ""
    
    try:
        if is_audio:
            # 来自 metadata.py 的逻辑 (音频部分)
            # URL结构: .../audio/ServerId/ItemId/SourceId/filename.strm
            # 或者仅文件名: a-xxxx-xxxx-HEX-unknown.strm
            
            # 处理主题前缀
            if filename.startswith("emby-themes-audio-"):
                filename = filename.replace("emby-themes-audio-", "a-")
            
            # 格式: a-{EmbyId}-{SourceId}-{HexPath}-unknown.strm
            data_parts = filename.split('-')
            
            if len(data_parts) >= 4:
                # 在 metadata.py 中，此十六进制部分有效需要检查 'isHttp'
                # 我们假设如果存在则用户希望提取它
                hex_str = data_parts[3]
                try:
                    raw_path = bytes.fromhex(hex_str).decode('utf-8')
                except binascii.Error:
                    # 解码音频十六进制段失败
                    return get_fallback()
            else:
                return get_fallback()

        elif is_video:
            # 来自 metadata.py 的逻辑 (其他/视频部分)
            # URL结构: .../{ServerId}/{EmbyId}/{Data}/{SourceId for kodi?}/filename.strm
            
            if len(parts) < 2:
                return get_fallback()

            # 查找包含十六进制数据的段
            data_str = None
            # 寻找包含十六进制数据的段（通常是包含多个连字符的段）
            for part in reversed(parts):
                # 检查是否可能是包含十六进制数据的段
                if part.count('-') >= 4 and not any(c.isalpha() and c.lower() not in ['a', 'b', 'c', 'd', 'e', 'f'] for c in part.replace('-', '')):
                    data_str = part
                    break

            if data_str is None:
                # 尝试找到可能包含十六进制数据的段
                for part in reversed(parts):
                    if '-' in part and len(part) > 10:  # 可能包含十六进制数据
                        data_parts = part.split("-")
                        if len(data_parts) >= 5:
                            # 检查第五个部分是否看起来像十六进制
                            if all(c in '0123456789abcdefABCDEF' for c in data_parts[4]):
                                data_str = part
                                break

            if data_str is None:
                # 没有找到合适的数据段，尝试从文件名中查找
                if '-' in filename:
                    data_parts = filename.split("-")
                    if len(data_parts) >= 5:
                        # 检查第五个部分是否看起来像十六进制
                        if all(c in '0123456789abcdefABCDEF' for c in data_parts[4]):
                            data_str = filename

            if data_str is None:
                return get_fallback()

            if data_str.startswith("emby-themes-video-"):
                data_str = data_str.replace("emby-themes-video-", "v-")
            
            # 数据段格式: m-{KodiId}-{KodiFileId}-{ArtworkIds}-{HEX_METADATA}
            data_parts = data_str.split("-")
            
            if len(data_parts) < 5:
                # 可能是普通路径或不满足格式
                return get_fallback()
                
            hex_metadata = data_parts[4]
            try:
                metadata_str = bytes.fromhex(hex_metadata).decode('utf-8')
            except binascii.Error:
                # 解码视频元数据十六进制失败
                return get_fallback()
                
            # 解析元数据字符串
            # 格式: MediaData1<>MediaData2...
            # MediaData: Info<<VideoStreams<<AudioStreams...
            # Info: Name:Size:Id:PATH:Ticks...
            
            # 为简单起见，我们取第一个媒体源
            media_sources = metadata_str.split("<>")
            found_paths = []
            
            for ms in media_sources:
                sections = ms.split("<<")
                if sections:
                    info_part = sections[0]
                    infos = info_part.split(":")
                    if len(infos) >= 4:
                        # 索引3是路径
                        # 将 <;> 替换回 : (根据 metadata.py)
                        p = infos[3].replace("<;>", ":")
                        found_paths.append(p)
            
            if len(found_paths) >= 1:
                raw_path = found_paths[0]
            else:
                return get_fallback()

        else:
            # 不支持图片解码
            return get_fallback()

    except Exception as e:
        print(f"Error decoding URL: {e}")
        return get_fallback()

    # 后处理
    if decode_percent:
        raw_path = unquote(raw_path)
    
    return raw_path

def get_kodi_database_path():
    """获取Kodi数据库路径"""
    # 使用xbmcvfs代替已弃用的xbmc.translatePath
    try:
        import xbmcvfs
        database_path = xbmcvfs.translatePath("special://userdata/Database/MyVideos131.db")
    except AttributeError:
        # 如果xbmcvfs不可用，尝试使用旧方法
        try:
            database_path = xbmc.translatePath("special://userdata/Database/MyVideos131.db")
        except AttributeError:
            # 如果两者都不可用，手动构建路径
            import os
            home_dir = xbmc.translatePath("special://home").decode('utf-8') if hasattr(xbmc.translatePath("special://home"), 'decode') else xbmc.translatePath("special://home")
            database_path = os.path.join(home_dir, "userdata", "Database", "MyVideos131.db")
    return database_path

class VideoNavMonitor:
    def __init__(self):
        self.monitor = xbmc.Monitor()
        self.current_dbid = ""
        self.previous_dbid = ""
        self.current_viewmode = ""
        self.is_monitoring = True
        self.last_dbid_time = 0
        self.debounced_dbid = ""
        self.debounce_thread = None
        self.debounce_delay = 0.5  # 防抖延迟时间（秒）
        
    def get_original_path(self):
        """获取当前项目的原始路径，使用embypath.py的逻辑"""
        # 获取当前列表项的DBTYPE和DBID
        dbtype = xbmc.getInfoLabel("ListItem.DBTYPE")
        dbid = xbmc.getInfoLabel("ListItem.DBID")

        print(f"Current item DBTYPE: {dbtype}, DBID: {dbid}")

        if not dbtype or not dbid:
            print("DBTYPE or DBID is empty, cannot proceed")
            return ""

        try:
            dbid_int = int(dbid)
        except ValueError:
            print("DBID is not a valid integer")
            return ""

        # 获取数据库路径
        database_path = get_kodi_database_path()
        print(f"Database path: {database_path}")

        try:
            conn = sqlite3.connect(database_path)
            cursor = conn.cursor()

            original_url = ""
            
            if dbtype == "movie":
                # 修改后逻辑：直接读取movie_view视图
                view_query = "SELECT strPath, strFileName FROM movie_view WHERE idMovie = ?"
                cursor.execute(view_query, (dbid_int,))
                view_result = cursor.fetchone()
                if view_result and view_result[0] and view_result[1]:
                    folder_path = view_result[0]
                    file_name = view_result[1]
                    combined_path = folder_path + file_name
                    print(f"Movie path from movie_view: {combined_path}")
                    
                    # 判断拼接后的字符串是否为URL格式
                    if is_url_format(combined_path):
                        # 如果是URL格式，则进行解码
                        original_url = decode_nextgen_url(combined_path, decode_percent=True)
                        print(f"Decoded movie path: {original_url}")
                    else:
                        # 如果不是URL格式，直接使用拼接后的路径
                        original_url = combined_path
                        print(f"Movie path is not URL format, using combined path directly: {original_url}")
                else:
                    # 如果视图查询失败，使用$INFO[ListItem.FileNameAndPath]
                    original_url = xbmc.getInfoLabel("ListItem.FileNameAndPath")
                    print(f"Movie view query failed, using FileNameAndPath: {original_url}")
            
            elif dbtype == "tvshow":
                # 保持原逻辑：读取tvshow_view视图的strPath字段
                query = "SELECT strPath FROM tvshow_view WHERE idShow = ?"
                cursor.execute(query, (dbid_int,))
                result = cursor.fetchone()
                if result and result[0]:
                    # 检查是否为URL格式
                    if is_url_format(result[0]):
                        # 如果是URL格式，则进行解码
                        original_url = decode_nextgen_url(result[0], decode_percent=True)
                        print(f"TV Show path from strPath: {result[0]}")
                        print(f"Decoded TV show path: {original_url}")
                    else:
                        # 如果不是URL格式，直接使用strPath
                        original_url = result[0]
                        print(f"TV Show path is not URL format, using strPath directly: {original_url}")
                else:
                    # 如果查询失败，使用$INFO[ListItem.FileNameAndPath]
                    original_url = xbmc.getInfoLabel("ListItem.FileNameAndPath")
                    print(f"TV Show path query failed, using FileNameAndPath: {original_url}")
            
            elif dbtype == "season":
                # 保持原逻辑：读取season_view视图的strPath字段
                query = "SELECT strPath FROM season_view WHERE idSeason = ?"
                cursor.execute(query, (dbid_int,))
                result = cursor.fetchone()
                if result and result[0]:
                    # 检查是否为URL格式
                    if is_url_format(result[0]):
                        # 如果是URL格式，则进行解码
                        original_url = decode_nextgen_url(result[0], decode_percent=True)
                        print(f"Season path from strPath: {result[0]}")
                        print(f"Decoded season path: {original_url}")
                    else:
                        # 如果不是URL格式，直接使用strPath
                        original_url = result[0]
                        print(f"Season path is not URL format, using strPath directly: {original_url}")
                else:
                    # 如果查询失败，使用$INFO[ListItem.FileNameAndPath]
                    original_url = xbmc.getInfoLabel("ListItem.FileNameAndPath")
                    print(f"Season path query failed, using FileNameAndPath: {original_url}")
            
            elif dbtype == "episode":
                # 修改后逻辑：直接读取episode_view视图
                view_query = "SELECT strPath, strFileName FROM episode_view WHERE idEpisode = ?"
                cursor.execute(view_query, (dbid_int,))
                view_result = cursor.fetchone()
                if view_result and view_result[0] and view_result[1]:
                    folder_path = view_result[0]
                    file_name = view_result[1]
                    combined_path = folder_path + file_name
                    print(f"Episode path from episode_view: {combined_path}")
                    
                    # 判断拼接后的字符串是否为URL格式
                    if is_url_format(combined_path):
                        # 如果是URL格式，则进行解码
                        original_url = decode_nextgen_url(combined_path, decode_percent=True)
                        print(f"Decoded episode path: {original_url}")
                    else:
                        # 如果不是URL格式，直接使用拼接后的路径
                        original_url = combined_path
                        print(f"Episode path is not URL format, using combined path directly: {original_url}")
                else:
                    # 如果视图查询失败，使用$INFO[ListItem.FileNameAndPath]
                    original_url = xbmc.getInfoLabel("ListItem.FileNameAndPath")
                    print(f"Episode view query failed, using FileNameAndPath: {original_url}")
            
            else:
                print(f"Unsupported DBTYPE: {dbtype}")
                conn.close()
                return ""

            conn.close()

            if original_url:
                return original_url
            else:
                print("Failed to extract original URL")
                return ""

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return ""
        except Exception as e:
            print(f"Error: {e}")
            return ""

    def debounce_callback(self, dbid):
        """防抖回调函数，延迟执行解码逻辑"""
        # 检查在延迟期间是否有新的DBID变化
        if dbid == xbmc.getInfoLabel("ListItem.DBID"):
            # 获取当前视图模式
            current_viewmode = xbmc.getInfoLabel("Container.Viewmode")
            
            # 检查视图模式是否符合条件
            viewmode_match = current_viewmode in ["列表", "剧集列表"]
            
            if viewmode_match:
                # 获取原始路径
                original_path = self.get_original_path()
                
                if original_path:
                    # 设置transpath为1，设置原始路径
                    xbmc.executebuiltin('Skin.SetString(transpath,1)')
                    xbmc.executebuiltin(f'Skin.SetString(listpath,{original_path})')
                    print(f"Set transpath=1 and listpath={original_path}")

    def run(self):
        # 初始化transpath为0
        xbmc.executebuiltin('Skin.SetString(transpath,0)')
        
        while self.is_monitoring and not self.monitor.abortRequested():
            # 检查视频窗口是否可见
            videos_window_visible = xbmc.getCondVisibility("Window.IsVisible(videos)")
            
            # 如果视频窗口不可见，则退出脚本
            if not videos_window_visible:
                print("Videos window is not visible, stopping script...")
                break
            
            # 获取当前Viewmode和DBID
            current_viewmode = xbmc.getInfoLabel("Container.Viewmode")
            current_dbid = xbmc.getInfoLabel("ListItem.DBID")
            
            # 检查视图模式是否符合条件
            viewmode_match = current_viewmode in ["列表", "剧集列表"]
            
            # 检查DBID是否发生变化
            dbid_changed = current_dbid != self.current_dbid
            
            # 检查DBID是否从非空变为为空（空字符串）
            dbid_became_empty = self.current_dbid != "" and current_dbid == ""
            
            # 如果视图模式匹配且DBID从非空变为为空，则设置transpath为0
            if viewmode_match and dbid_became_empty:
                xbmc.executebuiltin('Skin.SetString(transpath,0)')
                print("Set transpath=0 because DBID changed from non-empty to empty")
            
            # 检查DBID是否发生变化且不为空
            dbid_not_empty = current_dbid != ""
            
            if viewmode_match and dbid_changed and dbid_not_empty:
                # 记录DBID变化的时间
                current_time = time.time()
                
                # 如果有之前的防抖线程正在运行，取消它
                if self.debounce_thread and self.debounce_thread.is_alive():
                    # 为了模拟取消，我们可以简单地不再等待之前的线程
                    pass
                
                # 更新记录的值
                self.previous_dbid = self.current_dbid  # 保存上一个DBID值
                self.current_dbid = current_dbid
                self.current_viewmode = current_viewmode
                self.last_dbid_time = current_time
                self.debounced_dbid = current_dbid
                
                # 创建新的防抖线程
                self.debounce_thread = threading.Thread(
                    target=self.delayed_execution,
                    args=(current_dbid, current_time)
                )
                self.debounce_thread.daemon = True
                self.debounce_thread.start()
            else:
                # 如果没有变化，也更新记录的值
                self.previous_dbid = self.current_dbid
                self.current_dbid = current_dbid
                self.current_viewmode = current_viewmode
            
            # 等待一小段时间再检查
            if self.monitor.waitForAbort(0.5):  # 每0.5秒检查一次
                break

    def delayed_execution(self, dbid, start_time):
        """延迟执行函数，用于防抖"""
        # 等待指定的防抖时间
        time.sleep(self.debounce_delay)
        
        # 检查是否仍在监控状态以及时间戳是否匹配（防止并发问题）
        if self.is_monitoring and abs(time.time() - start_time) >= self.debounce_delay:
            # 检查视频窗口是否仍然可见
            videos_window_visible = xbmc.getCondVisibility("Window.IsVisible(videos)")
            
            # 如果视频窗口不可见，不执行任何操作
            if not videos_window_visible:
                print("Videos window is not visible during delayed execution, skipping...")
                return
            
            # 再次验证当前DBID是否仍为该值
            current_dbid = xbmc.getInfoLabel("ListItem.DBID")
            current_viewmode = xbmc.getInfoLabel("Container.Viewmode")
            
            # 检查视图模式是否符合条件
            viewmode_match = current_viewmode in ["列表", "剧集列表"]
            
            if current_dbid == dbid and viewmode_match:
                # 获取原始路径
                original_path = self.get_original_path()
                
                if original_path:
                    # 设置transpath为1，设置原始路径
                    xbmc.executebuiltin('Skin.SetString(transpath,1)')
                    xbmc.executebuiltin(f'Skin.SetString(listpath,{original_path})')
                    print(f"Set transpath=1 and listpath={original_path}")

    def stop(self):
        self.is_monitoring = False

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "off":
        # 停止监测，关闭脚本
        print("Stopping video navigation monitoring...")
        return
    
    # 创建监控实例并运行
    monitor = VideoNavMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("Script interrupted by user")
    finally:
        monitor.stop()

if __name__ == "__main__":
    main()