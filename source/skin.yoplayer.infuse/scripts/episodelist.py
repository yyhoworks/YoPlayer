import xbmc
import xbmcgui
import xbmcaddon
import os
import time

def log_message(message, level=xbmc.LOGINFO):
    """记录日志消息"""
    xbmc.log(f"episodelist.py: {message}", level)

def get_info_label(label):
    """获取KODI信息标签的值"""
    value = xbmc.getInfoLabel(label)
    log_message(f"获取信息标签 {label} 的值: '{value}'")
    return value

def is_directory_path(path):
    """判断路径是否为目录路径"""
    log_message(f"检查路径是否为目录: '{path}'")
    
    # 检查路径是否以常见的视频文件扩展名结尾
    video_extensions = (
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', 
        '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', 
        '.rmvb', '.vob', '.iso', '.img'
    )
    
    # 如果路径以这些扩展名结尾，则认为是文件路径
    if path.lower().endswith(video_extensions):
        log_message(f"路径以视频扩展名结尾，判断为文件路径")
        return False
    else:
        # 如果路径不含文件扩展名，或者看起来像目录，则认为是目录路径
        filename = os.path.basename(path)
        if '.' in filename:
            # 有扩展名，是文件
            log_message(f"路径包含文件扩展名 '{filename}'，判断为文件路径")
            return False
        else:
            # 没有扩展名，可能是目录
            log_message(f"路径不包含文件扩展名，判断为目录路径")
            return True

def normalize_directory_path(path):
    """标准化目录路径，确保以适当的分隔符结尾"""
    log_message(f"标准化目录路径: '{path}'")
    
    # 检测路径使用的分隔符类型
    has_forward_slash = '/' in path
    has_backslash = '\\' in path
    
    if has_forward_slash and has_backslash:
        # 如果两种分隔符都存在，使用最后出现的那个
        last_slash_pos = path.rfind('/')
        last_backslash_pos = path.rfind('\\')
        if last_slash_pos > last_backslash_pos:
            separator = '/'
            log_message("检测到路径同时包含正斜杠和反斜杠，使用最后出现的正斜杠作为分隔符")
        else:
            separator = '\\'
            log_message("检测到路径同时包含正斜杠和反斜杠，使用最后出现的反斜杠作为分隔符")
    elif has_forward_slash:
        separator = '/'
        log_message("检测到路径使用正斜杠作为分隔符")
    elif has_backslash:
        separator = '\\'
        log_message("检测到路径使用反斜杠作为分隔符")
    else:
        # 默认使用系统分隔符
        separator = os.sep
        log_message(f"路径不包含标准分隔符，使用系统默认分隔符: '{separator}'")
    
    # 去除路径末尾的文件名，获取目录路径
    directory_path = os.path.dirname(path)
    log_message(f"提取目录路径: '{directory_path}'")
    
    # 确保目录路径以正确的分隔符结尾
    if not directory_path.endswith(separator):
        directory_path += separator
        log_message(f"添加分隔符到路径末尾: '{directory_path}'")
    else:
        log_message(f"路径已包含正确分隔符结尾")
    
    return directory_path

def run_script():
    log_message("开始执行 episodelist.py 脚本")
    
    # 获取ListItem.FolderPath的值
    folder_path = get_info_label('ListItem.FolderPath')
    
    # 如果ListItem.FolderPath为空，则获取ListItem.FileNameAndPath的值
    if not folder_path:
        log_message("ListItem.FolderPath 为空，获取 ListItem.FileNameAndPath 的值")
        file_path = get_info_label('ListItem.FileNameAndPath')
        path_to_use = file_path
        log_message(f"使用 ListItem.FileNameAndPath 的值: '{path_to_use}'")
    else:
        path_to_use = folder_path
        log_message(f"使用 ListItem.FolderPath 的值: '{path_to_use}'")
    
    # 如果获取不到任何路径，退出脚本
    if not path_to_use:
        log_message("无法获取路径信息，脚本退出", xbmc.LOGWARNING)
        return
    
    log_message(f"最终使用的路径: '{path_to_use}'")
    
    # 判断路径是否为文件夹目录路径
    is_dir = is_directory_path(path_to_use)
    
    if is_dir:
        log_message(f"路径 '{path_to_use}' 被识别为目录路径，执行 ActivateWindow")
        xbmc.executebuiltin(f'ActivateWindow(Videos,{path_to_use},return)')
        log_message("ActivateWindow 命令已发送")
    else:
        log_message(f"路径 '{path_to_use}' 被识别为文件路径，需要提取目录路径")
        
        # 如果不是目录路径而是文件路径，提取目录路径
        directory_path = normalize_directory_path(path_to_use)
        log_message(f"标准化后的目录路径: '{directory_path}'")
        
        # 设置皮肤字符串
        log_message(f"设置皮肤字符串 episodelist 为: '{directory_path}'")
        xbmc.executebuiltin(f'Skin.SetString(episodelist,{directory_path})')
        
        # 延时更长时间以确保皮肤字符串设置生效
        log_message("等待1秒以确保皮肤字符串设置生效...")
        
        # 直接使用目录路径激活窗口，而不是通过Skin.String
        log_message(f"直接使用目录路径激活窗口: '{directory_path}'")
        xbmc.executebuiltin(f'ActivateWindow(Videos,{directory_path},return)')
        log_message("ActivateWindow 命令已发送")
    
    log_message("脚本执行完成")
    # 关闭退出脚本
    return

if __name__ == '__main__':
    run_script()