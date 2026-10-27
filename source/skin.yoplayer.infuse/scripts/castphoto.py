import xbmc
import xbmcaddon
import xbmcgui
import sqlite3
import threading
import os
import urllib.request
import urllib.parse
import ssl
import uuid
from pathlib import Path

FIELDS = {'directorimg', 'directorurl', 'directorname', 'embyrating',
          'embytomato', 'embyimdb', 'embydouban', 'embypopcorn', 'userrating1'}
PUBLISHER = None


class DetailPublication:
    def __init__(self):
        self.window = xbmcgui.Window(12003)
        self.identity = self.window.getProperty('YoPlayer.Detail.Identity')
        self.path = self.window.getProperty('YoPlayer.Detail.Path')
        self.token = uuid.uuid4().hex
        self.window.setProperty('YoPlayer.Cast.Owner', self.token)

    def valid(self):
        return (self.identity and xbmc.getCondVisibility('Window.IsVisible(movieinformation)')
                and self.window.getProperty('YoPlayer.Cast.Owner') == self.token
                and self.window.getProperty('YoPlayer.Detail.Identity') == self.identity
                and self.window.getProperty('YoPlayer.Detail.Path') == self.path)

    def publish(self, key, value):
        if self.valid():
            self.window.setProperty('YoPlayer.Cast.' + key, str(value))


def get_skin_string(key):
    """获取皮肤字符串值"""
    if key in FIELDS:
        return xbmcgui.Window(12003).getProperty('YoPlayer.Cast.' + key)
    return xbmc.getInfoLabel(f'Skin.String({key})')

def set_skin_string(key, value):
    """设置皮肤字符串值"""
    if PUBLISHER is not None:
        PUBLISHER.publish(key, value)
    elif key in FIELDS:
        xbmcgui.Window(12003).setProperty('YoPlayer.Cast.' + key, str(value))
    else:
        xbmc.executebuiltin(f'Skin.SetString({key},{value})', True)

def get_listitem_info(info):
    """获取列表项信息"""
    return xbmc.getInfoLabel(f'ListItem.{info}')

def extract_url_from_thumb_tag(text):
    """从<thumb></thumb>标签中提取URL"""
    start_tag = "<thumb>"
    end_tag = "</thumb>"
    
    start_pos = text.find(start_tag)
    if start_pos != -1:
        start_pos += len(start_tag)
        end_pos = text.find(end_tag, start_pos)
        if end_pos != -1:
            return text[start_pos:end_pos]
    
    return text

def is_valid_network_url(url):
    """判断是否为有效的网络URL（排除本地路径误判）"""
    # 首先检查是否为本地文件路径（Windows路径特征）
    if url.replace('\\', '/').startswith(('C:', 'D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 'N:', 'O:', 'P:', 'Q:', 'R:', 'S:', 'T:', 'U:', 'V:', 'W:', 'X:', 'Y:', 'Z:')):
        return False
    
    # 检查是否为网络URL
    parsed = urllib.parse.urlparse(url)
    return bool(parsed.scheme and parsed.netloc)

def should_copy_to_cache(file_path):
    """判断是否需要复制文件到缓存目录"""
    path_lower = file_path.lower()
    return 'clounas' in path_lower or 'clouddrive' in path_lower or '115' in path_lower

def copy_local_file(src_path, dest_path):
    """复制本地文件到目标位置"""
    try:
        # 创建目录（如果不存在）
        directory = os.path.dirname(dest_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        # 复制文件
        import shutil
        shutil.copy2(src_path, dest_path)
        
        xbmc.log(f"[CastPhoto Script] Successfully copied local file: {src_path} -> {dest_path}", xbmc.LOGDEBUG)
        return True
    except Exception as e:
        xbmc.log(f"[CastPhoto Script] Copy local file Error: {str(e)} for source: {src_path}", xbmc.LOGERROR)
        return False

def download_image(url, local_path):
    """下载图片到本地"""
    try:
        # 创建目录（如果不存在）
        directory = os.path.dirname(local_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        # 创建请求对象并设置User-Agent
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # 创建SSL上下文（忽略证书验证）
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # 下载图片
        response = urllib.request.urlopen(req, timeout=30, context=context)
        
        with open(local_path, 'wb') as f:
            f.write(response.read())
        
        xbmc.log(f"[CastPhoto Script] Successfully downloaded image: {url} -> {local_path}", xbmc.LOGDEBUG)
        return True
    except Exception as e:
        xbmc.log(f"[CastPhoto Script] Download Error: {str(e)} for URL: {url}", xbmc.LOGERROR)
        return False

def update_actor_art_urls(conn, actor_id, new_art_urls):
    """更新actor表中的art_urls字段"""
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE actor SET art_urls = ? WHERE actor_id = ?", (new_art_urls, actor_id))
        conn.commit()
        xbmc.log(f"[CastPhoto Script] Updated actor {actor_id} art_urls to: {new_art_urls}", xbmc.LOGDEBUG)
        return True
    except Exception as e:
        xbmc.log(f"[CastPhoto Script] Update actor art_urls Error: {str(e)}", xbmc.LOGERROR)
        return False

def execute_task1(db_path, dbtype, dbid):
    """任务1：获取导演图片信息"""
    try:
        xbmc.log(f"[CastPhoto Script] Task1 started - DBTYPE: {dbtype}, DBID: {dbid}", xbmc.LOGDEBUG)
        
        conn = sqlite3.connect(Path(db_path).as_uri() + '?mode=ro', uri=True)
        cursor = conn.cursor()
        
        # 查询director_link表 - 现在同时检查media_id和media_type
        cursor.execute("SELECT actor_id FROM director_link WHERE media_id = ? AND media_type = ?", (dbid, dbtype))
        results = cursor.fetchall()
        
        xbmc.log(f"[CastPhoto Script] Task1 - Found {len(results)} rows in director_link table matching both media_id and media_type", xbmc.LOGDEBUG)
        
        if not results:
            conn.close()
            xbmc.log(f"[CastPhoto Script] Task1 - No results found in director_link table matching both media_id and media_type", xbmc.LOGDEBUG)
            return
            
        # 由于我们已经在SQL中过滤了media_type，现在只需取第一个结果
        target_row = results[0]
        actor_id = target_row[0]
        xbmc.log(f"[CastPhoto Script] Task1 - Actor ID: {actor_id}", xbmc.LOGDEBUG)
        
        # 查询actor表
        cursor.execute("SELECT art_urls, name FROM actor WHERE actor_id = ?", (actor_id,))
        actor_result = cursor.fetchone()
        
        xbmc.log(f"[CastPhoto Script] Task1 - Actor query result: {actor_result}", xbmc.LOGDEBUG)
        
        if actor_result and actor_result[0]:
            art_urls = actor_result[0]
            name = actor_result[1]  # 获取name字段
            xbmc.log(f"[CastPhoto Script] Task1 - Raw art_urls: {art_urls}", xbmc.LOGDEBUG)
            xbmc.log(f"[CastPhoto Script] Task1 - Actor name: {name}", xbmc.LOGDEBUG)
            
            # 只要art_urls非空，就设置directorimg标志
            if art_urls and art_urls.strip():  # 检查art_urls是否非空
                set_skin_string('directorimg', '1')
                xbmc.log(f"[CastPhoto Script] Task1 - Set directorimg=1", xbmc.LOGDEBUG)
                
                # 检查当前ListItem.Director是否为空值
                current_director = get_listitem_info('Director')
                xbmc.log(f"[CastPhoto Script] Task1 - Current ListItem.Director: '{current_director}'", xbmc.LOGDEBUG)
                
                if not current_director or current_director.strip() == '':
                    # 如果Director为空，设置directorname
                    if name:
                        set_skin_string('directorname', name)
                        xbmc.log(f"[CastPhoto Script] Task1 - Set directorname={name}", xbmc.LOGDEBUG)
                    else:
                        xbmc.log(f"[CastPhoto Script] Task1 - Name field is empty, cannot set directorname", xbmc.LOGDEBUG)
                
                # 提取URL（如果包含<thumb></thumb>标签）
                extracted_url = extract_url_from_thumb_tag(art_urls)
                xbmc.log(f"[CastPhoto Script] Task1 - Extracted URL: {extracted_url}", xbmc.LOGDEBUG)
                
                # 直接设置directorurl为提取后的URL
                set_skin_string('directorurl', extracted_url)
                xbmc.log(f"[CastPhoto Script] Task1 - Set directorurl={extracted_url}", xbmc.LOGDEBUG)
        else:
            xbmc.log(f"[CastPhoto Script] Task1 - No art_urls found or art_urls is empty", xbmc.LOGDEBUG)
        
        conn.close()
        xbmc.log(f"[CastPhoto Script] Task1 completed", xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f"[CastPhoto Script] Task1 Error: {str(e)}", xbmc.LOGERROR)

def execute_task2(db_path, dbtype, dbid):
    """任务2：获取评分信息"""
    try:
        xbmc.log(f"[CastPhoto Script] Task2 started - DBTYPE: {dbtype}, DBID: {dbid}", xbmc.LOGDEBUG)
        
        conn = sqlite3.connect(Path(db_path).as_uri() + '?mode=ro', uri=True)
        cursor = conn.cursor()
        
        # 查询rating表
        cursor.execute("SELECT rating, rating_type, media_type FROM rating WHERE media_id = ?", (dbid,))
        results = cursor.fetchall()
        
        xbmc.log(f"[CastPhoto Script] Task2 - Found {len(results)} rows in rating table", xbmc.LOGDEBUG)
        
        if not results:
            conn.close()
            xbmc.log(f"[CastPhoto Script] Task2 - No results found in rating table", xbmc.LOGDEBUG)
            return
            
        # 如果有多行，根据media_type筛选
        filtered_by_media_type = []
        if len(results) > 1:
            for row in results:
                xbmc.log(f"[CastPhoto Script] Task2 - Checking row: rating={row[0]}, rating_type={row[1]}, media_type={row[2]}", xbmc.LOGDEBUG)
                if row[2] == dbtype:
                    filtered_by_media_type.append(row)
                    xbmc.log(f"[CastPhoto Script] Task2 - Added row matching media_type", xbmc.LOGDEBUG)
        else:
            filtered_by_media_type = [row for row in results if row[2] == dbtype]
            xbmc.log(f"[CastPhoto Script] Task2 - Using single result", xbmc.LOGDEBUG)
            
        # 进一步筛选rating_type包含imdb、tomato、douban、popcorn的行
        final_results = []
        popcorn_rating = None
        for row in filtered_by_media_type:
            rating_type_lower = row[1].lower()
            if 'imdb' in rating_type_lower or 'tomato' in rating_type_lower or 'douban' in rating_type_lower or 'popcorn' in rating_type_lower:
                final_results.append(row)
                xbmc.log(f"[CastPhoto Script] Task2 - Kept row with rating_type: {row[1]}", xbmc.LOGDEBUG)
                
                # 特别处理popcorn评分
                if 'popcorn' in rating_type_lower:
                    rating_value = float(row[0])
                    if rating_value < 10:
                        popcorn_rating = round(rating_value * 10)
                        xbmc.log(f"[CastPhoto Script] Task2 - Popcorn rating < 10, multiplying by 10: {rating_value} -> {rating_value * 10}, rounded to: {popcorn_rating}", xbmc.LOGDEBUG)
                    else:
                        popcorn_rating = round(rating_value)
                        xbmc.log(f"[CastPhoto Script] Task2 - Popcorn rating >= 10, rounding directly: {rating_value}, rounded to: {popcorn_rating}", xbmc.LOGDEBUG)
        
        xbmc.log(f"[CastPhoto Script] Task2 - After filtering by rating_type, {len(final_results)} rows remain", xbmc.LOGDEBUG)
        
        # 如果最终结果大于等于一行，则设置embyrating
        if len(final_results) >= 1:
            set_skin_string('embyrating', '1')
            xbmc.log(f"[CastPhoto Script] Task2 - Set embyrating=1", xbmc.LOGDEBUG)
            
            # 处理各种评分类型
            for row in final_results:
                rating_value = float(row[0])  # 转换为浮点数
                rating_type_lower = row[1].lower()
                
                if 'imdb' in rating_type_lower:
                    # IMDB评分：保留一位小数（四舍五入）
                    imdb_rating = round(rating_value, 1)
                    set_skin_string('embyimdb', str(imdb_rating))
                    xbmc.log(f"[CastPhoto Script] Task2 - Set embyimdb={imdb_rating} (from {rating_value})", xbmc.LOGDEBUG)
                elif 'tomato' in rating_type_lower:
                    # Tomato评分：如果值小于10则乘以10再四舍五入，否则直接四舍五入
                    if rating_value < 10:
                        tomato_rating = round(rating_value * 10)
                        xbmc.log(f"[CastPhoto Script] Task2 - Tomato rating < 10, multiplying by 10: {rating_value} -> {rating_value * 10}", xbmc.LOGDEBUG)
                    else:
                        tomato_rating = round(rating_value)
                        xbmc.log(f"[CastPhoto Script] Task2 - Tomato rating >= 10, rounding directly: {rating_value}", xbmc.LOGDEBUG)
                    set_skin_string('embytomato', str(tomato_rating))
                    xbmc.log(f"[CastPhoto Script] Task2 - Set embytomato={tomato_rating} (from {rating_value})", xbmc.LOGDEBUG)
                elif 'douban' in rating_type_lower:
                    # Douban评分：保留一位小数（四舍五入）
                    douban_rating = round(rating_value, 1)
                    set_skin_string('embydouban', str(douban_rating))
                    xbmc.log(f"[CastPhoto Script] Task2 - Set embydouban={douban_rating} (from {rating_value})", xbmc.LOGDEBUG)
                # popcorn评分已经在上面处理过了
        
        # 设置popcorn评分（如果有）
        if popcorn_rating is not None:
            set_skin_string('embypopcorn', str(popcorn_rating))
            xbmc.log(f"[CastPhoto Script] Task2 - Set embypopcorn={popcorn_rating}", xbmc.LOGDEBUG)
                
        conn.close()
        xbmc.log(f"[CastPhoto Script] Task2 completed", xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f"[CastPhoto Script] Task2 Error: {str(e)}", xbmc.LOGERROR)

def execute_task3(db_path, dbtype, dbid):
    """任务3：获取用户评分信息"""
    try:
        xbmc.log(f"[CastPhoto Script] Task3 started - DBTYPE: {dbtype}, DBID: {dbid}", xbmc.LOGDEBUG)
        
        conn = sqlite3.connect(Path(db_path).as_uri() + '?mode=ro', uri=True)
        cursor = conn.cursor()
        
        # 根据DBTYPE确定表名和ID字段名
        if dbtype == 'movie':
            table_name = 'movie'
            id_field = 'idMovie'
        elif dbtype == 'episode':
            table_name = 'episode'
            id_field = 'idepisode'
        elif dbtype == 'tvshow':
            table_name = 'tvshow'
            id_field = 'idshow'
        else:
            xbmc.log(f"[CastPhoto Script] Task3 - Unsupported DBTYPE: {dbtype}", xbmc.LOGDEBUG)
            conn.close()
            return
        
        # 查询对应的表
        query = f"SELECT userrating FROM {table_name} WHERE {id_field} = ?"
        cursor.execute(query, (dbid,))
        result = cursor.fetchone()
        
        if result and result[0] is not None:
            userrating_value = float(result[0])
            # 保留一位小数（四舍五入）
            formatted_userrating = round(userrating_value, 1)
            
            set_skin_string('userrating1', str(formatted_userrating))
            xbmc.log(f"[CastPhoto Script] Task3 - Set userrating1={formatted_userrating} (from {userrating_value})", xbmc.LOGDEBUG)
        else:
            xbmc.log(f"[CastPhoto Script] Task3 - No userrating found or userrating is NULL", xbmc.LOGDEBUG)
        
        conn.close()
        xbmc.log(f"[CastPhoto Script] Task3 completed", xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f"[CastPhoto Script] Task3 Error: {str(e)}", xbmc.LOGERROR)

def handle_director_option():
    """处理带director参数的逻辑"""
    # 获取当前项目类型
    dbtype = get_listitem_info('DBTYPE')
    xbmc.log(f"[CastPhoto Script] Director option - Current item DBTYPE: {dbtype}", xbmc.LOGDEBUG)
    
    # 检查是否为movie或episode
    if dbtype not in ['movie', 'episode', 'tvshow']:
        xbmc.log(f"[CastPhoto Script] Director option - Not a supported type (movie, episode, tvshow), exiting.", xbmc.LOGDEBUG)
        return
    
    # 获取数据库ID
    dbid = get_listitem_info('DBID')
    xbmc.log(f"[CastPhoto Script] Director option - Current item DBID: {dbid}", xbmc.LOGDEBUG)
    
    if not dbid or dbid == '':
        xbmc.log("[CastPhoto Script] Director option - No DBID found, exiting.", xbmc.LOGDEBUG)
        return
        
    try:
        dbid = int(dbid)
        xbmc.log(f"[CastPhoto Script] Director option - Parsed DBID as integer: {dbid}", xbmc.LOGDEBUG)
    except ValueError:
        xbmc.log("[CastPhoto Script] Director option - Invalid DBID, exiting.", xbmc.LOGDEBUG)
        return

    # 弹出选择窗口
    dialog = xbmcgui.Dialog()
    options = ["手动上传导演头像", "列出媒体库该导演作品"]
    selected = dialog.select("导演操作", options)
    
    if selected == 0:  # 手动上传导演头像
        # 弹出图片选择窗口
        image_path = dialog.browseSingle(1, '选择导演头像', 'pictures')
        if image_path:
            xbmc.log(f"[CastPhoto Script] Selected image: {image_path}", xbmc.LOGDEBUG)
            
            # 获取数据库路径
            try:
                import xbmcvfs
                db_path = xbmcvfs.translatePath("special://userdata/Database/MyVideos131.db")
            except:
                db_path = xbmc.translatePath("special://userdata/Database/MyVideos131.db") if hasattr(xbmc, 'translatePath') else "special://userdata/Database/MyVideos131.db"
            
            xbmc.log(f"[CastPhoto Script] Database path: {db_path}", xbmc.LOGDEBUG)
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # 在director_link表中查找匹配的记录
                cursor.execute("SELECT actor_id FROM director_link WHERE media_id = ? AND media_type = ?", (dbid, dbtype))
                result = cursor.fetchone()
                
                if result:
                    # 情况1：找到了匹配的记录
                    actor_id = result[0]
                    xbmc.log(f"[CastPhoto Script] Found existing actor_id: {actor_id}", xbmc.LOGDEBUG)
                    
                    # 更新actor表中的art_urls字段
                    cursor.execute("UPDATE actor SET art_urls = ? WHERE actor_id = ?", (image_path, actor_id))
                    conn.commit()
                    xbmc.log(f"[CastPhoto Script] Updated actor {actor_id} art_urls to: {image_path}", xbmc.LOGDEBUG)
                    
                    # 设置skin string
                    set_skin_string('directorurl', image_path)
                    xbmc.log(f"[CastPhoto Script] Set Skin.SetString(directorurl, {image_path})", xbmc.LOGDEBUG)
                else:
                    # 情况2：未找到匹配的记录，需要创建新记录
                    xbmc.log(f"[CastPhoto Script] No existing record found, creating new entries", xbmc.LOGDEBUG)
                    
                    # 获取当前最大的actor_id
                    cursor.execute("SELECT MAX(actor_id) FROM actor")
                    max_id_result = cursor.fetchone()
                    if max_id_result[0] is not None:
                        new_actor_id = max_id_result[0] + 1
                    else:
                        new_actor_id = 1
                    
                    # 获取ListItem.Director的值
                    director_name = get_listitem_info('Director')
                    if not director_name or director_name.strip() == '':
                        director_name = None
                    
                    # 在actor表中插入新记录
                    cursor.execute("INSERT INTO actor (actor_id, name, art_urls) VALUES (?, ?, ?)", 
                                   (new_actor_id, director_name, image_path))
                    conn.commit()
                    xbmc.log(f"[CastPhoto Script] Inserted new actor with id: {new_actor_id}, name: {director_name}, art_urls: {image_path}", xbmc.LOGDEBUG)
                    
                    # 在director_link表中插入新记录
                    cursor.execute("INSERT INTO director_link (actor_id, media_id, media_type) VALUES (?, ?, ?)",
                                   (new_actor_id, dbid, dbtype))
                    conn.commit()
                    xbmc.log(f"[CastPhoto Script] Inserted new director_link record with actor_id: {new_actor_id}, media_id: {dbid}, media_type: {dbtype}", xbmc.LOGDEBUG)
                    
                    # 设置skin string
                    set_skin_string('directorurl', image_path)
                    xbmc.log(f"[CastPhoto Script] Set Skin.SetString(directorurl, {image_path})", xbmc.LOGDEBUG)
                
                conn.close()
                xbmc.log(f"[CastPhoto Script] Director image update completed", xbmc.LOGDEBUG)
            except Exception as e:
                xbmc.log(f"[CastPhoto Script] Error updating director image: {str(e)}", xbmc.LOGERROR)
        else:
            xbmc.log(f"[CastPhoto Script] No image selected", xbmc.LOGDEBUG)
    
    elif selected == 1:  # 列出媒体库该导演作品
        xbmc.executebuiltin("SendClick(2003,13)")
        xbmc.log(f"[CastPhoto Script] Executed SendClick(2003,13)", xbmc.LOGDEBUG)

def main():
    global PUBLISHER
    # 检查是否有'director'参数
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'director':
        handle_director_option()
        return
    
    PUBLISHER = DetailPublication()
    if not PUBLISHER.valid():
        return

    # 将所有相关的皮肤字符串设为空值
    xbmc.log(f"[CastPhoto Script] Initializing - clearing all skin strings", xbmc.LOGDEBUG)
    set_skin_string('directorimg', '')
    set_skin_string('directorurl', '')
    set_skin_string('embyrating', '')
    set_skin_string('embytomato', '')
    set_skin_string('embyimdb', '')
    set_skin_string('embydouban', '')
    set_skin_string('embypopcorn', '')
    set_skin_string('directorname', '')
    set_skin_string('userrating1', '')
    
    # 获取当前项目类型与数据库ID（优先取 onload 同步锁死的窗口身份，避免延迟启动期间焦点漂移）
    ident_type, _, ident_id = (PUBLISHER.identity or '').partition(':')
    dbtype = ident_type or get_listitem_info('DBTYPE')
    xbmc.log(f"[CastPhoto Script] Current item DBTYPE: {dbtype}", xbmc.LOGDEBUG)
    
    # 检查是否为movie或episode
    if dbtype not in ['movie', 'episode', 'tvshow']:
        xbmc.log(f"[CastPhoto Script] Not a supported type (movie, episode, tvshow), exiting.", xbmc.LOGDEBUG)
        return
    
    # 获取数据库ID
    dbid = ident_id or get_listitem_info('DBID')
    xbmc.log(f"[CastPhoto Script] Current item DBID: {dbid}", xbmc.LOGDEBUG)
    
    if not dbid or dbid == '':
        xbmc.log("[CastPhoto Script] No DBID found, exiting.", xbmc.LOGDEBUG)
        return
        
    try:
        dbid = int(dbid)
        xbmc.log(f"[CastPhoto Script] Parsed DBID as integer: {dbid}", xbmc.LOGDEBUG)
    except ValueError:
        xbmc.log("[CastPhoto Script] Invalid DBID, exiting.", xbmc.LOGDEBUG)
        return
    
    # 数据库路径
    try:
        import xbmcvfs
        db_path = xbmcvfs.translatePath("special://userdata/Database/MyVideos131.db")
    except:
        db_path = xbmc.translatePath("special://userdata/Database/MyVideos131.db") if hasattr(xbmc, 'translatePath') else "special://userdata/Database/MyVideos131.db"
    
    xbmc.log(f"[CastPhoto Script] Database path: {db_path}", xbmc.LOGDEBUG)
    
    # 创建线程执行三个任务
    task1_thread = threading.Thread(target=execute_task1, args=(db_path, dbtype, dbid))
    task2_thread = threading.Thread(target=execute_task2, args=(db_path, dbtype, dbid))
    task3_thread = threading.Thread(target=execute_task3, args=(db_path, dbtype, dbid))
    
    # 启动线程
    xbmc.log(f"[CastPhoto Script] Starting threads", xbmc.LOGDEBUG)
    task1_thread.start()
    task2_thread.start()
    task3_thread.start()
    
    # 等待线程完成
    task1_thread.join()
    task2_thread.join()
    task3_thread.join()
    
    xbmc.log(f"[CastPhoto Script] All tasks completed", xbmc.LOGDEBUG)

if __name__ == '__main__':
    main()
