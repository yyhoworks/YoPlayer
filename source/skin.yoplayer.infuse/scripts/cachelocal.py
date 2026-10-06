import os
import sys
import glob
import sqlite3
import xbmc
import xbmcvfs

# 兼容 Kodi 18 (Leia) 和 Kodi 19+ (Matrix/Nexus/Omega)
try:
    translate_path = xbmcvfs.translatePath
except AttributeError:
    translate_path = xbmc.translatePath

def get_latest_db(prefix):
    """获取指定前缀的最新修改的数据库文件路径"""
    db_dir = translate_path('special://userdata/Database/')
    pattern = os.path.join(db_dir, '{}*.db'.format(prefix))
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    # 按文件修改时间降序排序，获取最新的一个
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def process_databases(monitor, thumb_abs_path):
    """处理视频数据库和纹理数据库的URL替换"""
    video_db_path = get_latest_db('MyVideo')
    texture_db_path = get_latest_db('Textures')

    if not video_db_path or not texture_db_path:
        xbmc.log('CacheLocal: 无法找到视频数据库或纹理数据库文件。', xbmc.LOGERROR)
        return

    # 连接数据库，设置 timeout 防止被 Kodi 主进程锁定时直接报错
    try:
        video_conn = sqlite3.connect(video_db_path, timeout=10.0)
        texture_conn = sqlite3.connect(texture_db_path, timeout=10.0)
    except sqlite3.OperationalError as e:
        xbmc.log('CacheLocal: 数据库连接失败: {}'.format(e), xbmc.LOGERROR)
        return

    video_cur = video_conn.cursor()
    texture_cur = texture_conn.cursor()

    try:
        # 查询 art 表中以 http 开头的 url (自动跳过 image:// 和 special://)
        video_cur.execute("SELECT art_id, url FROM art WHERE url LIKE 'http%'")
        rows = video_cur.fetchall()

        for art_id, url in rows:
            # 在纹理数据库的 texture 表中查找对应的缓存路径
            texture_cur.execute("SELECT cachedurl FROM texture WHERE url = ?", (url,))
            result = texture_cur.fetchone()

            if result:
                cachedurl = result[0]
                # 拼接本地绝对路径前缀
                # thumb_abs_path 已经是类似 /storage/.kodi/userdata/Thumbnails/ 的绝对路径
                new_url = "{}{}".format(thumb_abs_path, cachedurl)
                
                # 覆盖写回到视频数据库 art 表
                video_cur.execute("UPDATE art SET url = ? WHERE art_id = ?", (new_url, art_id))
                video_conn.commit()

            # 每处理完一行，根据播放状态决定延时时间
            has_media = xbmc.getCondVisibility('Player.HasMedia')
            sleep_time = 1.0 if has_media else 0.3
            
            # 使用 waitForAbort 进行延时，以便在等待期间能响应退出信号
            if monitor.waitForAbort(sleep_time):
                break

    except sqlite3.OperationalError as e:
        xbmc.log('CacheLocal: 数据库操作出错: {}'.format(e), xbmc.LOGERROR)
    finally:
        video_conn.close()
        texture_conn.close()

def main():
    # 检查是否带有 'start' 参数
    if 'start' not in sys.argv:
        return

    # 动态获取 Thumbnails 文件夹的绝对物理路径
    # 这将把 special://userdata/Thumbnails/ 转换为如 /storage/.kodi/userdata/Thumbnails/
    thumb_special_path = 'special://userdata/Thumbnails/'
    thumb_abs_path = translate_path(thumb_special_path)
    
    # 确保路径以斜杠结尾，以便后续拼接
    if not thumb_abs_path.endswith(os.sep):
        thumb_abs_path += os.sep
        
    xbmc.log('CacheLocal: 脚本已启动，缩略图绝对路径前缀: {}'.format(thumb_abs_path), xbmc.LOGINFO)
    
    monitor = xbmc.Monitor()

    # 主循环，直到 Kodi 请求退出
    while not monitor.abortRequested():
        process_databases(monitor, thumb_abs_path)
        
        # 全部行处理完毕后，等待 15 分钟 (900秒) 再开始下一轮
        # waitForAbort 会在超时后返回 False，如果 Kodi 退出则返回 True
        if monitor.waitForAbort(100):
            break

    xbmc.log('CacheLocal: 脚本已安全退出。', xbmc.LOGINFO)

if __name__ == '__main__':
    main()