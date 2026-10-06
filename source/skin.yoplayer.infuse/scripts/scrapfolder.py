# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：管理已刮削的电影/电视剧目录（查看/删除/刷新）+ 原路径设置功能
放置路径：special://skin/scripts/scrapfolder.py
调用方式1：RunScript(special://skin/scripts/scrapfolder.py)  # 原功能（设置皮肤字符串）
调用方式2：RunScript(special://skin/scripts/scrapfolder.py,mofolder)  # 电影目录管理
调用方式3：RunScript(special://skin/scripts/scrapfolder.py,tvfolder)  # 电视剧目录管理
调用方式4：RunScript(special://skin/scripts/scrapfolder.py,folder)  # 统一入口（电影/剧集二选一）
"""
import xbmc
import xbmcvfs
import xbmcgui
import sqlite3
import os
import sys

# 全局配置
DB_VERSION = 131  # 数据库版本，根据KODI版本调整
DIALOG = xbmcgui.Dialog()  # KODI对话框实例

def get_myvideos_db_path():
    """获取MyVideos数据库路径（兼容KODI 19+/20+/21+）"""
    try:
        userdata_path = xbmcvfs.translatePath("special://userdata/")
    except AttributeError:
        userdata_path = xbmc.translatePath("special://userdata/")
    db_path = os.path.join(userdata_path, "Database", f"MyVideos{DB_VERSION}.db")
    return xbmcvfs.validatePath(db_path)

def query_content_paths(content_type):
    """
    通用查询函数：查询指定content_type的strPath列表
    :param content_type: 内容类型（movies/tvshows）
    :return: 纯路径列表 [path1, path2, ...]
    """
    db_path = get_myvideos_db_path()
    path_list = []
    if not xbmcvfs.exists(db_path):
        DIALOG.ok("错误", f"数据库文件不存在：{db_path}")
        xbmc.log(f"[scrapfolder] 错误：数据库文件不存在 {db_path}", level=xbmc.LOGERROR)
        return path_list

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT strPath FROM path WHERE strContent = ? AND strPath IS NOT NULL",
            (content_type,)
        )
        path_list = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        xbmc.log(f"[scrapfolder] 读取到{content_type}路径数量：{len(path_list)}", level=xbmc.LOGINFO)
    except Exception as e:
        DIALOG.ok("错误", f"读取数据库失败：{str(e)}")
        xbmc.log(f"[scrapfolder] 读取{content_type}失败：{str(e)}", level=xbmc.LOGERROR)
    return path_list

def delete_content_path(content_type, str_path=None, delete_all=False):
    """
    通用删除函数：删除指定content_type的路径（单个/全部）
    删除成功后自动刷新皮肤字符串
    :param content_type: 内容类型（movies/tvshows）
    :param str_path: 要删除的strPath（单个删除）
    :param delete_all: 是否删除全部路径
    """
    db_path = get_myvideos_db_path()
    if not xbmcvfs.exists(db_path):
        DIALOG.ok("错误", f"数据库文件不存在：{db_path}")
        return

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        if delete_all:
            # 删除全部指定类型的行
            cursor.execute("DELETE FROM path WHERE strContent = ?", (content_type,))
            type_name = "电影" if content_type == "movies" else "电视剧"
            msg = f"全部已刮削{type_name}目录"
        else:
            # 精准删除指定路径的行
            cursor.execute(
                "DELETE FROM path WHERE strContent = ? AND strPath = ?",
                (content_type, str_path)
            )
            msg = f"刮削目录：{str_path}"
        
        conn.commit()
        cursor.close()
        conn.close()

        # 删除成功后自动刷新皮肤字符串
        xbmc.executebuiltin('RunScript(special://skin/scripts/scrapfolder.py)')
        xbmc.log(f"[scrapfolder] 删除{msg}后，执行刷新皮肤字符串脚本", level=xbmc.LOGINFO)

        DIALOG.ok("成功", f"已删除{msg}！\n刮削目录已自动刷新")
    except Exception as e:
        DIALOG.ok("错误", f"删除失败：{str(e)}")
        xbmc.log(f"[scrapfolder] 删除{msg}失败：{str(e)}", level=xbmc.LOGERROR)

def show_view_content_paths(content_type):
    """
    通用查看函数：查看指定content_type的已刮削目录
    :param content_type: 内容类型（movies/tvshows）
    """
    type_name = "电影" if content_type == "movies" else "电视剧"
    paths = query_content_paths(content_type)
    
    if not paths:
        DIALOG.ok("提示", f"暂无已刮削的{type_name}目录！")
        return
    
    # 弹窗选择要查看的路径
    selected_idx = DIALOG.select(f"选择要查看的{type_name}刮削目录", paths)
    if selected_idx == -1:
        return
    
    # 激活视频窗口到选中路径
    target_path = paths[selected_idx]
    xbmc.executebuiltin(f'ActivateWindow(Videos, {target_path}, return)')
    xbmc.log(f"[scrapfolder] 激活视频窗口到{type_name}路径：{target_path}", level=xbmc.LOGINFO)

def show_delete_content_paths(content_type):
    """
    通用删除弹窗函数：删除指定content_type的已刮削目录
    :param content_type: 内容类型（movies/tvshows）
    """
    type_name = "电影" if content_type == "movies" else "电视剧"
    paths = query_content_paths(content_type)
    
    if not paths:
        DIALOG.ok("提示", f"暂无已刮削的{type_name}目录！")
        return
    
    # 构造删除选项列表（第一项=删除全部，后续=各路径）
    delete_options = [f"删除全部已刮削{type_name}目录"] + paths
    selected_idx = DIALOG.select(f"选择要删除的{type_name}刮削目录", delete_options)
    
    if selected_idx == -1:
        return
    
    # 处理删除全部
    if selected_idx == 0:
        confirm = DIALOG.yesno(
            "确认删除", 
            f"是否确定删除全部已刮削的{type_name}目录？\n此操作不可恢复！"
        )
        if confirm:
            delete_content_path(content_type, delete_all=True)
    # 处理删除单个路径
    else:
        selected_path = delete_options[selected_idx]
        confirm = DIALOG.yesno(
            "确认删除", 
            f"是否确定删除以下{type_name}刮削目录？\n{selected_path}\n此操作不可恢复！"
        )
        if confirm:
            delete_content_path(content_type, str_path=selected_path)

def handle_mofolder_param():
    """处理mofolder参数：电影目录管理（新增刷新选项）"""
    # 新增第三个选项：刷新已刮削目录
    main_options = ["查看已刮削目录", "删除已刮削目录", "刷新已刮削目录"]
    selected_idx = DIALOG.select("电影刮削目录管理", main_options)
    if selected_idx == -1:
        return
    if selected_idx == 0:
        show_view_content_paths("movies")
    elif selected_idx == 1:
        show_delete_content_paths("movies")
    elif selected_idx == 2:  # 处理刷新逻辑
        # 执行无参数脚本刷新皮肤字符串
        xbmc.executebuiltin('RunScript(special://skin/scripts/scrapfolder.py)')
        xbmc.log(f"[scrapfolder] 手动触发刮削目录皮肤字符串刷新（电影管理入口）", level=xbmc.LOGINFO)
        DIALOG.ok("成功", "已手动刷新刮削目录！")

def handle_tvfolder_param():
    """处理tvfolder参数：电视剧目录管理（新增刷新选项）"""
    # 新增第三个选项：刷新已刮削目录
    main_options = ["查看已刮削目录", "删除已刮削目录", "刷新已刮削目录"]
    selected_idx = DIALOG.select("电视剧刮削目录管理", main_options)
    if selected_idx == -1:
        return
    if selected_idx == 0:
        show_view_content_paths("tvshows")
    elif selected_idx == 1:
        show_delete_content_paths("tvshows")
    elif selected_idx == 2:  # 处理刷新逻辑
        # 执行无参数脚本刷新皮肤字符串
        xbmc.executebuiltin('RunScript(special://skin/scripts/scrapfolder.py)')
        xbmc.log(f"[scrapfolder] 手动触发刮削目录皮肤字符串刷新（电视剧管理入口）", level=xbmc.LOGINFO)
        DIALOG.ok("成功", "已手动刷新刮削目录！")

def handle_folder_param():
    """处理folder参数：统一入口（新增刷新选项）"""
    # 新增第三个选项：刷新已刮削目录
    main_options = ["电影已刮削目录", "剧集已刮削目录", "刷新已刮削目录"]
    selected_idx = DIALOG.select("刮削目录管理", main_options)
    
    if selected_idx == -1:  # 用户取消选择
        return
    elif selected_idx == 0:  # 选择电影已刮削目录，调用mofolder逻辑
        xbmc.executebuiltin('RunScript(special://skin/scripts/scrapfolder.py,mofolder)')
        xbmc.log(f"[scrapfolder] 触发电影刮削目录管理", level=xbmc.LOGINFO)
    elif selected_idx == 1:  # 选择剧集已刮削目录，调用tvfolder逻辑
        xbmc.executebuiltin('RunScript(special://skin/scripts/scrapfolder.py,tvfolder)')
        xbmc.log(f"[scrapfolder] 触发剧集刮削目录管理", level=xbmc.LOGINFO)
    elif selected_idx == 2:  # 处理刷新逻辑
        # 执行无参数脚本刷新皮肤字符串
        xbmc.executebuiltin('RunScript(special://skin/scripts/scrapfolder.py)')
        xbmc.log(f"[scrapfolder] 手动触发刮削目录皮肤字符串刷新（统一入口）", level=xbmc.LOGINFO)
        DIALOG.ok("成功", "已手动刷新刮削目录！")

def set_skin_strings():
    """原功能：设置movies/tvshows皮肤字符串"""
    db_path = get_myvideos_db_path()
    
    # 处理Movies路径
    movie_paths = query_content_paths("movies")
    movie_str = "_".join(movie_paths)
    safe_movie = movie_str.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")
    xbmc.executebuiltin(f'Skin.setString(scmoviepath, "{safe_movie}")')
    xbmc.log(f"[scrapfolder] 已设置scmoviepath：{safe_movie[:50]}...", level=xbmc.LOGINFO)
    
    # 处理TVShows路径
    try:
        tvshow_paths = query_content_paths("tvshows")
        tvshow_str = "_".join(tvshow_paths)
        safe_tvshow = tvshow_str.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")
        xbmc.executebuiltin(f'Skin.setString(sctvshowpath, "{safe_tvshow}")')
        xbmc.log(f"[scrapfolder] 已设置sctvshowpath：{safe_tvshow[:50]}...", level=xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[scrapfolder] 读取tvshows失败：{str(e)}", level=xbmc.LOGERROR)

def main():
    """主函数：判断参数并执行对应逻辑"""
    args = sys.argv[1:]
    if "mofolder" in args:
        handle_mofolder_param()
    elif "tvfolder" in args:
        handle_tvfolder_param()
    elif "folder" in args:
        handle_folder_param()
    else:
        set_skin_strings()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        DIALOG.ok("脚本执行失败", f"错误信息：{str(e)}")
        xbmc.log(f"[scrapfolder] 脚本执行失败：{str(e)}", level=xbmc.LOGERROR)
        raise    