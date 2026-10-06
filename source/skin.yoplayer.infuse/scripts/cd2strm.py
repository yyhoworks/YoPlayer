import os
import sys
import xbmc
import xbmcgui
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
import urllib.parse
from urllib.parse import urlparse, unquote, quote
import datetime
import zipfile
import shutil
import time
from collections import defaultdict

# -------------------------- 配置参数 --------------------------
TARGET_DIR = "/storage/videos/strm/"
DEFAULT_SOURCE_PATH = "/storage/videos/CloudNAS/CloudDrive/"
SOURCE_RECORD_FILE = os.path.join(TARGET_DIR, "source_directories.xml")
MAX_FILENAME_LENGTH = 115
MAX_FOLDER_NAME_LENGTH = 90
SUPPORTED_NETWORK_PROTOCOLS = {"smb", "nfs", "webdav", "dav"}  # 添加 dav 协议支持
# 访问频率控制参数
ACCESS_INTERVAL = 0.25  # 250毫秒间隔
LAST_ACCESS_TIMES = defaultdict(float)  # 记录每个路径的最后访问时间
# -------------------------- 配置结束 --------------------------

# -------------------------- 工具函数 --------------------------
def is_valid_network_path(path):
    if not path:
        return False
    try:
        parsed = urlparse(path)
        scheme = parsed.scheme.lower()
        # 支持 dav 和 webdav 协议
        return scheme in SUPPORTED_NETWORK_PROTOCOLS and parsed.netloc
    except Exception:
        return False

def is_valid_local_path(path):
    if not path:
        return False
    return os.path.exists(path) and (os.path.isdir(path) or os.path.isfile(path))

def is_valid_path(path):
    if is_valid_local_path(path):
        return True
    if is_valid_network_path(path):
        return True
    return False

def is_directory_path(path):
    if is_valid_local_path(path):
        return os.path.isdir(path)
    if is_valid_network_path(path):
        path = path.rstrip("/")
        return "." not in os.path.basename(path)
    return False

def get_path_protocol(path):
    if is_valid_network_path(path):
        return urlparse(path).scheme.lower()
    return ""

def clean_network_path(path):
    if not is_valid_network_path(path):
        return path
    parsed = urlparse(path)
    netloc = unquote(parsed.netloc)
    path_part = unquote(parsed.path)
    
    # 修复路径部分的多余斜杠，但保留协议部分的双斜杠
    # 首先将路径规范化，移除多余的斜杠，但保持第一个斜杠
    cleaned_path = path_part
    # 替换路径部分中连续的斜杠（但保留开头的斜杠）
    cleaned_path = re.sub(r'/+', '/', cleaned_path)
    
    # 重新构建URL，确保协议部分的格式正确
    result = f"{parsed.scheme}://{netloc}{cleaned_path}".rstrip("/")
    return result

def extract_path_without_protocol(path):
    if is_valid_network_path(path):
        parsed = urlparse(path)
        # 修复路径中的多余斜杠，但不影响协议部分
        path = parsed.path
        # 替换路径部分中连续的斜杠（但保留开头的斜杠）
        cleaned_path = re.sub(r'/+', '/', path).lstrip('/')
        return cleaned_path
    return path

def is_bdmv_related_directory(path):
    """判断路径是否为BDMV相关目录"""
    if not path:
        return False
    lower_path = path.lower()
    return "/bdmv/" in lower_path or "/bdmv\\" in lower_path

def remove_auth_from_dav_path(path):
    """
    从DAV路径中移除认证信息
    例如：dav://user:pass@host/path -> dav://host/path
    """
    if not is_valid_network_path(path):
        return path
    
    parsed = urlparse(path)
    scheme = parsed.scheme.lower()
    
    if scheme in ['dav', 'webdav']:
        # 从netloc中移除认证部分
        netloc = parsed.netloc
        if '@' in netloc:
            # 提取主机部分，丢弃认证信息
            host_part = netloc.split('@')[-1]
            new_path = f"{parsed.scheme}://{host_part}{parsed.path}"
            if parsed.query:
                new_path += f"?{parsed.query}"
            if parsed.fragment:
                new_path += f"#{parsed.fragment}"
            return new_path
        else:
            # 如果没有认证信息，直接返回原路径
            return path
    else:
        # 非DAV协议路径直接返回
        return path

# 控制访问频率的函数
def rate_limit_access(path, force_delay=False):
    """限制对指定路径的访问频率，确保每250毫秒最多访问一次"""
    global LAST_ACCESS_TIMES
    current_time = time.time()
    last_access = LAST_ACCESS_TIMES[path]
    
    # 计算距离上次访问的时间间隔
    time_since_last = current_time - last_access
    
    # 如果间隔小于设定值，则等待剩余时间
    if time_since_last < ACCESS_INTERVAL or force_delay:
        sleep_time = ACCESS_INTERVAL - time_since_last if not force_delay else ACCESS_INTERVAL
        sleep_time = max(sleep_time, 0)  # 确保sleep_time不为负数
        xbmc.log(f"[STRM同步工具] 访问频率控制：等待 {sleep_time:.3f} 秒后访问 {path}", xbmc.LOGINFO)
        time.sleep(sleep_time)
    
    # 更新最后访问时间
    LAST_ACCESS_TIMES[path] = time.time()

# 【核心函数】统计指定目录的一级元素总数 - 文件夹/文件各算1个元素
def count_dir_first_level_elements(dir_path):
    total = 0
    if not is_valid_path(dir_path) or not is_directory_path(dir_path):
        return total

    # 应用访问频率控制
    rate_limit_access(dir_path)

    try:
        if is_valid_local_path(dir_path):
            items = os.listdir(dir_path)
            total = len(items)
        else:
            import xbmcvfs
            dirs, files = xbmcvfs.listdir(dir_path)
            total = len(dirs) + len(files)
    except Exception as e:
        xbmc.log(f"[STRM同步工具] 统计一级元素失败：{str(e)}", xbmc.LOGERROR)
    return total

# URL转义函数 - 不对dav协议进行转义，其他协议也不转义
def escape_url_path(url_path):
    """
    对URL路径进行转义，但不对dav协议进行转义，其他协议也不转义
    现在只返回原始路径，不做任何转义处理
    """
    if not is_valid_network_path(url_path):
        return url_path

    parsed = urlparse(url_path)
    scheme = parsed.scheme.lower()

    # 不对任何协议进行转义，直接返回原始路径
    return url_path

# -------------------------- 初始化 --------------------------
def initialize():
    if not os.path.exists(TARGET_DIR):
        try:
            os.makedirs(TARGET_DIR)
            xbmc.log(f"[STRM同步工具] 已创建STRM根目录：{TARGET_DIR}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[STRM同步工具] 创建STRM根目录失败：{str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("初始化失败", f"无法创建STRM目录：{str(e)}")
            sys.exit(1)
    
    if not os.path.exists(SOURCE_RECORD_FILE):
        try:
            root = ET.Element("source_directories")
            rough_string = ET.tostring(root, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ")
            
            with open(SOURCE_RECORD_FILE, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            xbmc.log(f"[STRM同步工具] 已创建源目录XML记录文件：{SOURCE_RECORD_FILE}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[STRM同步工具] 创建源目录XML记录文件失败：{str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("初始化失败", f"无法创建源目录记录文件：{str(e)}")
            sys.exit(1)

# -------------------------- 源目录管理 --------------------------
def load_source_directories():
    if not os.path.exists(SOURCE_RECORD_FILE):
        return []
    try:
        tree = ET.parse(SOURCE_RECORD_FILE)
        root = tree.getroot()
        
        sources = []
        for dir_elem in root.findall('directory'):
            path = dir_elem.text.strip() if dir_elem.text else ""
            if path and is_valid_path(path) and is_directory_path(path) and path not in sources:
                sources.append(path)
        return sources
    except Exception as e:
        xbmc.log(f"[STRM同步工具] 读取源目录XML记录失败：{str(e)}", xbmc.LOGERROR)
        return []

def save_source_directories(sources):
    """保存源目录列表到XML文件"""
    try:
        root = ET.Element("source_directories")
        for source in sources:
            dir_elem = ET.SubElement(root, "directory")
            dir_elem.text = clean_network_path(source)
            dir_elem.tail = "\n  "
        
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")
        lines = [line for line in pretty_xml.split('\n') if line.strip() != '']
        pretty_xml = '\n'.join(lines)
        
        with open(SOURCE_RECORD_FILE, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)
        
        xbmc.log(f"[STRM同步工具] 源目录列表已保存到：{SOURCE_RECORD_FILE}", xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log(f"[STRM同步工具] 保存源目录XML记录失败：{str(e)}", xbmc.LOGERROR)
        return False

def add_source_directory(new_dir):
    sources = load_source_directories()
    if new_dir in sources:
        return True, "目录已存在"
    
    if not is_valid_path(new_dir) or not is_directory_path(new_dir):
        return False, "目录不存在或不是有效目录"
    
    try:
        sources.append(new_dir)
        return save_source_directories(sources), "添加成功"
    except Exception as e:
        return False, f"添加失败：{str(e)}"

def remove_source_directory(target_dir):
    """从源目录列表中移除指定目录"""
    sources = load_source_directories()
    if target_dir in sources:
        sources.remove(target_dir)
        if save_source_directories(sources):
            xbmc.log(f"[STRM同步工具] 已从源目录列表中移除：{target_dir}", xbmc.LOGINFO)
            return True, "删除成功"
        else:
            return False, "保存失败"
    else:
        return False, "目录不在源列表中"

# -------------------------- 删除源目录功能 --------------------------
def get_strm_path_for_source(source_dir):
    """根据源目录路径生成对应的STRM目录路径"""
    target_parts = []
    if is_valid_network_path(source_dir):
        path_without_protocol = extract_path_without_protocol(source_dir)
        if path_without_protocol:
            for segment in path_without_protocol.split('/'):
                cleaned_segment = clean_folder_name(segment)
                if cleaned_segment:
                    target_parts.append(cleaned_segment)
    else:
        normalized_path = os.path.normpath(source_dir)
        path_parts = normalized_path.split(os.sep)
        priority_prefixes = ['clouddrive', 'cloudnas']
        found_truncate_point = False
        for part in path_parts:
            part_lower = part.lower()
            if not found_truncate_point and part_lower in priority_prefixes:
                found_truncate_point = True
                continue
            if found_truncate_point:
                cleaned_part = clean_folder_name(part)
                if cleaned_part:
                    target_parts.append(cleaned_part)
        if not found_truncate_point:
            cleaned_path_parts = [clean_path_segment(seg) for seg in path_parts if seg]
            target_parts = [clean_folder_name(part) for part in cleaned_path_parts if part]
    
    final_target_dir = TARGET_DIR
    if target_parts:
        target_subdir = os.path.join(*target_parts)
        final_target_dir = os.path.join(TARGET_DIR, target_subdir)
    
    return final_target_dir

def delete_corresponding_strm_directory(source_dir):
    """删除对应源目录的STRM目录及其中的文件"""
    strm_path = get_strm_path_for_source(source_dir)
    if os.path.exists(strm_path) and os.path.isdir(strm_path):
        try:
            # 递归删除目录及其内容
            shutil.rmtree(strm_path)
            xbmc.log(f"[STRM同步工具] 已删除对应的STRM目录：{strm_path}", xbmc.LOGINFO)
            return True, f"已删除STRM目录：{strm_path}"
        except Exception as e:
            xbmc.log(f"[STRM同步工具] 删除STRM目录失败：{strm_path} - {str(e)}", xbmc.LOGERROR)
            return False, f"删除STRM目录失败：{str(e)}"
    else:
        xbmc.log(f"[STRM同步工具] 对应的STRM目录不存在：{strm_path}", xbmc.LOGINFO)
        return True, f"STRM目录不存在，无需删除：{strm_path}"

def show_delete_source_menu():
    """显示删除源目录的选择菜单"""
    sources = load_source_directories()
    
    if not sources:
        xbmcgui.Dialog().ok("删除源目录", "没有可删除的源目录")
        return
    
    # 构建显示选项列表
    display_options = [get_display_name(source_dir) for source_dir in sources]
    display_options.append("取消")  # 添加取消选项
    
    selected = xbmcgui.Dialog().select("选择要删除的源目录", display_options)
    
    if selected == -1 or selected == len(sources):  # 用户取消或选择"取消"选项
        xbmc.log("[STRM同步工具] 用户取消删除源目录操作", xbmc.LOGINFO)
        return
    
    if 0 <= selected < len(sources):
        target_dir = sources[selected]
        display_name = get_display_name(target_dir)
        
        # 确认删除
        confirm = xbmcgui.Dialog().yesno(
            "确认删除",
            f"确定要从源目录列表中删除以下目录吗？\n\n{display_name}\n\n注意：这将从列表中移除该目录并删除STRM目录中对应的文件夹及内容！"
        )
        
        if confirm:
            # 先删除对应的STRM目录
            strm_success, strm_msg = delete_corresponding_strm_directory(target_dir)
            # 再从源目录列表中移除
            source_success, source_msg = remove_source_directory(target_dir)
            
            if source_success:
                result_msg = f"已从源目录列表中移除：{display_name}\n{strm_msg}"
                xbmcgui.Dialog().ok("删除成功", result_msg)
            else:
                xbmcgui.Dialog().ok("删除失败", f"从源目录列表删除失败：{source_msg}\n{strm_msg}")
        else:
            xbmc.log("[STRM同步工具] 用户取消删除操作", xbmc.LOGINFO)
    else:
        xbmc.log("[STRM同步工具] 无效的选择", xbmc.LOGERROR)

def delete_all_strm():
    """删除STRM目录下的所有内容"""
    if not os.path.exists(TARGET_DIR):
        xbmcgui.Dialog().ok("删除失败", "STRM目录不存在")
        return
    
    confirm = xbmcgui.Dialog().yesno(
        "危险操作警告",
        "此操作将删除所有STRM文件！\n\n确定要删除STRM目录下的所有内容吗？\n\nSTRM目录：" + TARGET_DIR
    )
    
    if not confirm:
        xbmc.log("[STRM同步工具] 用户取消删除所有STRM操作", xbmc.LOGINFO)
        return
    
    progress = xbmcgui.DialogProgress()
    progress.create("删除STRM文件", "正在删除所有STRM文件...")
    
    try:
        # 统计待删除文件数量
        total_files = 0
        for root, dirs, files in os.walk(TARGET_DIR):
            total_files += len([f for f in files if f.lower().endswith('.strm')])
        
        if total_files == 0:
            xbmcgui.Dialog().ok("删除完成", "STRM目录中没有STRM文件")
            progress.close()
            return
        
        deleted_count = 0
        for root, dirs, files in os.walk(TARGET_DIR, topdown=False):
            for file in files:
                if file.lower().endswith('.strm'):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        xbmc.log(f"[STRM同步工具] 已删除STRM文件：{file_path}", xbmc.LOGINFO)
                    except Exception as e:
                        xbmc.log(f"[STRM同步工具] 删除STRM文件失败：{file_path} - {str(e)}", xbmc.LOGERROR)
                
                # 更新进度
                progress_percent = int((deleted_count / total_files) * 100) if total_files > 0 else 0
                progress.update(progress_percent, f"已删除：{deleted_count}/{total_files} 个STRM文件")
                
                if progress.iscanceled():
                    xbmc.log("[STRM同步工具] 用户取消删除操作", xbmc.LOGINFO)
                    break
            
            if progress.iscanceled():
                break
        
        # 删除空目录
        delete_empty_dirs(TARGET_DIR)
        
        progress.close()
        xbmcgui.Dialog().ok("删除完成", f"已删除 {deleted_count} 个STRM文件")
        
    except Exception as e:
        progress.close()
        xbmc.log(f"[STRM同步工具] 删除STRM文件时发生错误：{str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("删除失败", f"删除过程中发生错误：{str(e)}")

# -------------------------- 文件名/目录名清理 --------------------------
def extract_without_brackets(filename):
    cleaned = re.sub(r'【|】|\[|\]', ' ', filename)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else "未命名文件"

def clean_folder_name(folder_name):
    # 首先解码可能存在的URL编码
    folder_name = unquote(folder_name)
    cleaned = extract_without_brackets(folder_name)
    cleaned = re.sub(r'[^\w\s\u4e00-\u9fa5\.\-_\(\)]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if not cleaned:
        cleaned = "未命名文件夹"
    
    if len(cleaned) > MAX_FOLDER_NAME_LENGTH:
        cleaned = cleaned[:MAX_FOLDER_NAME_LENGTH].strip()
        while cleaned.endswith('.'):
            cleaned = cleaned[:-1].strip()
        if not cleaned:
            cleaned = "未命名文件夹"
    
    return cleaned

def clean_path_segment(segment):
    # 首先解码可能存在的URL编码
    segment = unquote(segment)
    cleaned = re.sub(r'[^\w\s\-\.]', '', segment)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else "untitled_folder"

def clean_and_truncate(filename, max_length):
    # 首先解码可能存在的URL编码
    filename = unquote(filename)
    base_name = os.path.splitext(filename)[0]
    original_ext = os.path.splitext(filename)[1].lower()
    
    core_content = extract_without_brackets(base_name)
    safe_content = re.sub(r'[^\w\s\u4e00-\u9fa5\.\-_\(\)]', '', core_content)
    safe_content = re.sub(r'\s+', ' ', safe_content).strip()
    if not safe_content:
        safe_content = "未命名文件"
    
    valid_exts = {'.mkv', '.mp4', '.ts', '.m2ts', '.iso'}
    ext_part = original_ext if original_ext in valid_exts else ""
    
    strm_ext = ".strm"
    
    available_length = max_length - len(ext_part) - len(strm_ext)
    available_length = max(available_length, 1)
    
    truncated_body = safe_content[:available_length] if len(safe_content) > available_length else safe_content
    
    final_name = f"{truncated_body}{ext_part}{strm_ext}"
    
    if len(final_name) > max_length:
        final_name = final_name[:max_length - len(strm_ext)] + strm_ext
    if final_name.startswith('.'):
        final_name = f"视频{final_name}"
        if len(final_name) > max_length:
            final_name = final_name[:max_length - len(strm_ext)] + strm_ext
    
    return final_name

# -------------------------- STRM文件生成 --------------------------
def collect_existing_strm(include_mtime=False, source_dir_filter=None):
    existing_strm = {}
    if not os.path.exists(TARGET_DIR):
        return existing_strm
    
    for root, _, files in os.walk(TARGET_DIR):
        for file in files:
            if file.lower().endswith('.strm'):
                strm_path = os.path.join(root, file)
                try:
                    with open(strm_path, 'r', encoding='utf-8') as f:
                        source_path = f.readline().strip()
                    
                    if source_dir_filter and not source_path.startswith(source_dir_filter):
                        continue

                    base_source = source_dir_filter or None
                    if not base_source:
                        if is_valid_network_path(source_path):
                            parsed = urlparse(source_path)
                            share_dir = os.path.dirname(parsed.path).split('/')[1] if parsed.path else ''
                            base_source = f"{parsed.scheme}://{parsed.netloc}/{share_dir}"
                        else:
                            source_dirs = load_source_directories()
                            for src_dir in source_dirs:
                                if source_path.startswith(src_dir):
                                    base_source = src_dir
                                    break
                            if not base_source:
                                base_source = os.path.dirname(source_path) if os.path.isfile(source_path) else source_path
                    
                    if 'BDMV/index.bdmv' in source_path:
                        bdmv_folder = os.path.dirname(os.path.dirname(source_path))
                        rel_path = os.path.relpath(bdmv_folder, base_source) if base_source else bdmv_folder
                        item_key = f"bdmv_{rel_path}_{base_source}"
                    else:
                        rel_path = os.path.relpath(source_path, base_source) if base_source else source_path
                        item_key = f"video_{rel_path}_{base_source}"
                    
                    if include_mtime:
                        strm_mtime = os.path.getmtime(strm_path)
                        existing_strm[item_key] = (strm_path, strm_mtime)
                    else:
                        existing_strm[item_key] = strm_path
                
                except Exception as e:
                    xbmc.log(f"[STRM同步工具] 处理STRM文件失败：{str(e)}", xbmc.LOGERROR)
    
    return existing_strm

def create_strm_file(item_type, source_path, name, source_dir):
    try:
        if item_type == "bdmv":
            if is_valid_network_path(source_path):
                # 修复BDMV路径中的多余斜杠，同时保护协议部分
                bdmv_path = f"{source_path}/BDMV/index.bdmv"
                # 清理路径中的多余斜杠，但保护协议部分
                strm_content = clean_network_path(bdmv_path)
                # 不再对DAV协议路径进行转义
                strm_content = strm_content
            else:
                strm_content = os.path.join(source_path, "BDMV", "index.bdmv")
            original_filename = name
            full_source_dir = source_path
        else:
            # 修复普通视频路径中的多余斜杠，同时保护协议部分
            strm_content = clean_network_path(source_path)
            # 不再对DAV协议路径进行转义
            strm_content = strm_content
            original_filename = name
            full_source_dir = os.path.dirname(source_path) if is_valid_local_path(source_path) else os.path.dirname(source_path)
        
        strm_filename = clean_and_truncate(original_filename, MAX_FILENAME_LENGTH)
        xbmc.log(f"[STRM同步工具] 处理后STRM文件名：{strm_filename}（长度：{len(strm_filename)}）", xbmc.LOGINFO)
        xbmc.log(f"[STRM同步工具] 最终STRM内容：{strm_content}", xbmc.LOGINFO)
        
        target_parts = []
        if is_valid_network_path(full_source_dir):
            path_without_protocol = extract_path_without_protocol(full_source_dir)
            if path_without_protocol:
                for segment in path_without_protocol.split('/'):
                    cleaned_segment = clean_folder_name(segment)
                    if cleaned_segment:
                        target_parts.append(cleaned_segment)
        else:
            normalized_path = os.path.normpath(full_source_dir)
            path_parts = normalized_path.split(os.sep)
            priority_prefixes = ['clouddrive', 'cloudnas']
            found_truncate_point = False
            for part in path_parts:
                part_lower = part.lower()
                if not found_truncate_point and part_lower in priority_prefixes:
                    found_truncate_point = True
                    continue
                if found_truncate_point:
                    cleaned_part = clean_folder_name(part)
                    if cleaned_part:
                        target_parts.append(cleaned_part)
            if not found_truncate_point:
                cleaned_path_parts = [clean_path_segment(seg) for seg in path_parts if seg]
                target_parts = [clean_folder_name(part) for part in cleaned_path_parts if part]
        
        final_target_dir = TARGET_DIR
        if target_parts:
            target_subdir = os.path.join(*target_parts)
            final_target_dir = os.path.join(TARGET_DIR, target_subdir)
        
        if not os.path.exists(final_target_dir):
            os.makedirs(final_target_dir, exist_ok=True)
        
        strm_path = os.path.join(final_target_dir, strm_filename)
        
        path_length = len(strm_path)
        if path_length > 255:
            xbmc.log(f"[STRM同步工具] 路径较长（{path_length}字符）：{strm_path}", xbmc.LOGWARNING)
        
        with open(strm_path, 'w', encoding='utf-8') as f:
            # 再次清理写入的路径
            clean_content = clean_network_path(strm_content)
            # 不再对DAV协议路径进行转义
            final_content = clean_content
            f.write(final_content)
            xbmc.log(f"[STRM同步工具] 写入STRM文件内容：{final_content}", xbmc.LOGINFO)
        
        if os.path.getsize(strm_path) == 0:
            raise Exception("STRM文件为空")
        
        return True, strm_path
    except Exception as e:
        return False, f"{str(e)}"

# -------------------------- 目录处理 --------------------------
def delete_empty_dirs(root_dir):
    if not os.path.isdir(root_dir):
        return
    for dir_name in os.listdir(root_dir):
        dir_path = os.path.join(root_dir, dir_name)
        if os.path.isdir(dir_path):
            delete_empty_dirs(dir_path)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                    xbmc.log(f"[STRM同步工具] 删除空目录：{dir_path}", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[STRM同步工具] 删除空目录失败：{str(e)}", xbmc.LOGERROR)

def process_source_directory(source_dir, progress):
    xbmc.log(f"[STRM同步工具] 开始处理源目录：{source_dir}", xbmc.LOGINFO)
    if not is_valid_path(source_dir) or not is_directory_path(source_dir):
        xbmc.log(f"[STRM同步工具] 错误：源目录无效 -> {source_dir}", xbmc.LOGERROR)
        return (0, 0, [f"源目录无效：{source_dir}"], set())
    
    new_count = 0
    updated_count = 0
    error_list = []
    valid_source_keys = set()
    existing_strm = collect_existing_strm(include_mtime=True, source_dir_filter=source_dir)
    
    # ======== 核心进度计数 - 双计数分离 完全保留原逻辑 ========
    total_element_count = count_dir_first_level_elements(source_dir)  # 进度条总基数：一级元素总数
    processed_element_count = 0  # 已处理的一级元素数 → 用于计算百分比
    generated_strm_count = 0     # 真实生成的STRM文件数 → 用于文本显示的完成数
    # ==========================================================

    # -------------------------- 本地目录递归处理函数 --------------------------
    def _recurse_local_directory(current_dir):
        nonlocal new_count, updated_count, error_list, generated_strm_count
        
        if is_bdmv_related_directory(current_dir):
            return
            
        # 应用访问频率控制
        rate_limit_access(current_dir)
            
        try:
            # 处理当前目录下的BDMV文件夹
            dirs, files = next(os.walk(current_dir))[1], next(os.walk(current_dir))[2]
            bdmv_dir_found = any(dir_name.lower() == 'bdmv' for dir_name in dirs)
            if bdmv_dir_found:
                folder_name = os.path.basename(current_dir.rstrip(os.sep))
                rel_path = os.path.relpath(current_dir, source_dir) if source_dir != current_dir else ""
                item_key = f"bdmv_{rel_path}_{source_dir}"
                valid_source_keys.add(item_key)
                
                is_new = item_key not in existing_strm
                # 实时计算当前进度百分比
                current_percent = int((processed_element_count / total_element_count) * 100) if total_element_count > 0 else 0
                process_title = f"处理BDMV：{folder_name}（{current_dir}）"
                progress_msg = f"{process_title}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                progress.update(current_percent, progress_msg)
                
                success, result = create_strm_file("bdmv", current_dir, folder_name, source_dir)
                if success:
                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1
                    generated_strm_count += 1
                    xbmc.log(f"[STRM同步工具] BDMV STRM{'新增' if is_new else '更新'}成功：{result}", xbmc.LOGINFO)
                else:
                    error_list.append(f"BDMV {folder_name}：{result}")
                    xbmc.log(f"[STRM同步工具] BDMV STRM生成失败：{result}", xbmc.LOGERROR)
                    return
            
            # 处理当前目录下的视频文件
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in {'.mkv', '.mp4', '.ts', '.m2ts', '.iso'}:
                    file_path = os.path.join(current_dir, file)
                    rel_path = os.path.relpath(file_path, source_dir)
                    item_key = f"video_{rel_path}_{source_dir}"
                    valid_source_keys.add(item_key)
                    
                    is_new = item_key not in existing_strm
                    # 实时计算当前进度百分比
                    current_percent = int((processed_element_count / total_element_count) * 100) if total_element_count > 0 else 0
                    process_title = f"处理文件：{file}（{current_dir}）"
                    progress_msg = f"{process_title}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                    progress.update(current_percent, progress_msg)
                    
                    # 检查文件修改时间
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        if not is_new:
                            strm_path, strm_mtime = existing_strm[item_key]
                            if file_mtime <= strm_mtime:
                                xbmc.log(f"[STRM同步工具] 跳过：视频{file}未更新", xbmc.LOGINFO)
                                continue
                    except Exception as e:
                        error_list.append(f"获取{file}修改时间失败：{str(e)}")
                        continue
                    
                    success, result = create_strm_file("video", file_path, file, source_dir)
                    if success:
                        if is_new:
                            new_count += 1
                        else:
                            updated_count += 1
                        generated_strm_count += 1
                        xbmc.log(f"[STRM同步工具] 视频STRM{'新增' if is_new else '更新'}成功：{result}", xbmc.LOGINFO)
                    else:
                        error_list.append(f"视频 {file}：{result}")
                        xbmc.log(f"[STRM同步工具] 视频STRM生成失败：{result}", xbmc.LOGERROR)
                    
                    # 处理完每个文件后也要应用延迟
                    rate_limit_access(file_path, force_delay=True)
            
            # 递归处理当前目录下的子文件夹（排除BDMV）
            for dir_name in dirs:
                if dir_name.lower() == 'bdmv':
                    continue
                sub_dir = os.path.join(current_dir, dir_name)
                _recurse_local_directory(sub_dir)
                # 处理完每个子目录后也应用延迟
                rate_limit_access(sub_dir, force_delay=True)
                
        except Exception as e:
            error_msg = f"递归扫描本地目录 {current_dir} 出错：{str(e)}"
            error_list.append(error_msg)
            xbmc.log(f"[STRM同步工具] {error_msg}", xbmc.LOGERROR)

    # -------------------------- 网络目录递归处理函数 --------------------------
    def _recurse_network_directory(current_dir):
        nonlocal new_count, updated_count, error_list, generated_strm_count
        
        if is_bdmv_related_directory(current_dir):
            return

        # 应用访问频率控制
        rate_limit_access(current_dir)
            
        try:
            import xbmcvfs
            dirs, files = xbmcvfs.listdir(current_dir)
            if not dirs and not files:
                return
            
            bdmv_dir_found = 'bdmv' in [d.lower() for d in dirs]
            if bdmv_dir_found:
                folder_name = os.path.basename(current_dir.rstrip("/"))
                rel_path = os.path.relpath(current_dir, source_dir) if source_dir != current_dir else ""
                item_key = f"bdmv_{rel_path}_{source_dir}"
                valid_source_keys.add(item_key)
                
                is_new = item_key not in existing_strm
                current_percent = int((processed_element_count / total_element_count) * 100) if total_element_count > 0 else 0
                process_title = f"处理BDMV：{folder_name}（{current_dir}）"
                progress_msg = f"{process_title}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                progress.update(current_percent, progress_msg)
                
                success, result = create_strm_file("bdmv", current_dir, folder_name, source_dir)
                if success:
                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1
                    generated_strm_count += 1
                    xbmc.log(f"[STRM同步工具] BDMV STRM{'新增' if is_new else '更新'}成功：{result}", xbmc.LOGINFO)
                else:
                    error_list.append(f"BDMV {folder_name}：{result}")
                    xbmc.log(f"[STRM同步工具] BDMV STRM生成失败：{result}", xbmc.LOGERROR)
                    return
            
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in {'.mkv', '.mp4', '.ts', '.m2ts', '.iso'}:
                    file_path = f"{current_dir}/{file}"
                    rel_path = os.path.relpath(file_path, source_dir)
                    item_key = f"video_{rel_path}_{source_dir}"
                    valid_source_keys.add(item_key)
                    
                    is_new = item_key not in existing_strm
                    current_percent = int((processed_element_count / total_element_count) * 100) if total_element_count > 0 else 0
                    process_title = f"处理文件：{file}（{current_dir}）"
                    progress_msg = f"{process_title}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                    progress.update(current_percent, progress_msg)
                    
                    success, result = create_strm_file("video", file_path, file, source_dir)
                    if success:
                        if is_new:
                            new_count += 1
                        else:
                            updated_count += 1
                        generated_strm_count += 1
                        xbmc.log(f"[STRM同步工具] 视频STRM{'新增' if is_new else '更新'}成功：{result}", xbmc.LOGINFO)
                    else:
                        error_list.append(f"视频 {file}：{result}")
                        xbmc.log(f"[STRM同步工具] 视频STRM生成失败：{result}", xbmc.LOGERROR)
                    
                    # 处理完每个网络文件后也应用延迟
                    rate_limit_access(file_path, force_delay=True)
            
            for dir_name in dirs:
                if dir_name.lower() == 'bdmv':
                    continue
                sub_dir = f"{current_dir}/{dir_name}"
                _recurse_network_directory(sub_dir)
                # 处理完每个网络子目录后也应用延迟
                rate_limit_access(sub_dir, force_delay=True)
                
        except Exception as e:
            error_msg = f"递归扫描网络目录 {current_dir} 出错：{str(e)}"
            error_list.append(error_msg)
            xbmc.log(f"[STRM同步工具] {error_msg}", xbmc.LOGERROR)
    
    # -------------------------- 本地/网络路径处理逻辑 --------------------------
    try:
        if is_valid_local_path(source_dir):
            # 获取源目录一级子项列表（用于进度计数）
            first_level_items = os.listdir(source_dir)
            
            for item_name in first_level_items:
                if progress.iscanceled():
                    error_list.append("操作已取消")
                    return (new_count, updated_count, error_list, valid_source_keys)
                
                item_path = os.path.join(source_dir, item_name)
                # 处理一级文件夹：调用递归函数扫描所有子层级
                if os.path.isdir(item_path):
                    # 递归处理该文件夹的所有子目录
                    _recurse_local_directory(item_path)
                    
                    # 一级文件夹处理完成，进度+1（保留原进度逻辑）
                    processed_element_count += 1
                    if total_element_count > 0:
                        current_percent = int((processed_element_count / total_element_count) * 100)
                        progress_msg = f"处理完成：{item_name}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                        progress.update(current_percent, progress_msg)
                
                # 处理一级文件
                elif os.path.isfile(item_path):
                    file_ext = os.path.splitext(item_name)[1].lower()
                    if file_ext in {'.mkv', '.mp4', '.ts', '.m2ts', '.iso'}:
                        # 直接处理一级文件（无递归）
                        file_path = item_path
                        rel_path = os.path.relpath(file_path, source_dir)
                        item_key = f"video_{rel_path}_{source_dir}"
                        valid_source_keys.add(item_key)
                        
                        try:
                            file_mtime = os.path.getmtime(file_path)
                            is_new = item_key not in existing_strm
                            
                            if not is_new:
                                strm_path, strm_mtime = existing_strm[item_key]
                                if file_mtime <= strm_mtime:
                                    xbmc.log(f"[STRM同步工具] 跳过：视频{item_name}未更新", xbmc.LOGINFO)
                                    processed_element_count += 1
                                    continue
                            
                            current_percent = int((processed_element_count / total_element_count) * 100) if total_element_count > 0 else 0
                            process_title = f"处理文件：{item_name}"
                            progress_msg = f"{process_title}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                            progress.update(current_percent, progress_msg)
                            
                            success, result = create_strm_file("video", file_path, item_name, source_dir)
                            if success:
                                if is_new:
                                    new_count += 1
                                else:
                                    updated_count += 1
                                generated_strm_count += 1
                                xbmc.log(f"[STRM同步工具] 视频STRM{'新增' if is_new else '更新'}成功：{result}", xbmc.LOGINFO)
                            else:
                                error_list.append(f"视频 {item_name}：{result}")
                                xbmc.log(f"[STRM同步工具] 视频STRM生成失败：{result}", xbmc.LOGERROR)
                                
                            # 处理完一级文件后应用延迟
                            rate_limit_access(file_path, force_delay=True)
                        except Exception as e:
                            error_list.append(f"获取{item_name}修改时间失败：{str(e)}")
                    
                    # 一级文件处理完成，进度+1
                    processed_element_count += 1
                    if total_element_count > 0:
                        current_percent = int((processed_element_count / total_element_count) * 100)
                        progress_msg = f"处理完成：{item_name}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                        progress.update(current_percent, progress_msg)
                        
                    # 在处理完每个一级项目后也应用延迟
                    rate_limit_access(item_path, force_delay=True)
        else:
            # 网络路径处理 - 保留原有逻辑（已递归）
            total_element_count = count_dir_first_level_elements(source_dir)
            import xbmcvfs
            dirs, files = xbmcvfs.listdir(source_dir)
            all_items = dirs + files
            total_element_count = len(all_items)
            
            for idx, item_name in enumerate(all_items):
                if progress.iscanceled():
                    break

                item_path = f"{source_dir}/{item_name}"
                if item_name in dirs:
                    _recurse_network_directory(item_path)
                else:
                    file_ext = os.path.splitext(item_name)[1].lower()
                    if file_ext in {'.mkv', '.mp4', '.ts', '.m2ts', '.iso'}:
                        file_path = item_path
                        rel_path = os.path.relpath(file_path, source_dir)
                        item_key = f"video_{rel_path}_{source_dir}"
                        valid_source_keys.add(item_key)
                        
                        is_new = item_key not in existing_strm
                        current_percent = int((idx / total_element_count) * 100) if total_element_count > 0 else 0
                        process_title = f"处理文件：{item_name}（{source_dir}）"
                        progress_msg = f"{process_title}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                        progress.update(current_percent, progress_msg)
                        
                        success, result = create_strm_file("video", file_path, item_name, source_dir)
                        if success:
                            if is_new:
                                new_count += 1
                            else:
                                updated_count += 1
                            generated_strm_count += 1
                            xbmc.log(f"[STRM同步工具] 视频STRM{'新增' if is_new else '更新'}成功：{result}", xbmc.LOGINFO)
                        else:
                            error_list.append(f"视频 {item_name}：{result}")
                            xbmc.log(f"[STRM同步工具] 视频STRM生成失败：{result}", xbmc.LOGERROR)
                        
                        # 处理完每个网络文件后也应用延迟
                        rate_limit_access(file_path, force_delay=True)
                
                # 在处理完每个一级项目后应用延迟
                rate_limit_access(item_path, force_delay=True)
                
                # 网络路径进度更新
                processed_element_count += 1
                if total_element_count > 0:
                    current_percent = int((processed_element_count / total_element_count) * 100)
                    progress_msg = f"处理中：{item_name}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
                    progress.update(current_percent, progress_msg)
            
            if progress.iscanceled():
                error_list.append("操作已取消")
                return (new_count, updated_count, error_list, valid_source_keys)
        
        xbmc.log(f"[STRM同步工具] 源目录处理完成：{source_dir}，新增{new_count}个，更新{updated_count}个STRM", xbmc.LOGINFO)
        xbmc.log(f"[STRM同步工具] 本次同步有效的Item Keys: {valid_source_keys}", xbmc.LOGINFO)
    
    except Exception as e:
        error_msg = f"扫描目录出错：{str(e)}"
        error_list.append(error_msg)
        xbmc.log(f"[STRM同步工具] 扫描目录异常：{error_msg}", xbmc.LOGERROR)
    
    return (new_count, updated_count, error_list, valid_source_keys)

def process_single_file(file_path, progress):
    xbmc.log(f"[STRM同步工具] 开始处理单个文件：{file_path}", xbmc.LOGINFO)
    if not is_valid_path(file_path) or not os.path.isfile(file_path) and not is_valid_network_path(file_path):
        xbmc.log(f"[STRM同步工具] 错误：文件无效 -> {file_path}", xbmc.LOGERROR)
        return (0, 0, [f"文件无效：{file_path}"], set())
    
    if is_bdmv_related_directory(file_path):
        xbmc.log(f"[STRM同步工具] 跳过BDMV相关文件：{file_path}", xbmc.LOGINFO)
        return (0, 0, [], set())
    
    file_ext = os.path.splitext(file_path)[1].lower()
    valid_exts = {'.mkv', '.mp4', '.ts', '.m2ts', '.iso'}
    if file_ext not in valid_exts:
        error_msg = f"文件格式不支持：{os.path.basename(file_path)}（仅支持{', '.join(valid_exts)}）"
        xbmc.log(f"[STRM同步工具] 错误：{error_msg}", xbmc.LOGERROR)
        return (0, 0, [error_msg], set())
    
    new_count = 0
    updated_count = 0
    error_list = []
    source_keys = set()
    existing_strm = collect_existing_strm(include_mtime=True)
    generated_strm_count = 0  # 真实生成计数

    try:
        source_dir = os.path.dirname(file_path) if is_valid_local_path(file_path) else os.path.dirname(file_path)
        rel_path = os.path.relpath(file_path, source_dir) if is_valid_local_path(file_path) else os.path.basename(file_path)
        item_key = f"video_{rel_path}_{source_dir}"
        source_keys.add(item_key)
        
        file_name = os.path.basename(file_path)
        is_new = item_key not in existing_strm
        
        if not is_new:
            strm_path, strm_mtime = existing_strm[item_key]
            if is_valid_local_path(file_path):
                file_mtime = os.path.getmtime(file_path)
                if file_mtime <= strm_mtime:
                    xbmc.log(f"[STRM同步工具] 跳过：视频{file_name}未更新", xbmc.LOGINFO)
                    return (0, 0, [], source_keys)
        
        # 应用访问频率控制
        rate_limit_access(file_path)
        
        # ✅ 修改10：单文件进度文本格式 → 处理进度XX% - 已完成 [N]
        current_percent = 50
        process_title = f"处理文件：{file_name}"
        progress_msg = f"{process_title}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
        progress.update(current_percent, progress_msg)
        
        success, result = create_strm_file("video", file_path, file_name, source_dir)
        if success:
            if is_new:
                new_count += 1
            else:
                updated_count += 1
            generated_strm_count += 1
            current_percent = 100
            # ✅ 修改11：单文件完成后进度文本格式统一
            progress_msg = f"处理完成：{file_name}\n处理进度{current_percent}% - 已生成 [{generated_strm_count}] 个strm文件"
            progress.update(current_percent, progress_msg)
            xbmc.log(f"[STRM同步工具] 视频STRM{'新增' if is_new else '更新'}成功：{result}", xbmc.LOGINFO)
        else:
            error_list.append(f"视频 {file_name}：{result}")
            xbmc.log(f"[STRM同步工具] 视频STRM生成失败：{result}", xbmc.LOGERROR)
        
    except Exception as e:
        error_msg = f"处理文件出错：{str(e)}"
        error_list.append(error_msg)
        xbmc.log(f"[STRM同步工具] 处理文件异常：{error_msg}", xbmc.LOGERROR)
    
    return (new_count, updated_count, error_list, source_keys)

# -------------------------- STRM备份与恢复功能 --------------------------
def backup_strm():
    if not os.path.exists(TARGET_DIR) or not os.path.isdir(TARGET_DIR):
        xbmcgui.Dialog().ok("备份失败", "STRM目录不存在或不是有效目录")
        return
    
    backup_dir = "/storage/backup"
    if not os.path.exists(backup_dir):
        try:
            os.makedirs(backup_dir)
            xbmc.log(f"[STRM同步工具] 创建备份目录：{backup_dir}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[STRM同步工具] 创建备份目录失败：{str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("备份失败", f"无法创建备份目录：{str(e)}")
            return
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    zip_filename = f"strm_{timestamp}.zip"
    zip_path = os.path.join(backup_dir, zip_filename)
    
    progress = xbmcgui.DialogProgress()
    progress.create("备份STRM文件", f"正在创建压缩包：{zip_filename}")
    
    try:
        total_files = 0
        for root, _, files in os.walk(TARGET_DIR):
            total_files += len(files)
        
        if total_files == 0:
            progress.close()
            xbmcgui.Dialog().ok("备份提示", "STRM目录下没有文件可备份")
            return
        
        processed_files = 0
        zipf = zipfile.ZipFile(zip_path, 'w')
        
        for root, dirs, files in os.walk(TARGET_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, TARGET_DIR)
                zipf.write(file_path, arcname)
                
                processed_files += 1
                progress_percent = int((processed_files / total_files) * 100)
                progress_message = f"已处理：{processed_files}/{total_files} 文件 - 当前：{file}"
                progress.update(progress_percent, progress_message)
                
                if progress.iscanceled():
                    zipf.close()
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    progress.close()
                    xbmcgui.Dialog().ok("备份取消", "备份操作已终止，压缩包已删除")
                    return
        
        zipf.close()
        
        progress.close()
        file_size = os.path.getsize(zip_path) / (1024 * 1024)
        xbmc.log(f"[STRM同步工具] STRM备份成功：{zip_path}（大小：{file_size:.2f}MB）", xbmc.LOGINFO)
        xbmcgui.Dialog().ok("备份成功", 
                          f"STRM文件已成功备份！\n\n备份文件：{zip_filename}\n保存路径：{backup_dir}\n文件大小：{file_size:.2f} MB")

    except Exception as e:
        try:
            zipf.close()
        except:
            pass
        progress.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        xbmc.log(f"[STRM同步工具] STRM备份失败：{str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("备份失败", f"备份过程中出错：{str(e)}")

def restore_strm():
    backup_dir = "/storage/backup/"
    if not os.path.exists(backup_dir):
        xbmcgui.Dialog().ok("恢复失败", "备份目录不存在")
        return
    
    zip_path = xbmcgui.Dialog().browse(
        type=1,
        heading="选择STRM备份文件",
        shares="files",
        defaultt=backup_dir,
        useThumbs=False,
        treatAsFolder=False,
        mask=".zip"
    )
    
    if not zip_path or zip_path == backup_dir:
        xbmcgui.Dialog().ok("操作取消", "未选择备份文件")
        return
    
    if not zip_path.lower().endswith('.zip'):
        xbmcgui.Dialog().ok("恢复失败", "请选择有效的ZIP备份文件")
        return
    
    confirm = xbmcgui.Dialog().yesno(
        "警告",
        f"恢复操作将删除当前STRM目录下的所有文件和目录，然后从备份文件恢复。\n\n备份文件：{os.path.basename(zip_path)}\n\n确定继续？"
    )
    
    if not confirm:
        return
    
    progress = xbmcgui.DialogProgress()
    progress.create("恢复STRM文件", "正在删除现有文件...")
    
    try:
        progress.update(0, "正在删除现有STRM文件...")
        for root, dirs, files in os.walk(TARGET_DIR, topdown=False):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                except Exception as e:
                    xbmc.log(f"[STRM同步工具] 删除文件失败：{file_path} - {str(e)}", xbmc.LOGERROR)
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    os.rmdir(dir_path)
                except Exception as e:
                    xbmc.log(f"[STRM同步工具] 删除目录失败：{dir_path} - {str(e)}", xbmc.LOGERROR)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            total_files = len(zipf.namelist())
        
        if total_files == 0:
            progress.close()
            xbmcgui.Dialog().ok("恢复失败", "备份文件为空")
            return
        
        progress.update(0, "正在解压备份文件...")
        processed_files = 0
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            for file_info in zipf.infolist():
                zipf.extract(file_info, TARGET_DIR)
                
                processed_files += 1
                progress_percent = int((processed_files / total_files) * 100)
                progress_message = f"已解压：{processed_files}/{total_files} 文件 - {os.path.basename(file_info.filename)}"
                progress.update(progress_percent, progress_message)
                
                if progress.iscanceled():
                    progress.close()
                    xbmcgui.Dialog().ok("恢复取消", "恢复操作已终止")
                    return
        
        progress.close()
        xbmc.log(f"[STRM同步工具] STRM恢复成功：{zip_path}", xbmc.LOGINFO)
        xbmcgui.Dialog().ok("恢复成功", 
                          f"STRM文件已成功从备份恢复！\n\n备份文件：{os.path.basename(zip_path)}\n恢复文件数：{total_files} 个")

    except Exception as e:
        progress.close()
        xbmc.log(f"[STRM同步工具] STRM恢复失败：{str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("恢复失败", f"恢复过程中出错：{str(e)}")

def show_backup_restore_menu():
    options = [
        "备份/导出STRM文件",
        "恢复/导入STRM文件"
    ]
    return xbmcgui.Dialog().select("备份/恢复选项", options)

# -------------------------- 同步与交互 --------------------------
def sync_selected_source(selected_dirs, auto_shutdown=False):
    total_new = 0
    total_updated = 0
    total_deleted = 0
    total_errors = []
    
    for src_dir in selected_dirs:
        src_name = get_display_name(src_dir)
        progress = xbmcgui.DialogProgress()
        progress.create("同步目录", f"正在处理：{src_name}")
        
        try:
            new_count, updated_count, errors, valid_source_keys = process_source_directory(src_dir, progress)
            total_new += new_count
            total_updated += updated_count
            total_errors.extend(errors)
            
            if progress.iscanceled():
                progress.close()
                xbmcgui.Dialog().ok("同步取消", f"对 {src_name} 的同步已终止")
                if auto_shutdown:
                    xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,turnoff)')
                return
            
            progress.update(0, f"正在处理：{src_name} - 查找过时文件")
            existing_strm_for_src = collect_existing_strm(include_mtime=False, source_dir_filter=src_dir)
            
            obsolete_strm_paths = []
            for item_key, strm_path in existing_strm_for_src.items():
                if item_key not in valid_source_keys:
                    try:
                        with open(strm_path, 'r', encoding='utf-8') as f:
                            strm_content = f.readline().strip()
                        if is_bdmv_related_directory(strm_content):
                            obsolete_strm_paths.append(strm_path)
                            continue
                    except:
                        pass
                    obsolete_strm_paths.append(strm_path)
            
            if obsolete_strm_paths:
                if auto_shutdown:
                    confirm = True
                else:
                    progress.close()
                    confirm = xbmcgui.Dialog().yesno(
                        "发现过时文件",
                        f"在 '{src_name}' 中，有 {len(obsolete_strm_paths)} 个STRM文件对应的源文件已删除。\n是否删除这些过时的STRM文件？"
                    )
                
                if confirm:
                    if not auto_shutdown:
                        progress.close()
                        confirm = xbmcgui.Dialog().yesno(
                            "发现过时文件",
                            f"在 '{src_name}' 中，有 {len(obsolete_strm_paths)} 个STRM文件对应的源文件已删除。\n是否删除这些过时的STRM文件？"
                        )
                
                if confirm:
                    if not auto_shutdown:
                        progress.close()
                        progress.create("删除过时文件", f"正在删除 {src_name} 的过时文件")
                    for i, strm_path in enumerate(obsolete_strm_paths):
                        try:
                            if os.path.exists(strm_path):
                                os.remove(strm_path)
                                total_deleted += 1
                                xbmc.log(f"[STRM同步工具] 删除过时STRM：{strm_path}", xbmc.LOGINFO)
                        except Exception as e:
                            total_errors.append(f"删除{os.path.basename(strm_path)}失败：{str(e)}")
                            xbmc.log(f"[STRM同步工具] 删除过时STRM失败：{str(e)}", xbmc.LOGERROR)
                        
                        if not auto_shutdown:
                            progress_percent = int((i+1)/len(obsolete_strm_paths)*100)
                            progress.update(progress_percent, f"删除：{os.path.basename(strm_path)}")
                            if progress.iscanceled():
                                break
            
        finally:
            progress.close()

    delete_empty_dirs(TARGET_DIR)
    
    result_msg = [
        f"同步目录数量：{len(selected_dirs)}",
        f"新增STRM文件：{total_new} 个",
        f"更新STRM文件：{total_updated} 个",
        f"删除过时文件：{total_deleted} 个"
    ]
    
    if total_errors:
        result_msg.append(f"\n错误 ({len(total_errors)})：")
        for err in total_errors[:5]:
            result_msg.append(f"- {err}")
        if len(total_errors) > 5:
            result_msg.append(f"- 还有 {len(total_errors)-5} 个错误")
    
    if auto_shutdown:
        progress = xbmcgui.DialogProgress()
        progress.create("同步完成", "即将关机...")
        
        for i in range(7, 0, -1):
            progress.update(100 - (i * 100 // 7), f"同步完成！{i} 秒后将自动关机...")
            xbmc.sleep(1000)
            if progress.iscanceled():
                xbmc.log(f"[STRM同步工具] 用户取消了自动关机。", xbmc.LOGINFO)
                progress.close()
                return
        
        progress.close()
        xbmc.log(f"[STRM同步工具] 同步完成，执行自动关机。", xbmc.LOGINFO)
        xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,turnoff)')
    else:
        xbmcgui.Dialog().ok("同步完成", "\n".join(result_msg))

def get_display_name(source_dir):
    if is_valid_network_path(source_dir):
        parsed = urlparse(source_dir)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    else:
        path_parts = [part for part in source_dir.split(os.sep) if part]
        display_parts = []
        found_truncate_prefix = False
        priority_prefixes = ['clouddrive', 'cloudnas']
        
        for part in path_parts:
            part_lower = part.lower()
            if not found_truncate_prefix and part_lower in priority_prefixes:
                found_truncate_prefix = True
                display_parts.append(part)
                continue
            if found_truncate_prefix:
                display_parts.append(part)
        
        if not found_truncate_prefix:
            display_parts = path_parts[-2:] if len(path_parts) >= 2 else path_parts
        
        return os.sep.join(display_parts)

def open_strm_in_kodi():
    if os.path.exists(TARGET_DIR) and os.path.isdir(TARGET_DIR):
        xbmc.executebuiltin(f'ActivateWindow(Videos, "{TARGET_DIR}", return)')
    else:
        xbmcgui.Dialog().ok("打开失败", "STRM目录不存在")

def confirm_open_strm():
    if xbmcgui.Dialog().yesno("跳转确认", "是否跳转到STRM文件目录？"):
        open_strm_in_kodi()

def add_source_and_sync():
    default_path = DEFAULT_SOURCE_PATH
    if not is_valid_path(default_path) or not is_directory_path(default_path):
        default_path = "/storage"
        xbmc.log(f"[STRM同步工具] 默认源路径无效，使用 fallback：{default_path}", xbmc.LOGWARNING)
    
    new_source = select_directory("选择视频源目录（支持本地、smb://、nfs://、webdav://、dav://）", default_path)
    if not new_source:
        return
    
    # 特殊处理DAV协议路径
    if is_valid_network_path(new_source) and get_path_protocol(new_source) in ['dav', 'webdav']:
        # 从DAV路径中移除认证信息
        clean_path = remove_auth_from_dav_path(new_source)
        xbmc.log(f"[STRM同步工具] 检测到DAV协议路径，移除认证信息后: {clean_path}", xbmc.LOGINFO)
        xbmc.log(f"[STRM同步工具] 现在使用统一的处理流程", xbmc.LOGINFO)
        
        progress = xbmcgui.DialogProgress()
        progress.create("生成STRM文件", f"正在处理DAV路径：{os.path.basename(clean_path)}")
        
        try:
            new_count, updated_count, error_list, valid_source_keys = process_source_directory(clean_path, progress)
            target_type = "目录"
            
            sources = load_source_directories()
            if clean_path not in sources:
                xbmc.log(f"[STRM同步工具] 尝试将DAV源目录添加到记录: {clean_path}", xbmc.LOGINFO)
                add_success, add_msg = add_source_directory(clean_path)
                xbmc.log(f"[STRM同步工具] 添加DAV源目录结果: {add_msg}", xbmc.LOGINFO)
            
            result_msg = [
                f"处理{target_type}：{get_display_name(clean_path) if is_directory_path(clean_path) else os.path.basename(clean_path)}",
                f"新增STRM文件：{new_count} 个",
                f"更新STRM文件：{updated_count} 个"
            ]
            
            if error_list:
                result_msg.append(f"\n错误 ({len(error_list)})：")
                for err in error_list[:5]:
                    result_msg.append(f"- {err}")
                if len(error_list) > 5:
                    result_msg.append(f"- 还有 {len(error_list)-5} 个错误")
            
            xbmcgui.Dialog().ok("STRM生成完成", "\n".join(result_msg))

        finally:
            progress.close()
        
        confirm_open_strm()
        return
    
    sources = load_source_directories()
    if new_source in sources:
        confirm = xbmcgui.Dialog().yesno(
            "源目录已存在",
            "您选择的源目录已经生成过STRM文件，是否重新生成？"
        )
        if not confirm:
            return
        success = True
        msg = "源目录已存在，重新生成STRM"
    else:
        success, msg = add_source_directory(new_source)
        if not success:
            xbmcgui.Dialog().ok("操作失败", msg)
            return
    
    progress = xbmcgui.DialogProgress()
    progress.create("同步目录", f"处理：{get_display_name(new_source)}")
    
    try:
        new_count, updated_count, error_list, valid_source_keys = process_source_directory(new_source, progress)
        
        if not progress.iscanceled():
            existing_strm_for_src = collect_existing_strm(include_mtime=False, source_dir_filter=new_source)
            obsolete_strm_paths = [p for k, p in existing_strm_for_src.items() if k not in valid_source_keys]
            delete_count = 0
            
            if obsolete_strm_paths:
                progress.close()
                confirm = xbmcgui.Dialog().yesno(
                    "发现过时文件",
                    f"在 '{get_display_name(new_source)}' 中，有 {len(obsolete_strm_paths)} 个STRM文件对应的源文件已删除。\n是否删除？"
                )
                if confirm:
                    progress.create("删除过时文件", "正在处理")
                    for i, strm_path in enumerate(obsolete_strm_paths):
                        try:
                            if os.path.exists(strm_path):
                                os.remove(strm_path)
                                delete_count += 1
                        except Exception as e:
                            error_list.append(f"删除{os.path.basename(strm_path)}失败：{str(e)}")
                        progress_percent = int((i+1)/len(obsolete_strm_paths)*100)
                        progress.update(progress_percent, f"删除：{os.path.basename(strm_path)}")
                        if progress.iscanceled(): break

    finally:
        progress.close()
    
    delete_empty_dirs(TARGET_DIR)
    
    result_msg = [
        f"源目录：{get_display_name(new_source)}",
        f"{msg}",
        f"新增STRM文件：{new_count} 个",
        f"更新STRM文件：{updated_count} 个",
        f"删除过时文件：{delete_count} 个"
    ]
    
    if error_list:
        result_msg.append(f"\n错误 ({len(error_list)})：")
        for err in error_list[:5]:
            result_msg.append(f"- {err}")
        if len(error_list) > 5:
            result_msg.append(f"- 还有 {len(error_list)-5} 个错误")
    
    xbmcgui.Dialog().ok("同步完成", "\n".join(result_msg))
    confirm_open_strm()

# -------------------------- 菜单与入口 --------------------------
def show_manual_sync_menu():
    options = [
        "添加源目录生成STRM",
        "手动选择同步源目录",
        "手动选择删除源目录",
        "备份/恢复STRM文件",
        "同步生成115老接口STRM文件夹"  # 新增选项
    ]
    return xbmcgui.Dialog().select("手动同步模式选择", options)

def show_source_selection_menu():
    source_dirs = load_source_directories()
    if not source_dirs:
        xbmcgui.Dialog().ok("同步失败", "未找到源目录，请先添加源目录")
        return None
    
    options = ["所有文件夹"]
    options.extend([get_display_name(dir) for dir in source_dirs])
    
    selected = xbmcgui.Dialog().select("选择要同步的目录", options)
    if selected == -1:
        xbmcgui.Dialog().ok("操作取消", "未选择源目录")
        return None
    
    if selected == 0:
        return source_dirs
    else:
        return [source_dirs[selected - 1]]

def select_directory(title, default_path):
    result = xbmcgui.Dialog().browse(
        type=3,
        heading=title,
        shares="all",
        defaultt=default_path,
        useThumbs=False,
        treatAsFolder=True,
        mask=""
    )
    
    if not result or result == default_path:
        xbmcgui.Dialog().ok("操作取消", "未选择源目录")
        return None
    
    return result

def auto_mode():
    source_dirs = load_source_directories()
    strm_exists = os.path.exists(TARGET_DIR) and os.path.isdir(TARGET_DIR)
    strm_empty = True
    
    if strm_exists:
        for _, _, files in os.walk(TARGET_DIR):
            if any(f.lower().endswith('.strm') for f in files):
                strm_empty = False
                break
    
    if not source_dirs or (strm_exists and strm_empty):
        confirm = xbmcgui.Dialog().yesno(
            "未找到有效数据",
            "是否添加源目录并生成STRM文件？"
        )
        if confirm:
            add_source_and_sync()
    else:
        confirm_open_strm()

def handle_addstrm():
    selected_path = xbmc.getInfoLabel("ListItem.FilenameAndPath").strip()
    xbmc.log(f"[STRM同步工具] addstrm参数触发，获取选中路径：{selected_path}", xbmc.LOGINFO)
    
    if not selected_path:
        xbmcgui.Dialog().ok("操作失败", "未获取到当前选中项目的路径\n请确保在文件列表中选中一个视频文件或目录")
        return
    
    try:
        selected_path = unquote(selected_path)
    except Exception as e:
        xbmc.log(f"[STRM同步工具] 路径解码失败: {e}", xbmc.LOGERROR)
    
    if not is_valid_path(selected_path):
        xbmcgui.Dialog().ok("操作失败", f"路径不存在或无法访问：\n{selected_path}")
        return

    source_dir_to_add = None
    if is_directory_path(selected_path):
        source_dir_to_add = selected_path
    elif is_valid_path(selected_path):
        source_dir_to_add = os.path.dirname(selected_path)
    
    if source_dir_to_add:
        sources = load_source_directories()
        if source_dir_to_add in sources:
            confirm = xbmcgui.Dialog().yesno(
                "源目录已存在",
                "您选择的源目录或文件已经生成过STRM文件，是否重新生成？"
            )
            if not confirm:
                return

    progress = xbmcgui.DialogProgress()
    progress.create("生成STRM文件", f"正在处理：{os.path.basename(selected_path)}")
    
    try:
        if is_directory_path(selected_path):
            new_count, updated_count, error_list, valid_source_keys = process_source_directory(selected_path, progress)
            target_type = "目录"
        elif is_valid_path(selected_path) and (os.path.isfile(selected_path) or is_valid_network_path(selected_path)):
            new_count, updated_count, error_list, valid_source_keys = process_single_file(selected_path, progress)
            target_type = "文件"
        else:
            xbmcgui.Dialog().ok("操作失败", f"不支持的路径类型：{selected_path}")
            return
        
        if source_dir_to_add and (new_count > 0 or updated_count > 0):
            sources = load_source_directories()
            if source_dir_to_add not in sources:
                xbmc.log(f"[STRM同步工具] 尝试将源目录添加到记录: {source_dir_to_add}", xbmc.LOGINFO)
                add_success, add_msg = add_source_directory(source_dir_to_add)
                xbmc.log(f"[STRM同步工具] 添加源目录结果: {add_msg}", xbmc.LOGINFO)
        
        result_msg = [
            f"处理{target_type}：{get_display_name(selected_path) if is_directory_path(selected_path) else os.path.basename(selected_path)}",
            f"新增STRM文件：{new_count} 个",
            f"更新STRM文件：{updated_count} 个"
        ]
        
        if error_list:
            result_msg.append(f"\n错误 ({len(error_list)})：")
            for err in error_list[:5]:
                result_msg.append(f"- {err}")
            if len(error_list) > 5:
                result_msg.append(f"- 还有 {len(error_list)-5} 个错误")
        
        xbmcgui.Dialog().ok("STRM生成完成", "\n".join(result_msg))

    finally:
        progress.close()
    
    confirm_open_strm()

def handle_allsync():
    confirm = xbmcgui.Dialog().yesno(
        "关机前同步",
        "是否关机前同步所有STRM文件？\n同步完成后将自动关机"
    )
    
    if confirm:
        source_dirs = load_source_directories()
        if not source_dirs:
            xbmcgui.Dialog().ok("同步失败", "未找到源目录，无法同步")
            xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,turnoff)')
            return
        
        sync_selected_source(source_dirs, auto_shutdown=True)
    else:
        xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,turnoff)')

def main():
    initialize()
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    if "addstrm" in args:
        handle_addstrm()
        return
    
    if "allsync" in args:
        handle_allsync()
        return
    
    if "manualsync" in args:
        selected = show_manual_sync_menu()
        if selected == 0:
            add_source_and_sync()
        elif selected == 1:
            selected_dirs = show_source_selection_menu()
            if selected_dirs is not None and len(selected_dirs) > 0:
                sync_selected_source(selected_dirs)
                confirm_open_strm()
        elif selected == 2:  # 修复：现在正确处理"手动选择删除源目录"
            show_delete_source_menu()
        elif selected == 3:
            backup_restore_selected = show_backup_restore_menu()
            if backup_restore_selected == 0:
                backup_strm()
            elif backup_restore_selected == 1:
                restore_strm()
        elif selected == 4:  # 新增分支处理115老接口STRM生成
            xbmc.executebuiltin('RunScript(special://skin/scripts/115strm.py,manual)')
    else:
        auto_mode()

if __name__ == '__main__':
    main()
    # 在脚本退出前执行115STRM_SYNC脚本
    xbmc.executebuiltin('RunScript(special://skin/scripts/115strm.py,silent)')