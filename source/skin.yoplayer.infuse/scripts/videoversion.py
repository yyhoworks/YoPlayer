import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import sqlite3
import os

def get_listitem_info():
    """获取当前列表项的DBTYPE和DBID"""
    dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
    dbid = xbmc.getInfoLabel('ListItem.DBID')
    
    if not dbtype or not dbid:
        xbmc.log("无法获取ListItem信息: DBTYPE={}, DBID={}".format(dbtype, dbid), xbmc.LOGERROR)
        return None, None
    
    try:
        dbid = int(dbid)
    except ValueError:
        xbmc.log("DBID不是有效数字: {}".format(dbid), xbmc.LOGERROR)
        return None, None
    
    return dbtype, dbid

def get_database_path():
    """获取视频数据库路径"""
    # 构建数据库文件路径
    db_path = xbmcvfs.translatePath('special://userdata/Database/MyVideos131.db')
    
    if not os.path.exists(db_path):
        xbmc.log("数据库文件不存在: {}".format(db_path), xbmc.LOGERROR)
        return None
    
    xbmc.log("使用数据库文件: {}".format(db_path), xbmc.LOGINFO)
    return db_path

def find_videoversion_poster_entry(db_path, media_id):
    """查找videoversion poster条目"""
    query = """
    SELECT art_id, url 
    FROM art 
    WHERE media_id = ? AND media_type = 'videoversion' AND type = 'poster'
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute(query, (media_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        xbmc.log("查找videoversion poster条目失败: {}".format(str(e)), xbmc.LOGERROR)
        return None

def find_original_poster_url(db_path, media_id, media_type):
    """查找原始媒体类型的poster URL"""
    query = """
    SELECT url 
    FROM art 
    WHERE media_id = ? AND media_type = ? AND type = 'poster' AND url != '' AND url IS NOT NULL
    LIMIT 1
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute(query, (media_id, media_type))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        xbmc.log("查找原始poster URL失败: {}".format(str(e)), xbmc.LOGERROR)
        return None

def get_movie_file_id(db_path, movie_id):
    """获取电影的文件ID"""
    query = "SELECT idFile FROM movie WHERE idMovie = ?"
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute(query, (movie_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        xbmc.log("获取电影文件ID失败: {}".format(str(e)), xbmc.LOGERROR)
        return None

def get_next_art_id(db_path):
    """获取下一个可用的art_id"""
    query = "SELECT MAX(art_id) FROM art"
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()[0]
        conn.close()
        return 1 if result is None else result + 1
    except Exception as e:
        xbmc.log("获取下一个art_id失败: {}".format(str(e)), xbmc.LOGERROR)
        return 1

def update_videoversion_poster_url(db_path, art_id, new_url):
    """更新videoversion poster的URL"""
    query = "UPDATE art SET url = ? WHERE art_id = ?"
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute(query, (new_url, art_id))
        conn.commit()
        conn.close()
        xbmc.log("成功更新videoversion poster条目的URL", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log("更新videoversion poster URL失败: {}".format(str(e)), xbmc.LOGERROR)

def insert_videoversion_poster_entry(db_path, media_id, poster_url):
    """插入新的videoversion poster条目"""
    try:
        next_art_id = get_next_art_id(db_path)
        
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()
        
        query = """
        INSERT INTO art (art_id, media_id, media_type, type, url) 
        VALUES (?, ?, 'videoversion', 'poster', ?)
        """
        cursor.execute(query, (next_art_id, media_id, poster_url))
        conn.commit()
        conn.close()
        xbmc.log("成功插入新的videoversion poster条目", xbmc.LOGINFO)
        return next_art_id
    except Exception as e:
        xbmc.log("插入videoversion poster条目失败: {}".format(str(e)), xbmc.LOGERROR)
        return None

def insert_videoversion_poster_for_file(db_path, file_id, poster_url):
    """为文件ID插入videoversion poster条目"""
    try:
        next_art_id = get_next_art_id(db_path)
        
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()
        
        query = """
        INSERT INTO art (art_id, media_id, media_type, type, url) 
        VALUES (?, ?, 'videoversion', 'poster', ?)
        """
        cursor.execute(query, (next_art_id, file_id, poster_url))
        conn.commit()
        conn.close()
        xbmc.log("成功为文件ID插入videoversion poster条目", xbmc.LOGINFO)
        return next_art_id
    except Exception as e:
        xbmc.log("为文件ID插入videoversion poster条目失败: {}".format(str(e)), xbmc.LOGERROR)
        return None

def check_movieinfo_window_visible():
    """检查movieinformation窗口是否可见"""
    try:
        return xbmc.getCondVisibility('Window.IsActive(movieinformation)')
    except Exception as e:
        xbmc.log("检查movieinformation窗口状态失败: {}".format(str(e)), xbmc.LOGERROR)
        return False

def execute_sendclick_2003_14():
    """执行SendClick(2003,14)"""
    try:
        xbmc.executebuiltin('SendClick(2003,14)')
        xbmc.log("已发送点击事件(2003,14)", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log("发送点击事件失败: {}".format(str(e)), xbmc.LOGERROR)

def execute_action_select_sendclick_close_movieinfo():
    """执行Action(select)，然后SendClick(2003,14)，然后关闭movieinformation窗口"""
    try:
        # 执行Action(select)
        xbmc.executebuiltin('Action(select)')
        xbmc.sleep(500)  # 等待动作执行
        
        # 发送点击事件
        xbmc.executebuiltin('SendClick(2003,14)')
        xbmc.log("已发送点击事件(2003,14)", xbmc.LOGINFO)
        
        # 关闭movieinformation窗口
        xbmc.executebuiltin('Dialog.Close(movieinformation,true)')
        xbmc.log("movieinformation窗口已关闭", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log("执行操作序列失败: {}".format(str(e)), xbmc.LOGERROR)

def main():
    """主函数"""
    # 获取列表项信息
    dbtype, dbid = get_listitem_info()
    if not dbtype or not dbid:
        xbmc.log("无法获取列表项信息，退出脚本", xbmc.LOGERROR)
        return
    
    xbmc.log("获取到列表项信息 - DBTYPE: {}, DBID: {}".format(dbtype, dbid), xbmc.LOGINFO)
    
    # 获取数据库路径
    db_path = get_database_path()
    if not db_path:
        xbmc.log("无法获取数据库路径，退出脚本", xbmc.LOGERROR)
        return
    
    try:
        # 检查是否存在videoversion poster条目
        videoversion_poster_row = find_videoversion_poster_entry(db_path, dbid)
        
        if videoversion_poster_row:
            # 情况1: 找到了videoversion poster条目
            art_id, current_url = videoversion_poster_row
            xbmc.log("找到现有的videoversion poster条目，art_id: {}, 当前URL: {}".format(art_id, current_url), xbmc.LOGINFO)
            
            if current_url and current_url.strip():  # URL非空
                xbmc.log("videoversion poster条目的URL已存在，退出脚本", xbmc.LOGINFO)
                return
            else:  # 情况2: URL为空，需要更新
                original_poster_url = find_original_poster_url(db_path, dbid, dbtype)
                if original_poster_url:
                    update_videoversion_poster_url(db_path, art_id, original_poster_url)
                    xbmc.log("已用原始poster URL更新videoversion poster条目: {}".format(original_poster_url), xbmc.LOGINFO)
                    
                    # 关闭managevideoversions窗口
                    xbmc.executebuiltin('Dialog.Close(managevideoversions,true)')
                    xbmc.sleep(500)  # 等待窗口关闭
                    
                    # 判断movieinformation窗口是否可见
                    if check_movieinfo_window_visible():
                        # movieinformation窗口可见，只执行SendClick(2003,14)
                        execute_sendclick_2003_14()
                    else:
                        # movieinformation窗口不可见，执行Action(select)，然后SendClick(2003,14)，然后关闭movieinformation窗口
                        execute_action_select_sendclick_close_movieinfo()
                else:
                    xbmc.log("未找到原始poster URL", xbmc.LOGWARNING)
        else:
            # 情况3: 没有videoversion poster条目，需要创建
            xbmc.log("未找到videoversion poster条目，准备创建新条目", xbmc.LOGINFO)
            original_poster_url = find_original_poster_url(db_path, dbid, dbtype)
            if original_poster_url:
                # 插入针对媒体ID的poster记录
                insert_videoversion_poster_entry(db_path, dbid, original_poster_url)
                xbmc.log("已为媒体ID创建新的videoversion poster条目，URL: {}".format(original_poster_url), xbmc.LOGINFO)
                
                # 获取电影的文件ID
                movie_file_id = get_movie_file_id(db_path, dbid)
                if movie_file_id:
                    # 插入针对文件ID的poster记录
                    insert_videoversion_poster_for_file(db_path, movie_file_id, original_poster_url)
                    xbmc.log("已为文件ID创建新的videoversion poster条目，URL: {}".format(original_poster_url), xbmc.LOGINFO)
                else:
                    xbmc.log("未能获取电影的文件ID", xbmc.LOGWARNING)
                
                # 关闭managevideoversions窗口
                xbmc.executebuiltin('Dialog.Close(managevideoversions,true)')
                xbmc.sleep(500)  # 等待窗口关闭
                
                # 判断movieinformation窗口是否可见
                if check_movieinfo_window_visible():
                    # movieinformation窗口可见，只执行SendClick(2003,14)
                    execute_sendclick_2003_14()
                else:
                    # movieinformation窗口不可见，执行Action(select)，然后SendClick(2003,14)，然后关闭movieinformation窗口
                    execute_action_select_sendclick_close_movieinfo()
            else:
                xbmc.log("未找到原始poster URL，无法创建videoversion poster条目", xbmc.LOGWARNING)
        
    except Exception as e:
        xbmc.log("脚本执行出错: {}".format(str(e)), xbmc.LOGERROR)

if __name__ == '__main__':
    main()