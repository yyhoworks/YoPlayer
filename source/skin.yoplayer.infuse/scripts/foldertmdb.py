import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import os
import threading
import time

def get_special_path(path):
    """兼容新旧版本Kodi的路径转换"""
    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        return xbmc.translatePath(path)

def scan_video_files_async(folder_path, shared_data):
    """
    异步线程：扫描文件夹及子文件夹下的所有视频文件
    排除 STEAM 文件夹
    """
    video_extensions = {'.iso', '.mkv', '.mp4', '.wmv', '.ts', '.avi', '.mov'}
    excluded_folders = {'steam'}
    
    for root, dirs, files in os.walk(folder_path):
        # 原地修改 dirs 以排除特定文件夹
        dirs[:] = [d for d in dirs if d.lower() not in excluded_folders]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() in video_extensions:
                full_path = os.path.join(root, file)
                with shared_data['lock']:
                    shared_data['queue'].append(full_path)
                    shared_data['total_scanned'] += 1
                    
    # 扫描完成标记
    with shared_data['lock']:
        shared_data['scan_done'] = True

def main():
    # 1. 获取当前 ListItem 信息
    folder_path = xbmc.getInfoLabel('ListItem.FolderPath')
    current_filename = xbmc.getInfoLabel('ListItem.FileName')
    
    if not folder_path:
        xbmcgui.Dialog().ok("错误", "无法获取当前文件夹路径")
        return

    # 转换特殊路径为系统绝对路径
    system_folder_path = get_special_path(folder_path)
    db_path = get_special_path('special://userdata/Database/MyVideos131.db')
    
    if not xbmcvfs.exists(db_path):
        xbmcgui.Dialog().ok("错误", "未找到视频数据库文件 (MyVideos131.db)")
        return

    # 2. 初始化共享数据与异步扫描线程
    shared_data = {
        'queue': [],
        'total_scanned': 0,
        'scan_done': False,
        'lock': threading.Lock()
    }
    
    scan_thread = threading.Thread(target=scan_video_files_async, args=(system_folder_path, shared_data))
    scan_thread.start()

    # 3. 初始化进度条
    dialog = xbmcgui.DialogProgress()
    dialog.create("正在查找电影类型", f"{current_filename}\n[0/0]")
    
    # 连接数据库（保持连接以提高查询效率）
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    movie_count = 0
    episode_count = 0
    not_found_files = []
    processed_count = 0
    
    # 4. 并发处理：边扫描边查询
    while True:
        with shared_data['lock']:
            current_total = shared_data['total_scanned']
            is_scan_done = shared_data['scan_done']
            
            # 从队列中取出文件
            if shared_data['queue']:
                file_path = shared_data['queue'].pop(0)
            else:
                file_path = None

        # 如果队列为空且扫描已完成，则退出循环
        if file_path is None and is_scan_done:
            break
            
        # 如果队列为空但扫描未完成，等待一下
        if file_path is None:
            xbmc.sleep(50)
            continue

        # 处理当前文件
        processed_count += 1
        
        # 查询 movie 表 c22
        cursor.execute("SELECT idFile FROM movie WHERE c22 = ?", (file_path,))
        if cursor.fetchone():
            movie_count += 1
        else:
            # 查询 episode 表 c18
            cursor.execute("SELECT idFile FROM episode WHERE c18 = ?", (file_path,))
            if cursor.fetchone():
                episode_count += 1
            else:
                not_found_files.append(file_path)

        # 更新进度条
        if current_total > 0:
            # 确保进度不超过99%，直到扫描完全结束且处理完毕
            if is_scan_done and processed_count >= current_total:
                percent = 100
            else:
                percent = min(99, int((processed_count / current_total) * 100))
        else:
            percent = 0
            
        line1 = f"正在查找电影类型：{current_filename}"
        line2 = f"[{processed_count}/{current_total}]"
        
        dialog.update(percent, f"{line1}\n{line2}")
        
        if dialog.iscanceled():
            conn.close()
            dialog.close()
            return
            
        # 防止CPU占用过高
        xbmc.sleep(1)

    conn.close()
    dialog.close()
    
    # 5. 计算未入库数量
    total_count = processed_count
    not_found_count = total_count - movie_count - episode_count
    
    # 6. 弹出结果确认窗口
    msg = (
        f"该文件夹视频文件数量为[COLOR yellow]{total_count}[/COLOR]个，"
        f"已扫描生入库的电影数量为[COLOR green]{movie_count}[/COLOR]个，"
        f"单集数量为[COLOR green]{episode_count}[/COLOR]个。\n"
        f"未入库的文件数量为[COLOR red]{not_found_count}[/COLOR]个\n"
        f"点击\"是\"查看未生成海报的文件所在目录，点击\"否\"关闭该窗口。"
    )
    
    confirm = xbmcgui.Dialog().yesno("扫描结果", msg)
    
    if not confirm:
        # 用户选择“否”
        xbmc.executebuiltin('RunScript(special://skin/scripts/autotmdb.py,manage)')
        return
    else:
        # 用户选择“是”
        if not not_found_files:
            xbmcgui.Dialog().ok("提示", "所有文件均已入库")
            return
            
        # 弹出选择窗口，列出 FileNameAndPath (即完整路径)
        selected_idx = xbmcgui.Dialog().select("选择未入库文件", not_found_files)
        
        if selected_idx >= 0:
            selected_file_path = not_found_files[selected_idx]
            
            # 获取该文件的目录路径（去除文件本身，只保留目录）
            # 注：在 select 对话框中无法直接通过 getInfoLabel 获取选中项的 FolderPath，
            # 因此直接使用 os.path.dirname 解析完整路径，这完全符合“去除文件本身保留目录”的需求。
            dir_path = os.path.dirname(selected_file_path)
            
            # 执行 ActivateWindow 跳转到该目录
            xbmc.executebuiltin(f'ActivateWindow(Videos,{dir_path},return)')
            
        return

if __name__ == "__main__":
    main()