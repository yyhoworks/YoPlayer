import sys
import xbmc
import xbmcaddon
import xbmcgui
import sqlite3
from urllib.parse import unquote, urlparse
import binascii
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

def main():
    if len(sys.argv) < 2:
        print("Usage: script.py simple | play")
        return

    command = sys.argv[1]
    
    # 根据参数确定获取媒体信息的方式
    if command == "play":
        # 使用播放器信息获取媒体类型和ID
        is_movie = xbmc.getCondVisibility("VideoPlayer.Content(movies)")
        is_episode = xbmc.getCondVisibility("VideoPlayer.Content(episodes)")
        
        if is_movie:
            dbtype = "movie"
        elif is_episode:
            dbtype = "episode"
        else:
            print("Unknown content type during playback")
            return
            
        dbid = xbmc.getInfoLabel("VideoPlayer.DBID")
        print(f"Current playback item DBTYPE: {dbtype}, DBID: {dbid}")
    elif command == "simple":
        # 优先使用详情窗 onload 锁死的身份，回退到原有的列表项信息获取方式
        ident = xbmcgui.Window(12003).getProperty("YoPlayer.Detail.Identity")
        ident_type, _, ident_id = (ident or "").partition(":")
        dbtype = ident_type or xbmc.getInfoLabel("ListItem.DBTYPE")
        dbid = ident_id or xbmc.getInfoLabel("ListItem.DBID")
        print(f"Current item DBTYPE: {dbtype}, DBID: {dbid}")
    else:
        print("Usage: script.py simple | play")
        return

    if not dbtype or not dbid:
        print("DBTYPE or DBID is empty, cannot proceed")
        return

    try:
        dbid_int = int(dbid)
    except ValueError:
        print("DBID is not a valid integer")
        return

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
            return

        conn.close()

        if original_url:
            # 设置皮肤字符串变量
            xbmc.executebuiltin(f'Skin.SetString(shortpath,{original_url})')
            print(f"Set Skin variable 'shortpath' to: {original_url}")
        else:
            print("Failed to extract original URL")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()