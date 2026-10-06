# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import requests
import os
import tarfile
import re
import shutil
import sys  # 导入sys模块读取命令行参数
from requests.exceptions import RequestException
import time

# ===================== 自定义内核版本链接列表 =====================
# 当列表为空或内核版本名为空字符串时，选择窗口将不显示自定义内核选项
CUSTOM_KERNELS = [
    ("", "https://cdn.gh-proxy.org/https://github.com/avdvplus/Builds/releases/download/avdvplus_R9/Update_CoreELEC-Amlogic-ng.arm-21.3-Omega_avdvplus_R9_20260323131303.tar"),
]

# ===================== 核心配置常量（精准匹配需求，请勿修改） =====================
VERSION_URL = "https://gitee.com/ce-minsk/ce-kernel/raw/master/kernel/version.txt"
KERNEL_FILE_BASE_URL = "https://gitee.com/ce-minsk/ce-kernel/raw/master/kernel"
CACHE_DIR = "/storage/.resource/"       # 缓存目录-优先读取/下载分片/解压存放
TARGET_DIR = "/storage/.update/"         # 最终内核文件存放目录
TOTAL_FILE_SIZE_MB = 265                 # 进度条基准值 265MB = 100%
DATE_PATTERN = re.compile(r'(\d{8})')    # 提取8位纯数字年月日
LOG_TAG = "[CE-KernelUpdate] "           # 日志专属标记，方便检索
FORCE_SWITCH_OPTION = "强制切换内核(忽略CPM和原版/夜版兼容问题)"  # 保留之前的强制选项

# ===================== 【核心修复】日志输出函数 - 移到所有调用之前 =====================
def log(message, level=xbmc.LOGINFO):
    """
    日志规则：正常INFO极简输出，错误ERROR详细完整输出
    level=xbmc.LOGINFO  → 极简日志，只输出关键流程
    level=xbmc.LOGERROR → 详细日志，完整错误信息+路径+原因
    """
    try:
        log_msg = f"{LOG_TAG}{str(message)}".encode('utf-8', 'ignore').decode('utf-8')
        xbmc.log(log_msg, level)
    except Exception as e:
        xbmc.log(f"{LOG_TAG}日志输出异常: {str(e)}", level=xbmc.LOGERROR)

# ===================== 初始化环境（现在调用log函数时已定义） =====================
# 创建必要目录，不存在则新建
for dir_path in [CACHE_DIR, TARGET_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

dialog = xbmcgui.Dialog()
# 判断是否携带nocheck参数（忽略大小写）
skip_check = "nocheck" in [arg.lower() for arg in sys.argv[1:]]
if skip_check:
    log("检测到nocheck参数，将跳过内核兼容性校验", xbmc.LOGINFO)

# ===================== 核心工具函数 =====================
def get_8digit_build_date():
    """读取$INFO[Skin.String(BuildDate)]并提取其中的8位年月日纯数字"""
    build_date_str = xbmc.getInfoLabel("Skin.String(BuildDate)")
    match = DATE_PATTERN.search(build_date_str)
    return match.group(1) if match else ""

def read_kernel_version_list():
    """从远程读取version.txt，返回去空行的纯净内核版本列表"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android) Kodi/20.0"}
        resp = requests.get(VERSION_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        version_lines = [line.strip() for line in resp.text.splitlines() if line.strip()]
        return version_lines
    except RequestException as e:
        err_msg = f"读取内核版本列表失败: {str(e)}"
        log(err_msg, xbmc.LOGERROR)  # 错误详细日志
        dialog.ok("错误", err_msg)
        return []

def get_pretty_name():
    """从/etc/os-release读取PRETTY_NAME字段，读取失败返回空字符串"""
    pretty_name = ""
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f.readlines():
                if line.startswith("PRETTY_NAME="):
                    pretty_name = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception as e:
        log(f"读取系统环境失败: {str(e)}", xbmc.LOGERROR)  # 错误详细日志
    return pretty_name

def copy_file_with_progress(src_file, dst_file):
    """带进度条的大文件复制函数，适配KODI弹窗，复制失败输出详细错误日志"""
    if not os.path.exists(src_file):
        err_msg = f"源文件不存在：{src_file}"
        log(err_msg, xbmc.LOGERROR)
        return False
    
    file_size = os.path.getsize(src_file)
    copied_size = 0
    chunk_size = 4096 * 1024

    prog_dialog = xbmcgui.DialogProgress()
    prog_dialog.create("文件复制中", f"正在复制 {os.path.basename(src_file)}")
    
    try:
        with open(src_file, 'rb') as fsrc, open(dst_file, 'wb') as fdst:
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk: break
                fdst.write(chunk)
                copied_size += len(chunk)
                
                percent = int((copied_size / file_size) * 100)
                prog_dialog.update(percent, f"进度: {percent}%")
                
                if prog_dialog.iscanceled():
                    prog_dialog.close()
                    if os.path.exists(dst_file): os.remove(dst_file)
                    dialog.ok("提示", "已取消文件复制！")
                    return False
        prog_dialog.close()
        return True
    except Exception as e:
        prog_dialog.close()
        err_msg = f"文件复制出错：{str(e)} | 源:{src_file} → 目标:{dst_file}"
        log(err_msg, xbmc.LOGERROR)  # 错误详细日志
        dialog.ok("复制失败", err_msg)
        if os.path.exists(dst_file): os.remove(dst_file)
        return False

def download_custom_kernel(kernel_name, download_url):
    """下载自定义链接的内核文件到缓存目录"""
    save_path = os.path.join(CACHE_DIR, f"{kernel_name}.tar")
    
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android) Kodi/20.0"}
    
    try:
        response = requests.get(download_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # 获取文件总大小
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        chunk_size = 4096 * 1024  # 4MB chunks
        start_time = time.time()
        last_update_time = start_time
        last_downloaded_size = 0
        
        prog_dialog = xbmcgui.DialogProgress()
        prog_dialog.create("自定义内核下载中", f"正在下载 {kernel_name}")
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    current_time = time.time()
                    
                    # 计算下载速度（每秒更新一次显示）
                    if current_time - last_update_time >= 1.0:
                        time_diff = current_time - last_update_time
                        size_diff = downloaded_size - last_downloaded_size
                        speed_bps = size_diff / time_diff
                        speed_mbps = speed_bps / (1024 * 1024)
                        
                        if total_size > 0:
                            percent = int((downloaded_size / total_size) * 100)
                            downloaded_mb = downloaded_size / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            prog_dialog.update(percent, f"进度: {percent}% ({downloaded_mb:.2f}MB/{total_mb:.2f}MB)\n速度: {speed_mbps:.2f}MB/s")
                        else:
                            # 如果无法获取总大小，使用估算
                            downloaded_mb = downloaded_size / (1024 * 1024)
                            prog_dialog.update(0, f"已下载: {downloaded_mb:.2f}MB\n速度: {speed_mbps:.2f}MB/s")
                        
                        last_update_time = current_time
                        last_downloaded_size = downloaded_size
                    
                    if prog_dialog.iscanceled():
                        prog_dialog.close()
                        if os.path.exists(save_path):
                            os.remove(save_path)
                        dialog.ok("提示", "已取消自定义内核下载！")
                        return None
        
        prog_dialog.close()
        return save_path
    except Exception as e:
        err_msg = f"自定义内核下载失败: {str(e)} | URL: {download_url}"
        log(err_msg, xbmc.LOGERROR)  # 错误详细日志
        dialog.ok("下载失败", err_msg)
        if os.path.exists(save_path):
            os.remove(save_path)
        return None

def download_kernel_files(select_kernel_name):
    """分片下载内核文件到缓存目录，仅错误时输出详细日志，正常仅极简日志"""
    file_suffix = 1
    download_files = []
    total_download_size = 0
    download_url_prefix = f"{KERNEL_FILE_BASE_URL}/{select_kernel_name}/{select_kernel_name}.tar."
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android) Kodi/20.0"}

    prog_dialog = xbmcgui.DialogProgress()
    prog_dialog.create("内核文件下载中", f"正在下载 {select_kernel_name}，请稍候...")

    # 记录开始时间用于计算整体下载速度
    overall_start_time = time.time()
    last_update_time = overall_start_time
    last_overall_size = 0

    while True:
        file_num = f"{file_suffix:03d}"
        file_url = download_url_prefix + file_num
        save_path = os.path.join(CACHE_DIR, f"{select_kernel_name}.tar.{file_num}")

        try:
            resp = requests.get(file_url, headers=headers, stream=True, timeout=15)
            if resp.status_code == 404: break
            resp.raise_for_status()
        except RequestException: break

        if os.path.exists(save_path): os.remove(save_path)

        try:
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=4096*4):
                    if chunk:
                        f.write(chunk)
                        total_download_size += len(chunk)
                        
                        # 每秒更新一次下载速度
                        current_time = time.time()
                        if current_time - last_update_time >= 1.0:
                            time_diff = current_time - last_update_time
                            size_diff = total_download_size - last_overall_size
                            speed_bps = size_diff / time_diff
                            speed_mbps = speed_bps / (1024 * 1024)
                            
                            percent = int((total_download_size / (TOTAL_FILE_SIZE_MB * 1024 * 1024)) * 100)
                            percent = 100 if percent > 100 else percent
                            downloaded_mb = total_download_size / (1024 * 1024)
                            progress_text = f"{select_kernel_name} | 分片:{file_num} | {percent}% ({downloaded_mb:.2f}MB)\n速度: {speed_mbps:.2f}MB/s"
                            prog_dialog.update(percent, progress_text)
                            
                            last_update_time = current_time
                            last_overall_size = total_download_size
                        
                        if prog_dialog.iscanceled():
                            prog_dialog.close()
                            dialog.ok("提示", "已取消内核文件下载！")
                            for f_del in download_files: os.remove(f_del)
                            return []
            download_files.append(save_path)
            file_suffix += 1
        except Exception as e:
            prog_dialog.close()
            err_msg = f"分片{file_num}下载失败: {str(e)} | 文件路径:{save_path}"
            log(err_msg, xbmc.LOGERROR)  # 错误详细日志
            dialog.ok("下载失败", err_msg)
            for f_del in download_files: os.remove(f_del)
            return []

    prog_dialog.close()
    return download_files

def merge_and_extract_files(select_kernel_name, download_files):
    """合并解压分片文件，仅错误时输出详细日志"""
    if not download_files: return False
    target_tar = os.path.join(CACHE_DIR, f"{select_kernel_name}.tar")

    try:
        with open(target_tar, "wb") as out_f:
            for file_path in sorted(download_files):
                with open(file_path, "rb") as in_f:
                    out_f.write(in_f.read())

        if tarfile.is_tarfile(target_tar):
            for file_path in download_files: os.remove(file_path)
            return True
        else:
            err_msg = "合并后的文件不是有效的tar格式，文件损坏！"
            log(err_msg, xbmc.LOGERROR)
            dialog.ok("解压失败", err_msg)
            if os.path.exists(target_tar): os.remove(target_tar)
            return False
    except Exception as e:
        err_msg = f"文件合并解压失败: {str(e)} | 目标文件:{target_tar}"
        log(err_msg, xbmc.LOGERROR)  # 错误详细日志
        dialog.ok("解压失败", err_msg)
        if os.path.exists(target_tar): os.remove(target_tar)
        for file_path in download_files: os.remove(file_path)
        return False

# ===================== 修改后的兼容性检查函数 =====================
def check_kernel_compatibility(pretty_name, select_kernel):
    """
    修改后的兼容性检查函数
    将包含'avdvplus'字符、'cpm'字符和'community'字符视为同一种内核，允许互相切换
    所有字符比较不区分大小写
    """
    # 解析当前系统类型 - 转换为小写进行比较
    pretty_name_lower = pretty_name.lower()
    current_is_avdvplus = "avdvplus" in pretty_name_lower
    current_is_cpm = "cpm" in pretty_name_lower
    current_is_community = "community" in pretty_name_lower  # 新增community判断
    current_is_official_or_nightly = "official" in pretty_name_lower or "nightly" in pretty_name_lower
    
    # 解析目标内核类型 - 转换为小写进行比较
    select_kernel_lower = select_kernel.lower()
    target_is_avdvplus = "avdvplus" in select_kernel_lower
    target_is_cpm = "cpm" in select_kernel_lower
    target_is_community = "community" in select_kernel_lower  # 新增community判断
    target_is_official_or_nightly = "official" in select_kernel_lower or "nightly" in select_kernel_lower
    
    # 将avdvplus、cpm和community视为同一种内核类型
    current_is_advanced_kernel = current_is_avdvplus or current_is_cpm or current_is_community
    target_is_advanced_kernel = target_is_avdvplus or target_is_cpm or target_is_community
    
    # 兼容性判断逻辑
    if current_is_advanced_kernel and target_is_advanced_kernel:
        # avdvplus、cpm和community之间可以互相切换
        return True, ""
    elif current_is_official_or_nightly and target_is_official_or_nightly:
        # official和nightly之间可以互相切换
        return True, ""
    elif current_is_advanced_kernel and target_is_official_or_nightly:
        # avdvplus/cpm和community 不能切换到 official/nightly
        return False, "当前内核属于CPM分支(AVDVPlus/CPM)，不能切换到原版(Official/Nightly)内核，请选择CPM分支内核！"
    elif current_is_official_or_nightly and target_is_advanced_kernel:
        # official/nightly 不能切换到 avdvplus/cpm和community
        return False, "当前内核是原版(Official/Nightly)，不能切换到CPM分支(AVDVPlus/CPM)内核，请选择原版内核！"
    else:
        # 其他情况，按照原始逻辑处理
        return False, "获取当前内核类型失败，请尝试强制切换模式！"

# ===================== 主逻辑入口 - 完整保留所有业务规则 =====================
def main():
    log("内核切换脚本 开始运行", xbmc.LOGINFO)
    while True:
        # 1. 读取8位构建日期 + 远程内核列表
        build_date_8digit = get_8digit_build_date()
        kernel_list = read_kernel_version_list()
        if not kernel_list: return

        # 2. 构建选择列表，只有当自定义内核列表非空且内核版本名非空时才添加
        select_options = []
        kernel_name_map = {}
        
        # 检查自定义内核列表，只有当存在非空内核版本名时才添加到选择列表
        valid_custom_kernels = [(name, url) for name, url in CUSTOM_KERNELS if name.strip()]  # 过滤掉空字符串的内核版本
        if valid_custom_kernels:
            for custom_kernel_name, _ in valid_custom_kernels:
                option_text = custom_kernel_name
                if build_date_8digit and build_date_8digit in custom_kernel_name:
                    option_text = f"{custom_kernel_name} [COLOR green][当前内核][/COLOR]"
                select_options.append(option_text)
                kernel_name_map[option_text] = custom_kernel_name
        
        # 添加远程内核到选择列表
        for kernel_name in kernel_list:
            option_text = kernel_name
            if build_date_8digit and build_date_8digit in kernel_name:
                option_text = f"{kernel_name} [COLOR green][当前内核][/COLOR]"
            select_options.append(option_text)
            kernel_name_map[option_text] = kernel_name
        
        # 3. 内核选择弹窗
        select_idx = dialog.select("选择需要切换的内核版本", select_options)
        if select_idx == -1:
            log("用户取消选择，脚本结束", xbmc.LOGINFO)
            return
        
        # 获取选中内核信息
        select_option_text = select_options[select_idx]
        select_kernel = kernel_name_map[select_option_text]
        
        # 判断是否为自定义内核
        is_custom_kernel = select_kernel in [name for name, _ in valid_custom_kernels]
        
        kernel_tar_file = f"{select_kernel}.tar"
        cache_tar_path = os.path.join(CACHE_DIR, kernel_tar_file)
        target_tar_path = os.path.join(TARGET_DIR, kernel_tar_file)

        # 4. 选中当前内核，弹窗后返回选择窗
        if "[当前内核]" in select_option_text:
            dialog.ok("提示", f"当前系统内核就是「{select_kernel}」，无需转换！")
            continue
        
        # 5. 转换确认弹窗
        confirm_switch = dialog.yesno("确认转换", f"确认转换「{select_kernel}」内核？")
        if not confirm_switch: continue
        
        # 6. 内核兼容性校验（nocheck参数时跳过）
        if not skip_check:  # 仅当未携带nocheck参数时执行校验
            pretty_name = get_pretty_name()
            
            if not pretty_name:
                dialog.ok("错误", "无法获取系统信息，请检查系统环境！")
                log("脚本终止 - 无法获取系统信息", xbmc.LOGERROR)
                return
            
            # 使用修改后的兼容性检查函数
            is_compatible, error_msg = check_kernel_compatibility(pretty_name, select_kernel)
            
            if not is_compatible:
                dialog.ok("不兼容提示", error_msg)
                log(f"脚本终止 - {error_msg}", xbmc.LOGERROR)
                return
        else:
            # 携带nocheck参数时，仅记录日志，无弹窗
            log("已跳过内核兼容性校验，请注意风险！", xbmc.LOGINFO)

        # ===================== 核心逻辑：处理自定义内核或常规内核 =====================
        if is_custom_kernel:
            # 查找自定义内核的下载链接
            custom_url = None
            for name, url in valid_custom_kernels:
                if name == select_kernel:
                    custom_url = url
                    break
            
            if not custom_url:
                dialog.ok("错误", "找不到自定义内核的下载链接！")
                log("脚本终止 - 无法找到自定义内核下载链接", xbmc.LOGERROR)
                return
            
            # 下载自定义内核
            dialog.notification("开始下载", f"正在下载自定义内核 {select_kernel}", xbmcgui.NOTIFICATION_INFO, 3000)
            download_result = download_custom_kernel(select_kernel, custom_url)
            
            if not download_result:
                continue  # 下载失败，重新选择
            
            # 自定义内核下载完成后，直接复制到目标目录（跳过分片合并）
            copy_ok = copy_file_with_progress(cache_tar_path, target_tar_path)
            if copy_ok:
                reboot_confirm = dialog.yesno("操作完成", "自定义内核转换文件已处理完成，点击「是」立即重启执行内核转换\n点击「否」稍后手动重启执行内核转换。")
                if reboot_confirm:
                    xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,reboot)')
                log("自定义内核文件处理完成，脚本结束", xbmc.LOGINFO)
                return
        else:
            # 常规内核处理逻辑
            if os.path.exists(cache_tar_path):
                # 缓存存在 → 直接复制到目标目录
                copy_ok = copy_file_with_progress(cache_tar_path, target_tar_path)
                if copy_ok:
                    reboot_confirm = dialog.yesno("操作完成", "内核转换文件已处理完成，点击「是」立即重启执行内核转换\n点击「否」稍后手动重启执行内核转换。")
                    if reboot_confirm:
                        xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,reboot)')
                    log("内核文件处理完成，脚本结束", xbmc.LOGINFO)
                    return
            else:
                # 缓存不存在 → 下载→解压→复制
                dialog.notification("开始下载", f"正在下载 {select_kernel} 内核文件", xbmcgui.NOTIFICATION_INFO, 3000)
                download_files = download_kernel_files(select_kernel)
                if not download_files: continue

                extract_ok = merge_and_extract_files(select_kernel, download_files)
                if not extract_ok: continue

                copy_ok = copy_file_with_progress(cache_tar_path, target_tar_path)
                if copy_ok:
                    reboot_confirm = dialog.yesno("操作完成", "内核转换文件下载成功，点击「是」立即重启执行内核转换\n点击「否」稍后手动重启执行内核转换。")
                    if reboot_confirm:
                        xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,reboot)')
                    log("内核文件下载处理完成，脚本结束", xbmc.LOGINFO)
                    return

# ===================== 脚本启动 =====================
if __name__ == "__main__":
    main()