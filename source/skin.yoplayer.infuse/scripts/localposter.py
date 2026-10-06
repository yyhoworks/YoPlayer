import xbmc
import xbmcvfs
import xbmcgui
import sqlite3
import os
import sys
import time
from urllib.parse import unquote
import threading
import json

def log(msg):
    xbmc.log(f"[LocalPoster] {msg}", level=xbmc.LOGINFO)

def is_remote_protocol(url):
    """检查URL是否包含远程协议"""
    protocols = ['cloudnas', 'clouddrive', 'smb', 'webdav', 'nfs']
    url_lower = url.lower()
    for protocol in protocols:
        if protocol in url_lower:
            return True
    return False

def is_local_file_path(url):
    """检查URL是否为本地文件路径"""
    # 检查是否以file://开头
    if url.startswith('file://'):
        return True
    # 检查是否为绝对路径
    if url.startswith('/') or (len(url) > 1 and url[1:3] == ':\\'):
        return True
    # 检查是否为Windows盘符路径
    if len(url) > 2 and url[1:2] == ':' and url[2:3] in ['/', '\\']:
        return True
    return False

def is_special_protocol(url):
    """检查URL是否为special://协议"""
    return url.startswith('special://')

def is_image_protocol(url):
    """检查URL是否为image://协议"""
    return url.startswith('image://')

def is_http_protocol(url):
    """检查URL是否为http://或https://协议"""
    url_lower = url.lower()
    return url_lower.startswith('http://') or url_lower.startswith('https://')

def get_failure_log_path():
    """获取失败记录文件路径"""
    return 'special://userdata/addon_data/script.local.poster/failure_log.json'

def load_failed_urls():
    """加载失败的URL列表"""
    failure_log_path = get_failure_log_path()
    
    # 确保目录存在
    addon_data_dir = 'special://userdata/addon_data/script.local.poster/'
    if not xbmcvfs.exists(addon_data_dir):
        try:
            xbmcvfs.mkdirs(addon_data_dir)
        except Exception as e:
            log(f"Failed to create addon data directory: {str(e)}")
            return set()
    
    if not xbmcvfs.exists(failure_log_path):
        return set()
    
    try:
        # 使用xbmcvfs读取文件
        file_handle = xbmcvfs.File(failure_log_path, 'r')
        content = file_handle.read()
        file_handle.close()
        
        if content:
            content_str = content.decode('utf-8') if isinstance(content, bytes) else content
            failure_log = json.loads(content_str)
            return set(failure_log.get('failed_urls', []))
        else:
            return set()
    except Exception as e:
        log(f"Failed to load failure log: {str(e)}")
        return set()

def save_failed_url(url):
    """保存失败的URL到记录文件"""
    failure_log_path = get_failure_log_path()
    current_failed_urls = load_failed_urls()
    current_failed_urls.add(url)
    
    failure_log = {
        'failed_urls': list(current_failed_urls),
        'timestamp': time.time()
    }
    
    try:
        # 使用xbmcvfs写入文件
        file_handle = xbmcvfs.File(failure_log_path, 'w')
        json_str = json.dumps(failure_log, ensure_ascii=False)
        file_handle.write(json_str.encode('utf-8'))
        file_handle.close()
    except Exception as e:
        log(f"Failed to save failure log: {str(e)}")

def clear_failure_log():
    """清空失败记录"""
    failure_log_path = get_failure_log_path()
    if xbmcvfs.exists(failure_log_path):
        try:
            xbmcvfs.delete(failure_log_path)
            log("Cleared failure log")
        except Exception as e:
            log(f"Failed to clear failure log: {str(e)}")

def run_local_poster_script():
    if len(sys.argv) > 1:
        param = sys.argv[1].lower()
        if param == "local":
            process_local_posters()
            xbmc.executebuiltin('ReloadSkin()')
        elif param == "delete":
            delete_local_posters()
            xbmc.executebuiltin('ReloadSkin()')
        elif param == "select":
            show_selection_menu()
        elif param == "check":
            check_for_remote_posters()
        elif param == "clearfailures":
            clear_failure_log()
            xbmc.executebuiltin('Notification(LocalPoster, 已清除失败记录, 3000)')
        else:
            log(f"Unknown parameter: {param}")
    else:
        log("No parameter provided")

def check_for_remote_posters():
    """检查是否存在远程海报，如有则询问用户是否本地化"""
    # Database path - using xbmcvfs to handle special:// paths
    db_path = 'special://userdata/Database/MyVideos131.db'
    log(f"Checking database path: {db_path}")
    
    # Check if database exists
    if not xbmcvfs.exists(db_path):
        log("Database not found during check")
        return
    
    # Load previously failed URLs
    failed_urls = load_failed_urls()
    log(f"Loaded {len(failed_urls)} previously failed URLs")
    
    # Connect to database
    try:
        # Translate the special:// path to actual filesystem path
        actual_db_path = xbmcvfs.translatePath(db_path) if hasattr(xbmcvfs, 'translatePath') else xbmc.translatePath(db_path)
        conn = sqlite3.connect(actual_db_path)
        cursor = conn.cursor()
    except Exception as e:
        log(f"Failed to connect to database during check: {str(e)}")
        return
    
    # Find ALL URLs in the art table
    query = "SELECT url FROM art"
    
    try:
        cursor.execute(query)
        all_results = cursor.fetchall()
    except Exception as e:
        log(f"Failed to execute query during check: {str(e)}")
        conn.close()
        return
    
    # Filter results based on criteria - skip image://, special:// and http(s):// protocol URLs
    filtered_results = []
    skipped_count = 0
    for row in all_results:
        url = row[0]
        
        # 跳过以image://开头的URL
        if is_image_protocol(url):
            continue
        # 跳过以special://开头的URL（这些已经是本地化的）
        if is_special_protocol(url):
            continue
        # 跳过以http://或https://开头的URL
        if is_http_protocol(url):
            continue
        # 跳过之前失败的URL - 这里是关键修复点
        if url in failed_urls:
            skipped_count += 1
            continue
        # 仅包括本地文件路径或远程协议的URL
        if is_local_file_path(url) or is_remote_protocol(url):
            filtered_results.append(url)
    
    conn.close()
    
    # 如果没有找到符合条件的URL，静默退出
    if len(filtered_results) == 0:
        log("No remote or local poster URLs found, exiting silently")
        # 如果有跳过的失败URL，也静默处理，不显示通知
        if skipped_count > 0:
            log(f"Skipped {skipped_count} previously failed URLs")
        return
    
    # 如果找到了符合条件的URL，弹出确认对话框
    log(f"Found {len(filtered_results)} remote or local poster URLs, showing confirmation dialog")
    log(f"Also skipped {skipped_count} previously failed URLs")
    
    confirm = xbmcgui.Dialog().yesno(
        "海报本地化建议",
        f"检测到您的海报中包含远程图片，这将导致浏览海报卡顿，是否将其本地化？\n\n"
        f"待处理: {len(filtered_results)} 个\n"
        f"已跳过: {skipped_count} 个失败项"
    )
    
    if confirm:
        # 用户选择"是"，执行本地化操作
        log("User confirmed, running local poster script")
        xbmc.executebuiltin('RunScript(special://skin/scripts/localposter.py,local)')
    else:
        # 用户选择"否"，关闭脚本
        log("User declined, exiting script")

class CopyThread(threading.Thread):
    def __init__(self, source, destination):
        super().__init__()
        self.source = source
        self.destination = destination
        self.result = None
        self.exception = None
        
    def run(self):
        try:
            self.result = xbmcvfs.copy(self.source, self.destination)
        except Exception as e:
            self.exception = e

def copy_with_timeout(source, destination, timeout=15):
    """带超时控制的文件复制函数"""
    thread = CopyThread(source, destination)
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        # 线程仍在运行，表示超时
        log(f"Copy operation timed out for {source}")
        return False
    elif thread.exception:
        # 发生异常
        log(f"Copy operation failed with exception for {source}: {thread.exception}")
        return False
    else:
        # 正常完成
        return thread.result

def process_local_posters():
    # Database path - using xbmcvfs to handle special:// paths
    db_path = 'special://userdata/Database/MyVideos131.db'
    log(f"Database path: {db_path}")
    
    # Check if database exists
    if not xbmcvfs.exists(db_path):
        xbmc.executebuiltin('Notification(LocalPoster, 数据库未找到, 3000)')
        return
    
    # Connect to database
    try:
        # Translate the special:// path to actual filesystem path
        actual_db_path = xbmcvfs.translatePath(db_path) if hasattr(xbmcvfs, 'translatePath') else xbmc.translatePath(db_path)
        conn = sqlite3.connect(actual_db_path)
        cursor = conn.cursor()
    except Exception as e:
        log(f"Failed to connect to database: {str(e)}")
        xbmc.executebuiltin('Notification(LocalPoster, 数据库连接失败, 3000)')
        return
    
    # Load previously failed URLs to exclude them from processing
    failed_urls = load_failed_urls()
    log(f"Loaded {len(failed_urls)} previously failed URLs to skip")
    
    # Find URLs that are local paths or contain specified protocols
    query = "SELECT url FROM art"
    
    try:
        cursor.execute(query)
        all_results = cursor.fetchall()
    except Exception as e:
        log(f"Failed to execute query: {str(e)}")
        conn.close()
        return
    
    # Filter results based on criteria - skip image://, special:// and http(s):// protocol URLs
    filtered_results = []
    skipped_count = 0
    for row in all_results:
        url = row[0]
        # 跳过以image://开头的URL
        if is_image_protocol(url):
            log(f"Skipping image:// protocol URL: {url}")
            continue
        # 跳过以special://开头的URL（这些已经是本地化的）
        if is_special_protocol(url):
            log(f"Skipping special:// protocol URL: {url}")
            continue
        # 跳过以http://或https://开头的URL
        if is_http_protocol(url):
            log(f"Skipping http(s):// protocol URL: {url}")
            continue
        # 跳过之前失败的URL
        if url in failed_urls:
            log(f"Skipping previously failed URL: {url}")
            skipped_count += 1
            continue
        # 仅处理本地文件路径或远程协议的URL
        if is_local_file_path(url) or is_remote_protocol(url):
            filtered_results.append(url)
    
    total_items = len(filtered_results)
    if total_items == 0:
        message = "未找到匹配的海报"
        if skipped_count > 0:
            message += f" (已跳过{skipped_count}个失败项)"
        xbmc.executebuiltin(f'Notification(LocalPoster, {message}, 3000)')
        conn.close()
        return
    
    log(f"Found {total_items} matching poster entries, skipped {skipped_count} failed entries")

    # Clear failure log before starting new process
    if total_items > 0:
        clear_failure_log()
    
    # Create thumbnails local directory if it doesn't exist
    local_thumb_dir = 'special://userdata/Thumbnails/local/'
    if not xbmcvfs.exists(local_thumb_dir):
        try:
            xbmcvfs.mkdirs(local_thumb_dir)
            log(f"Created local thumbnail directory: {local_thumb_dir}")
        except Exception as e:
            log(f"Failed to create local thumbnail directory: {str(e)}")
            conn.close()
            return
    
    # Progress dialog with cancel button
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create("本地海报备份", "正在初始化...")
    
    processed_count = 0
    success_count = 0
    failure_count = 0
    
    for url in filtered_results:
        # Check if user cancelled the operation
        if progress_dialog.iscanceled():
            break
        
        # Update progress
        processed_count += 1
        progress_percent = int((processed_count / total_items) * 100)
        
        # Update progress dialog - only two parameters for DialogProgress
        message = f"正在处理海报 {processed_count}/{total_items}\n当前: {url}"
        progress_dialog.update(progress_percent, message)
        
        try:
            # Extract folder name from URL
            # Decode URL if needed
            decoded_url = unquote(url)
            
            # Handle special:// paths by translating them
            if decoded_url.startswith('special://'):
                actual_source_path = xbmcvfs.translatePath(decoded_url) if hasattr(xbmcvfs, 'translatePath') else xbmc.translatePath(decoded_url)
            else:
                actual_source_path = decoded_url
            
            # Get the parent directory name
            parent_folder = os.path.basename(os.path.dirname(actual_source_path))
            
            # Skip if parent folder is empty or invalid
            if not parent_folder or parent_folder in ['.', '..']:
                log(f"Skipping invalid parent folder for: {url}")
                failure_count += 1
                save_failed_url(url)  # 记录失败的URL
                continue
            
            # Create subdirectory under Thumbnails/local/
            target_subdir = f"special://userdata/Thumbnails/local/{parent_folder}/"
            if not xbmcvfs.exists(target_subdir):
                try:
                    xbmcvfs.mkdirs(target_subdir)
                    log(f"Created subdirectory: {target_subdir}")
                except Exception as e:
                    log(f"Failed to create subdirectory {target_subdir}: {str(e)}")
                    failure_count += 1
                    save_failed_url(url)  # 记录失败的URL
                    continue
            
            # Get the filename
            filename = os.path.basename(actual_source_path)
            target_path = f"special://userdata/Thumbnails/local/{parent_folder}/{filename}"
            
            # Copy file to local thumbnail directory with timeout
            if xbmcvfs.exists(decoded_url):
                copy_success = copy_with_timeout(decoded_url, target_path, timeout=15)
                if copy_success:
                    # Update the database entry
                    new_url = f"special://userdata/Thumbnails/local/{parent_folder}/{filename}"
                    update_query = "UPDATE art SET url = ? WHERE url = ?"
                    cursor.execute(update_query, (new_url, url))
                    
                    log(f"Copied {url} to {target_path}, updated DB to {new_url}")
                    success_count += 1
                else:
                    log(f"Failed to copy {url} to {target_path} (timeout or error)")
                    failure_count += 1
                    save_failed_url(url)  # 记录失败的URL
            else:
                log(f"Source file does not exist: {decoded_url}")
                failure_count += 1
                save_failed_url(url)  # 记录失败的URL
                
        except Exception as e:
            log(f"Error processing {url}: {str(e)}")
            failure_count += 1
            save_failed_url(url)  # 记录失败的URL
    
    # Close progress dialog
    progress_dialog.close()
    
    # Commit changes to database
    try:
        conn.commit()
        log("Database changes committed successfully")
    except Exception as e:
        log(f"Failed to commit database changes: {str(e)}")
    
    conn.close()
    
    # Calculate results
    actual_processed = success_count + failure_count
    
    # Show final result dialog
    result_text = f"处理完成！\n\n已处理: {actual_processed}\n成功: {success_count}\n失败: {failure_count}\n已跳过: {skipped_count} 个失败项"
    xbmcgui.Dialog().ok("本地海报备份结果", result_text)
    
    log(f"Local poster backup completed. Successful: {success_count}, Failed: {failure_count}")

def delete_local_posters():
    """删除本地海报文件夹"""
    # 弹出确认对话框
    confirm = xbmcgui.Dialog().yesno(
        "删除本地海报",
        "该操作将删除所有已经复制到本地的影片文件夹海报图片，是否继续？"
    )
    
    if not confirm:
        log("User cancelled deletion operation")
        return
    
    # 删除 special://userdata/Thumbnails/local 文件夹
    local_thumb_dir = 'special://userdata/Thumbnails/local/'
    
    try:
        if xbmcvfs.exists(local_thumb_dir):
            # 使用递归删除方法
            success = xbmcvfs.rmdir(local_thumb_dir)
            if success:
                xbmc.executebuiltin('Notification(LocalPoster, 本地海报文件夹已删除, 3000)')
                log("Local posters folder deleted successfully")
            else:
                xbmc.executebuiltin('Notification(LocalPoster, 删除本地海报文件夹失败, 3000)')
                log("Failed to delete local posters folder")
        else:
            xbmc.executebuiltin('Notification(LocalPoster, 本地海报文件夹不存在, 3000)')
            log("Local posters folder does not exist")
    except Exception as e:
        log(f"Error deleting local posters folder: {str(e)}")
        xbmc.executebuiltin('Notification(LocalPoster, 删除本地海报文件夹时发生错误, 3000)')

def show_selection_menu():
    """显示选择菜单"""
    # 创建选择对话框
    options = [
        "将影片文件夹内海报图片复制到系统本地",
        "[COLOR red]删除系统存储的影片文件夹内海报图片[/COLOR]",
        "清除失败记录",
        "显示失败记录"
    ]
    
    selected_option = xbmcgui.Dialog().select("海报管理选项", options)
    
    if selected_option == 0:
        # 选择第一个选项：复制海报
        log("Selected option: Copy posters to local")
        xbmc.executebuiltin('RunScript(special://skin/scripts/localposter.py,local)')
    elif selected_option == 1:
        # 选择第二个选项：删除海报
        log("Selected option: Delete local posters")
        xbmc.executebuiltin('RunScript(special://skin/scripts/localposter.py,delete)')
    elif selected_option == 2:
        # 选择第三个选项：清除失败记录
        log("Selected option: Clear failure records")
        xbmc.executebuiltin('RunScript(special://skin/scripts/localposter.py,clearfailures)')
    elif selected_option == 3:
        # 选择第四个选项：显示失败记录
        log("Selected option: Show failure records")
        show_failure_records()
    else:
        # 用户取消选择
        log("User cancelled selection")

def show_failure_records():
    """显示失败记录"""
    failed_urls = load_failed_urls()
    
    if not failed_urls:
        xbmc.executebuiltin('Notification(LocalPoster, 暂无失败记录, 3000)')
        return
    
    # 创建显示文本 - 限制显示数量以适应对话框
    header = f"失败记录 ({len(failed_urls)} 个):\n"
    header += "=" * 50 + "\n\n"
    
    # 将失败URL列表转换为字符串，每个URL占一行
    urls_list = list(failed_urls)
    
    # 如果URL太多，只显示前20个，并告知用户总数
    if len(urls_list) > 20:
        display_urls = urls_list[:20]
        remaining_count = len(urls_list) - 20
        content = header + "\n".join(display_urls) + f"\n\n... 还有 {remaining_count} 个失败记录未显示"
    else:
        content = header + "\n".join(urls_list)
    
    # 使用Dialog().textviewer显示文本内容
    xbmcgui.Dialog().textviewer("失败记录", content)

if __name__ == "__main__":
    run_local_poster_script()