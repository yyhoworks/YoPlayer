# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import os
import re
import json
from datetime import datetime
import time

def find_latest_videodb():
    """查找最新的MyVideos数据库文件"""
    db_folder = xbmcvfs.translatePath('special://userdata/Database/')
    db_files = []
    
    # 查找所有MyVideos数据库文件
    for filename in os.listdir(db_folder):
        if filename.startswith('MyVideos') and filename.endswith('.db'):
            full_path = os.path.join(db_folder, filename)
            mod_time = os.path.getmtime(full_path)
            db_files.append((full_path, mod_time))
    
    if not db_files:
        xbmcgui.Dialog().ok("错误", "未找到MyVideos数据库文件")
        return None
    
    # 按修改时间排序，返回最新文件
    latest_db = max(db_files, key=lambda x: x[1])
    return latest_db[0]

def execute_jsonrpc(method, params=None):
    """执行JSON-RPC命令"""
    query = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1
    }
    if params:
        query["params"] = params
    
    response = xbmc.executeJSONRPC(json.dumps(query))
    return json.loads(response)

def get_chinese_pinyin_initials(text):
    """获取中文文本的拼音首字母序列"""
    try:
        # 简化的中文到拼音首字母映射
        hanzi_ranges = [
            # 常见汉字范围的简化映射
            ('\u963f', '\u7231', 'A'), ('\u5427', '\u6ce2', 'B'), ('\u64e6', '\u9519', 'C'),
            ('\u8fbe', '\u5fb7', 'D'), ('\u989d', '\u997f', 'E'), ('\u53d1', '\u798f', 'F'),
            ('\u8be5', '\u9ad8', 'G'), ('\u54c8', '\u9ed1', 'H'), ('\u9e21', '\u4e5d', 'J'),
            ('\u5361', '\u79d1', 'K'), ('\u62c9', '\u6d1b', 'L'), ('\u5988', '\u6469', 'M'),
            ('\u62ff', '\u6d1c', 'N'), ('\u54e6', '\u6b27', 'O'), ('\u6015', '\u7834', 'P'),
            ('\u4e03', '\u7403', 'Q'), ('\u7136', '\u82e5', 'R'), ('\u6492', '\u6240', 'S'),
            ('\u4ed6', '\u7279', 'T'), ('\u54d4', '\u7a9d', 'W'), ('\u897f', '\u8840', 'X'),
            ('\u54c0', '\u7ea6', 'Y'), ('\u624e', '\u505a', 'Z')
        ]
        
        result = ""
        for char in text:
            found = False
            for start, end, initial in hanzi_ranges:
                if ord(start) <= ord(char) <= ord(end):
                    result += initial
                    found = True
                    break
            if not found:
                # 非中文字符处理
                if char.isalpha():
                    result += char.upper()
                elif char.isdigit():
                    result += char
                else:
                    result += 'Z'  # 其他字符默认为Z
        
        return result
    except:
        # 出错时返回原始文本的大写形式
        return text.upper()

def sort_by_pinyin(items_with_names):
    """按拼音首字母排序"""
    def get_sort_key(item_tuple):
        name = item_tuple[1]  # 获取名称
        if not name:
            return 'ZZZ'
        
        # 获取拼音首字母序列用于排序
        pinyin_key = get_chinese_pinyin_initials(name)
        return pinyin_key + name.lower()
    
    return sorted(items_with_names, key=get_sort_key)

def check_and_update_library():
    """检查进度条状态并在必要时更新媒体库"""
    start_time = time.time()
    while time.time() - start_time < 5:  # 监测5秒
        if xbmc.getCondVisibility('Window.IsVisible(extendedprogressdialog)'):
            xbmc.executebuiltin('UpdateLibrary(video,/storage/pictures)')
            break
        xbmc.sleep(500)  # 每0.5秒检查一次

def delete_scraper_folders():
    """情况1：删除已刮削文件夹(可多选)"""
    db_path = find_latest_videodb()
    if not db_path:
        return

    while True:
        try:
            # 检查数据库是否存在
            if not xbmcvfs.exists(db_path):
                xbmcgui.Dialog().ok("错误", f"数据库文件不存在: {db_path}")
                return
        
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
        
            # 查询path表中strScraper非空的记录
            cursor.execute("SELECT idPath, strPath, strContent, strScraper FROM path WHERE strScraper IS NOT NULL AND strScraper != ''")
            paths = cursor.fetchall()
        
            if not paths:
                xbmcgui.Dialog().ok("提示", "没有找到已刮削的路径")
                conn.close()
                return
        
            # 准备选项列表
            options = []
            for row in paths:
                id_path, str_path, str_content, _ = row
                if str_path:
                    content_type = "[电影]" if str_content == "movies" else "[剧集]" if str_content == "tvshows" else "[未知]"
                    display_text = f"{content_type}-{str_path}"
                    options.append((id_path, display_text, str_content, str_path))
        
            # 按拼音排序
            sorted_options = sort_by_pinyin(options)
            display_list = [item[1] for item in sorted_options]
        
            # 显示多选对话框
            dialog = xbmcgui.Dialog()
            selected_indices = dialog.multiselect("选择要删除的已刮削路径", display_list)
        
            if selected_indices is None or len(selected_indices) == 0:
                conn.close()
                return  # 返回到主选择窗口
        
            # 获取选中的路径信息
            selected_paths = [sorted_options[i] for i in selected_indices]
        
            # 确认删除
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除所选文件夹所有已刮削电影？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
        
            if not confirm:
                conn.close()
                continue  # 继续显示当前选择窗口（重新进入循环）
        
            # 统计删除数量
            path_deleted = 0
            movie_deleted = 0
            tvshow_deleted = 0
            episode_deleted = 0
        
            for selected_id_path, _, selected_content, selected_str_path in selected_paths:
                if selected_content == "movies":
                    # 删除电影
                    cursor.execute("DELETE FROM movie WHERE c23 = ?", (selected_id_path,))
                    movie_deleted += cursor.rowcount
                
                    # 同时删除path表中的记录
                    cursor.execute("DELETE FROM path WHERE idPath = ?", (selected_id_path,))
                    path_deleted += 1
                elif selected_content == "tvshows":
                    # 获取相关的剧集ID
                    cursor.execute("SELECT DISTINCT idShow FROM episode WHERE c19 = ?", (selected_id_path,))
                    show_ids = [row[0] for row in cursor.fetchall()]
                
                    if show_ids:
                        placeholders = ','.join(['?' for _ in show_ids])
                    
                        # 删除单集
                        cursor.execute(f"DELETE FROM episode WHERE c19 = ? AND idShow IN ({placeholders})", [selected_id_path] + show_ids)
                        episode_deleted += cursor.rowcount
                    
                        # 删除剧集
                        cursor.execute(f"DELETE FROM tvshow WHERE idShow IN ({placeholders})", show_ids)
                        tvshow_deleted += cursor.rowcount
                    
                        # 删除季信息
                        cursor.execute(f"DELETE FROM seasons WHERE idShow IN ({placeholders})", show_ids)
                    else:
                        # 即使没有关联剧集，也要删除episode表中c19字段匹配的记录
                        cursor.execute("DELETE FROM episode WHERE c19 = ?", (selected_id_path,))
                        episode_deleted += cursor.rowcount
                
                    # 删除path表中的记录
                    cursor.execute("DELETE FROM path WHERE idPath = ?", (selected_id_path,))
                    path_deleted += 1
        
            conn.commit()
        
            # 显示通知窗口而不是OK窗口
            message = f"已删除: 文件夹{path_deleted}个, 电影{movie_deleted}部, 剧集{tvshow_deleted}部, 单集{episode_deleted}集"
            xbmcgui.Dialog().notification("删除成功", message, xbmcgui.NOTIFICATION_INFO, 5000)
            check_and_update_library()
        
            conn.close()
            # 删除完成后继续显示当前选择窗口（重新进入循环）
            continue
    
        except Exception as e:
            xbmc.log(f"删除已刮削文件夹时出错: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", f"操作失败: {str(e)}")
            return

def delete_movies_batch():
    """情况2：已刮削电影批量删除(可多选)"""
    db_path = find_latest_videodb()
    if not db_path:
        return

    while True:
        try:
            # 检查数据库是否存在
            if not xbmcvfs.exists(db_path):
                xbmcgui.Dialog().ok("错误", f"数据库文件不存在: {db_path}")
                return
        
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
        
            # 查询所有电影
            cursor.execute("SELECT idMovie, c00, c16 FROM movie")
            movies = cursor.fetchall()
        
            if not movies:
                xbmcgui.Dialog().ok("提示", "没有找到已刮削的电影")
                conn.close()
                return
        
            # 准备选项列表
            options = []
            for row in movies:
                id_movie, title, sort_title = row
                if title:
                    # 使用c16字段进行排序，如果没有则使用标题
                    sort_key = sort_title if sort_title else title
                    display_text = f"[电影]-{title}"
                    options.append((id_movie, sort_key, display_text))
        
            if not options:
                xbmcgui.Dialog().ok("提示", "没有找到有效的电影记录")
                conn.close()
                return
        
            # 按c16字段排序
            sorted_options = sorted(options, key=lambda x: x[1].lower())
            display_list = [item[2] for item in sorted_options]
        
            # 显示多选对话框
            dialog = xbmcgui.Dialog()
            selected_indices = dialog.multiselect("选择要删除的已刮削电影", display_list)
        
            if selected_indices is None or len(selected_indices) == 0:
                conn.close()
                return  # 返回到主选择窗口
        
            # 获取选中的电影ID
            selected_ids = [sorted_options[i][0] for i in selected_indices]
        
            # 确认删除
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除您选择的已刮削电影？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
        
            if not confirm:
                conn.close()
                continue  # 继续显示当前选择窗口（重新进入循环）
        
            # 执行删除
            success_count = 0
            for movie_id in selected_ids:
                result = execute_jsonrpc("VideoLibrary.RemoveMovie", {"movieid": movie_id})
                if "error" not in result:
                    success_count += 1
        
            # 显示通知窗口而不是OK窗口
            message = f"已删除刮削电影{success_count}部！"
            xbmcgui.Dialog().notification("删除成功", message, xbmcgui.NOTIFICATION_INFO, 5000)
            check_and_update_library()
        
            conn.close()
            # 删除完成后继续显示当前选择窗口（重新进入循环）
            continue
    
        except Exception as e:
            xbmc.log(f"批量删除电影时出错: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", f"操作失败: {str(e)}")
            return

def delete_tvshows_batch():
    """情况3：已刮削剧集批量删除(可多选)"""
    db_path = find_latest_videodb()
    if not db_path:
        return

    while True:
        try:
            # 检查数据库是否存在
            if not xbmcvfs.exists(db_path):
                xbmcgui.Dialog().ok("错误", f"数据库文件不存在: {db_path}")
                return
        
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
        
            # 查询所有剧集
            cursor.execute("SELECT idShow, c00, c15 FROM tvshow")
            tvshows = cursor.fetchall()
        
            if not tvshows:
                xbmcgui.Dialog().ok("提示", "没有找到已刮削的剧集")
                conn.close()
                return
        
            # 准备选项列表
            options = []
            for row in tvshows:
                id_show, title, sort_title = row
                if title:
                    # 使用c15字段进行排序，如果没有则使用标题
                    sort_key = sort_title if sort_title else title
                    display_text = f"[剧集]-{title}"
                    options.append((id_show, sort_key, display_text))
        
            if not options:
                xbmcgui.Dialog().ok("提示", "没有找到有效的剧集记录")
                conn.close()
                return
        
            # 按c15字段排序
            sorted_options = sorted(options, key=lambda x: x[1].lower())
            display_list = [item[2] for item in sorted_options]
        
            # 显示多选对话框
            dialog = xbmcgui.Dialog()
            selected_indices = dialog.multiselect("选择要删除的已刮削剧集", display_list)
        
            if selected_indices is None or len(selected_indices) == 0:
                conn.close()
                return  # 返回到主选择窗口
        
            # 获取选中的剧集ID
            selected_ids = [sorted_options[i][0] for i in selected_indices]
        
            # 确认删除
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除您选择的已刮削剧集？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
        
            if not confirm:
                conn.close()
                continue  # 继续显示当前选择窗口（重新进入循环）
        
            # 记录要删除的剧集ID
            if selected_ids:
                placeholders = ','.join(['?' for _ in selected_ids])
            
                # 获取相关的单集数量
                cursor.execute(f"SELECT COUNT(*) FROM episode WHERE idShow IN ({placeholders})", selected_ids)
                episode_count = cursor.fetchone()[0]
            
                # 删除单集
                cursor.execute(f"DELETE FROM episode WHERE idShow IN ({placeholders})", selected_ids)
                episodes_deleted = cursor.rowcount
            
                # 删除季信息
                cursor.execute(f"DELETE FROM seasons WHERE idShow IN ({placeholders})", selected_ids)
            
                # 删除剧集
                cursor.execute(f"DELETE FROM tvshow WHERE idShow IN ({placeholders})", selected_ids)
                tvshows_deleted = cursor.rowcount
            
                conn.commit()
                
                # 执行JSON RPC删除命令
                success_count = 0
                for show_id in selected_ids:
                    result = execute_jsonrpc("VideoLibrary.RemoveTVShow", {"tvshowid": show_id})
                    if "error" not in result:
                        success_count += 1
        
            # 显示通知窗口而不是OK窗口
            message = f"已删除刮削剧集{success_count}部！包含单集{episodes_deleted}集"
            xbmcgui.Dialog().notification("删除成功", message, xbmcgui.NOTIFICATION_INFO, 5000)
            check_and_update_library()
        
            conn.close()
            # 删除完成后继续显示当前选择窗口（重新进入循环）
            continue
    
        except Exception as e:
            xbmc.log(f"批量删除剧集时出错: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", f"操作失败: {str(e)}")
            return

def backup_restore_library():
    """执行备份/恢复媒体库文件"""
    try:
        xbmc.executebuiltin('RunScript(special://skin/scripts/backuplib.py)')
    except Exception as e:
        xbmc.log(f"执行备份脚本时出错: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"执行备份脚本失败: {str(e)}")

def handle_single_item():
    """处理单一项目删除"""
    db_path = find_latest_videodb()
    if not db_path:
        return

    try:
        # 获取ListItem.DBType和ListItem.DBID
        db_type = xbmc.getInfoLabel('ListItem.DBType')
        db_id = xbmc.getInfoLabel('ListItem.DBID')
        
        if not db_type or not db_id:
            xbmcgui.Dialog().ok("错误", "无法获取项目信息")
            return

        # 转换DBID为整数
        try:
            db_id = int(db_id)
        except ValueError:
            xbmcgui.Dialog().ok("错误", "无效的项目ID")
            return

        if db_type == "movie":
            # 情况1：电影
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除已刮削数据？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
            if not confirm:
                return
            
            result = execute_jsonrpc("VideoLibrary.RemoveMovie", {"movieid": db_id})
            if "error" not in result:
                # 显示通知窗口而不是OK窗口
                xbmcgui.Dialog().notification("删除成功", "已删除所选文件刮削记录！", xbmcgui.NOTIFICATION_INFO, 5000)
                check_and_update_library()
            else:
                xbmcgui.Dialog().ok("错误", f"删除失败: {result['error']['message']}")
                
        elif db_type == "episode":
            # 情况2：单集
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除已刮削数据？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
            if not confirm:
                return
            
            result = execute_jsonrpc("VideoLibrary.RemoveEpisode", {"episodeid": db_id})
            if "error" not in result:
                # 显示通知窗口而不是OK窗口
                xbmcgui.Dialog().notification("删除成功", "已删除所选文件刮削记录！", xbmcgui.NOTIFICATION_INFO, 5000)
                check_and_update_library()
            else:
                xbmcgui.Dialog().ok("错误", f"删除失败: {result['error']['message']}")
                
        elif db_type == "tvshow":
            # 情况3：剧集
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除已刮削数据？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
            if not confirm:
                return
            
            result = execute_jsonrpc("VideoLibrary.RemoveTVShow", {"tvshowid": db_id})
            if "error" not in result:
                # 显示通知窗口而不是OK窗口
                xbmcgui.Dialog().notification("删除成功", "已删除所选文件刮削记录！", xbmcgui.NOTIFICATION_INFO, 5000)
                check_and_update_library()
            else:
                xbmcgui.Dialog().ok("错误", f"删除失败: {result['error']['message']}")
                
        elif db_type == "set":
            # 情况4：电影合集
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除已刮削数据？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
            if not confirm:
                return
            
            # 连接数据库获取相关电影ID
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 获取合集中的电影ID
            cursor.execute("SELECT idMovie FROM movie WHERE idSet = ?", (db_id,))
            movie_ids = [row[0] for row in cursor.fetchall()]
            
            # 删除相关电影
            success_count = 0
            for movie_id in movie_ids:
                result = execute_jsonrpc("VideoLibrary.RemoveMovie", {"movieid": movie_id})
                if "error" not in result:
                    success_count += 1
            
            # 删除合集本身
            cursor.execute("DELETE FROM sets WHERE idSet = ?", (db_id,))
            conn.commit()
            conn.close()
            
            # 显示通知窗口而不是OK窗口
            xbmcgui.Dialog().notification("删除成功", "已删除电影合集及其包含电影的刮削记录！", xbmcgui.NOTIFICATION_INFO, 5000)
            check_and_update_library()
            
        elif db_type == "season":
            # 情况5：季
            confirm = xbmcgui.Dialog().yesno("确认删除", "是否确认删除已刮削数据？\n\n选择\"是\"确认删除，选择\"否\"取消操作。")
            if not confirm:
                return
            
            # 连接数据库获取相关单集ID
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 获取季中的单集ID
            cursor.execute("SELECT idEpisode FROM episode WHERE idSeason = ?", (db_id,))
            episode_ids = [row[0] for row in cursor.fetchall()]
            
            # 删除相关单集
            success_count = 0
            for episode_id in episode_ids:
                result = execute_jsonrpc("VideoLibrary.RemoveEpisode", {"episodeid": episode_id})
                if "error" not in result:
                    success_count += 1
            
            # 删除季信息
            cursor.execute("DELETE FROM seasons WHERE idSeason = ?", (db_id,))
            conn.commit()
            conn.close()
            
            # 显示通知窗口而不是OK窗口
            xbmcgui.Dialog().notification("删除成功", "已删除季及其包含单集的刮削记录！", xbmcgui.NOTIFICATION_INFO, 5000)
            check_and_update_library()
            
        else:
            xbmcgui.Dialog().ok("错误", f"不支持的项目类型: {db_type}")
    
    except Exception as e:
        xbmc.log(f"处理单个项目时出错: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"操作失败: {str(e)}")

def main():
    """主函数"""
    try:
        # 检查是否有file参数
        if len(sys.argv) > 1 and sys.argv[1] == "file":
            handle_single_item()
            return

        # 显示备份确认对话框
        confirm_msg = "[COLOR red]强烈建议您在删除海报之前备份媒体库，否则有可能造成海报丢失！是否现在开始备份媒体库？[/COLOR]\n\n选择\"是\"开始备份媒体库，选择\"否\"则开始海报本地化流程。"
        confirm_backup = xbmcgui.Dialog().yesno("备份媒体库", confirm_msg)
        
        if confirm_backup:
            # 执行备份脚本
            xbmc.executebuiltin('RunScript(special://skin/scripts/backuplib.py)')
        else:
            # 显示操作选择菜单
            options = [
                "删除已刮削文件夹(可多选)",
                "已刮削电影批量删除(可多选)",
                "已刮削剧集批量删除(可多选)",
                "备份/恢复媒体库文件"
            ]
            
            while True:
                dialog = xbmcgui.Dialog()
                selected_option = dialog.select("选择操作", options)
                
                if selected_option == -1:  # 用户取消
                    break
                
                if selected_option == 0:
                    delete_scraper_folders()
                elif selected_option == 1:
                    delete_movies_batch()
                elif selected_option == 2:
                    delete_tvshows_batch()
                elif selected_option == 3:
                    backup_restore_library()
                    break  # 备份脚本执行后退出
    
    except Exception as e:
        xbmc.log(f"脚本运行时出错: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"脚本运行失败: {str(e)}")

# 添加sys模块导入
import sys

if __name__ == "__main__":
    main()