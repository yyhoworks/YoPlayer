# -*- coding: utf-8 -*-
import xbmc
import xbmcvfs
import sys
import re
import random
import time  # 修复：添加缺失的 time 模块导入

# 单位换算常量
UNIT_GB = 1024 ** 3
UNIT_MB = 1024 ** 2
LOG_TAG = "[FileSize脚本] "

def log_info(msg):
    xbmc.log(LOG_TAG + str(msg), level=xbmc.LOGINFO)

def log_error(msg):
    xbmc.log(LOG_TAG + str(msg), level=xbmc.LOGERROR)

def log_warning(msg):
    xbmc.log(LOG_TAG + str(msg), level=xbmc.LOGWARNING)

def get_directory_total_size_by_xbmcvfs(dir_path):
    """递归计算文件夹总大小，保留所有兼容修复"""
    total_size = 0
    dir_path = dir_path.rstrip("/\\").strip()
    try:
        dirs, files = xbmcvfs.listdir(dir_path)
    except Exception as e:
        log_warning(f"无法读取目录: {dir_path}")
        return total_size

    for file_name in files:
        file_path = f"{dir_path}\\{file_name}"
        try:
            f = xbmcvfs.File(file_path)
            file_size = f.size()
            f.close()
            if file_size > 0:
                total_size += file_size
        except:
            continue

    for sub_dir in dirs:
        sub_dir_path = f"{dir_path}\\{sub_dir}"
        total_size += get_directory_total_size_by_xbmcvfs(sub_dir_path)
    return total_size

def get_file_size_by_xbmcvfs(file_path):
    """获取单个文件大小，保留所有兼容修复"""
    file_size = 0
    if not xbmcvfs.exists(file_path):
        log_warning(f"文件不存在: {file_path}")
        return file_size
    try:
        f = xbmcvfs.File(file_path)
        file_size = f.size()
        f.close()
    except Exception as e:
        log_error(f"非文件路径: {file_path}")
        file_size = 0
    return file_size

def format_file_size(size_bytes):
    """格式化文件大小：数字与GB/MB之间无空格"""
    if size_bytes >= UNIT_GB:
        size = round(size_bytes / UNIT_GB, 2)
        return f"{size}GB"
    else:
        size = round(size_bytes / UNIT_MB, 2)
        return f"{size}MB"

def get_file_basename(path):
    """解析文件名"""
    path = path.replace("\\", "/")
    return path.split("/")[-1] if "/" in path else path

def get_file_dirname(path):
    """解析文件所在目录"""
    path = path.replace("\\", "/").rstrip("/")
    return path.rsplit("/", 1)[0] if "/" in path else ""

def get_upper_file_ext_custom(file_name):
    """核心规则：M2TS/WEBM/AVCH/M4V保留4位大写，其他扩展名保留3位大写"""
    keep_4_char = ["M2TS", "WEBM", "AVCH", "M4V"]
    if "." in file_name:
        ext = file_name.split(".")[-1].strip().upper()
        if ext in keep_4_char:
            return ext
        else:
            return ext[:3]
    return ""

def standardize_filesize_str(s):
    """标准化清洗：剔除字符串首尾所有多余字符，保留核心主体（修复索引越界错误）"""
    if not s:
        return ""
    while s:
        first_char_valid = s[0].strip() and s[0] in "0123456789未"
        if not first_char_valid:
            s = s[1:]
        else:
            break
    while s:
        last_char_valid = s[-1].strip() and s[-1] in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ盘"
        if not last_char_valid:
            s = s[:-1]
        else:
            break
    return s.strip()

def read_strm_real_path(strm_file_path):
    real_video_path = ""
    try:
        strm_file = xbmcvfs.File(strm_file_path, 'r')
        real_video_path = strm_file.read().strip()
        strm_file.close()
        log_info(f"✅ 读取STRM文件成功，真实路径：{real_video_path}")
    except Exception as e:
        log_warning(f"⚠️ 读取STRM文件失败: {strm_file_path}, 错误: {str(e)}")
    return real_video_path

def wait_for_shortpath():
    log_info("⏳ 等待Skin.String(shortpath)不为空...")
    while True:
        shortpath_value = xbmc.getInfoLabel("Skin.String(shortpath)").strip()
        if shortpath_value:
            log_info(f"✅ Skin.String(shortpath)已获取值: {shortpath_value}")
            return shortpath_value
        xbmc.sleep(500)

def wait_for_chapter_count(min_count=8, timeout_sec=60):
    """等待Player.ChapterCount达到指定值"""
    log_info(f"⏳ 检测到VideoPlayer.HasMenu为true，等待Player.ChapterCount >= {min_count}...")
    start_time = time.time()
    while True:
        chapter_count_str = xbmc.getInfoLabel("Player.ChapterCount").strip()
        try:
            chapter_count = int(chapter_count_str) if chapter_count_str else 0
        except ValueError:
            chapter_count = 0
            
        if chapter_count >= min_count:
            log_info(f"✅ Player.ChapterCount 已达到 {chapter_count}，继续执行")
            return
            
        if time.time() - start_time > timeout_sec:
            log_warning(f"⚠️ 等待Player.ChapterCount超时({timeout_sec}秒)，继续执行后续逻辑")
            return
            
        xbmc.sleep(500)

def get_player_duration_in_seconds():
    # 优化逻辑：判断 VideoPlayer.HasMenu
    has_menu = xbmc.getCondVisibility("VideoPlayer.HasMenu")
    if has_menu:
        wait_for_chapter_count(8)
        
    duration_str = xbmc.getInfoLabel("Player.Duration").strip()
    if not duration_str:
        return 0
    
    try:
        parts = duration_str.split(':')
        
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        else:
            return int(duration_str)
    except:
        log_warning(f"无法解析播放时长: {duration_str}")
        return 0

def calculate_bitrate(file_size_mb, duration_seconds):
    if duration_seconds <= 0:
        return 0
    bitrate = (file_size_mb * 8) / duration_seconds
    return round(bitrate, 2)

def main():
    log_info("▶ 文件大小脚本执行中")
    
    if 'delay' in sys.argv:
        log_info("✅ 检测到【delay】参数，开始等待播放时长>3秒后执行核心逻辑...")
        while True:
            play_time_ss = xbmc.getInfoLabel("Player.Time(ss)")
            try:
                play_seconds = float(play_time_ss) if play_time_ss else 0.0
            except:
                play_seconds = 0.0
            if play_seconds > 1.0:
                log_info(f"✅ 播放时长达标({play_seconds:.1f}秒)，开始执行核心逻辑")
                break
            xbmc.sleep(1000)
    
    if 'detail' in sys.argv:
        log_info("✅ 检测到【detail】参数，开始监测Skin.String(shortpath)...")
        file_path = wait_for_shortpath()
    else:
        file_path = xbmc.getInfoLabel("Player.FileNameAndPath").strip()

        if file_path == "":
            log_error("❌ 未获取到有效路径")
            xbmc.executebuiltin('Skin.SetString(filesize, "")')
            xbmc.executebuiltin('Skin.SetString(totalbitrate, "")')
            return
    
    if file_path.lower().endswith(".strm"):
        log_info(f"✅ 探测到STRM文件: {file_path}")
        real_path = read_strm_real_path(file_path)
        if real_path:
            file_path = real_path

    raw_filename = get_file_basename(file_path)
    file_name = raw_filename.lower()
    file_dir = get_file_dirname(file_path)
    final_size = 0
    filesize_value = ""

    if file_name != "index.bdmv":
        file_ext = get_upper_file_ext_custom(raw_filename)
        final_size = get_file_size_by_xbmcvfs(file_path)
        if final_size > 0:
            size_text = format_file_size(final_size)
            filesize_value = f"{size_text} - {file_ext}"
        else:
            filesize_value = f"未知大小 - {file_ext}"
    else:
        file_type = "BDMV原盘文件夹"
        stream_folder = f"{file_dir}\\STREAM"
        final_size = get_directory_total_size_by_xbmcvfs(stream_folder)
        if final_size == 0:
            stream_folder = f"{file_dir}\\stream"
            final_size = get_directory_total_size_by_xbmcvfs(stream_folder)
        if final_size > 0:
            size_text = format_file_size(final_size)
            filesize_value = f"{size_text} - {file_type}"
        else:
            filesize_value = f"未知大小 - {file_type}"

    filesize_standard = standardize_filesize_str(filesize_value)
    xbmc.executebuiltin(f'Skin.SetString(filesize, "{filesize_standard}")')
    log_info(f"✅ 标准化完成并赋值成功: {filesize_standard}")

    duration_seconds = get_player_duration_in_seconds()
    log_info(f"✅ 播放时长: {duration_seconds}秒")
    
    if "未知" in filesize_standard or final_size <= 0:
        log_info("❌ 文件大小未知或无效，设置比特率为空")
        xbmc.executebuiltin('Skin.SetString(totalbitrate, "")')
    else:
        file_size_mb = final_size / UNIT_MB
        log_info(f"✅ 文件大小(MB): {file_size_mb}")
        
        bitrate = calculate_bitrate(file_size_mb, duration_seconds)
        log_info(f"✅ 计算得到比特率: {bitrate} Mbps")
        
        xbmc.executebuiltin(f'Skin.SetString(totalbitrate, "{bitrate}")')

    log_info("◀ 脚本执行结束")
    sys.exit()

if __name__ == "__main__":
    main()