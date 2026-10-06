import os
import shutil
import subprocess
import xbmc
import xbmcgui
import sys
import urllib.parse
import xbmcvfs
import time
import threading

FLASH_DIR = "/flash"
RESOURCE_DIR = "/storage/.resource"
GUI_SETTINGS_CE = os.path.join(RESOURCE_DIR, "guisettingsce.xml")
GUI_SETTINGS_CPM = os.path.join(RESOURCE_DIR, "guisettingscpm.xml")
GUI_SETTINGS_CURRENT = "/storage/.kodi/userdata/guisettings.xml"
AUTOSTART_SCRIPT = "/storage/.config/autostart.sh"
BIND_LINE = "mount --bind /storage/.resource/settings.xml /usr/share/kodi/system/settings/settings.xml"
SETTINGS_XML = os.path.join(RESOURCE_DIR, "settings.xml")
UPDATE_DIR = "/storage/.update"  # 新增更新目录

# 两个标记文件
MARKER_CE = "/storage/.config/switch_to_ce"
MARKER_CPM = "/storage/.config/switch_to_cpm"


def get_build_date():
    """获取皮肤字符串 BuildDate 的值"""
    return xbmc.getInfoLabel("Skin.String(BuildDate)") or ""


def set_flash_writable():
    """将 /flash 挂载为可读写"""
    try:
        result = subprocess.run(
            ["mount", "-o", "remount,rw", FLASH_DIR],
            capture_output=True,
            text=True
        )
        xbmc.log(f"[DEBUG] 挂载 /flash 为可写命令执行结果: {result.returncode}", xbmc.LOGDEBUG)
        if result.returncode != 0:
            raise Exception(f"挂载 /flash 为可写失败: {result.stderr}")
        xbmc.log("[DEBUG] 成功将 /flash 挂载为可写", xbmc.LOGDEBUG)
        return True
    except Exception as e:
        xbmc.log(f"[ERROR] 挂载 /flash 为可写失败: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"无法挂载 /flash 为可写:\n{str(e)}")
        return False


def file_exists(filename):
    """检查文件是否存在"""
    full_path = os.path.join(FLASH_DIR, filename)
    exists = os.path.exists(full_path)
    xbmc.log(f"[DEBUG] 检查文件 {full_path} 是否存在: {exists}", xbmc.LOGDEBUG)
    return exists


def rename_file(old_name, new_name):
    """重命名文件"""
    old_path = os.path.join(FLASH_DIR, old_name)
    new_path = os.path.join(FLASH_DIR, new_name)
    xbmc.log(f"[DEBUG] 尝试重命名文件: {old_path} -> {new_path}", xbmc.LOGDEBUG)
    if os.path.exists(old_path):
        try:
            os.rename(old_path, new_path)
            xbmc.log(f"[DEBUG] 成功重命名文件: {old_path} -> {new_path}", xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log(f"[ERROR] 重命名文件失败: {old_path} -> {new_path}, 错误: {str(e)}", xbmc.LOGERROR)
            return False
    else:
        xbmc.log(f"[DEBUG] 源文件不存在，跳过重命名: {old_path}", xbmc.LOGDEBUG)
        return False


def ensure_resource_dir():
    """确保资源目录存在"""
    xbmc.log(f"[DEBUG] 确保资源目录存在: {RESOURCE_DIR}", xbmc.LOGDEBUG)
    os.makedirs(RESOURCE_DIR, exist_ok=True)
    xbmc.log(f"[DEBUG] 资源目录操作完成: {RESOURCE_DIR}", xbmc.LOGDEBUG)


def copy_gui_settings(src, dst):
    """复制 GUI 设置文件"""
    xbmc.log(f"[DEBUG] 开始复制 GUI 设置文件: {src} -> {dst}", xbmc.LOGDEBUG)
    try:
        shutil.copy2(src, dst)
        xbmc.log(f"[DEBUG] 成功复制 GUI 设置文件: {src} -> {dst}", xbmc.LOGDEBUG)
        return True
    except Exception as e:
        xbmc.log(f"[ERROR] 复制 GUI 设置文件失败: {src} -> {dst}, 错误: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"复制 GUI 设置文件失败:\n{str(e)}")
        return False


def reboot_system():
    """先同步数据再强制重启（加快重启速度）"""
    xbmc.log("同步数据并强制重启", xbmc.LOGINFO)
    xbmc.log("[DEBUG] 正在同步数据", xbmc.LOGDEBUG)
    subprocess.run(["sync"])
    xbmc.log("[DEBUG] 执行强制重启命令", xbmc.LOGDEBUG)
    subprocess.run(["reboot", "-f"])


def clean_bind_settings():
    """清理 autostart.sh 中的 bind 挂载命令和对应文件"""
    xbmc.log(f"[DEBUG] 开始清理 autostart.sh 中的 bind 设置", xbmc.LOGDEBUG)
    if os.path.exists(AUTOSTART_SCRIPT):
        try:
            xbmc.log(f"[DEBUG] 读取 autostart.sh 文件: {AUTOSTART_SCRIPT}", xbmc.LOGDEBUG)
            with open(AUTOSTART_SCRIPT, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = [line for line in lines if BIND_LINE not in line]

            if len(new_lines) != len(lines):
                xbmc.log(f"[DEBUG] 发现需要删除的 bind 行，开始写入新内容", xbmc.LOGDEBUG)
                with open(AUTOSTART_SCRIPT, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                xbmc.log("已从 autostart.sh 中删除 mount --bind 命令", xbmc.LOGINFO)

                if os.path.exists(SETTINGS_XML):
                    os.remove(SETTINGS_XML)
                    xbmc.log("已删除 /storage/.resource/settings.xml", xbmc.LOGINFO)
            else:
                xbmc.log("autostart.sh 中未发现需要删除的 mount --bind 命令", xbmc.LOGINFO)

        except Exception as e:
            xbmc.log(f"[ERROR] 清理 autostart.sh 失败: {str(e)}", xbmc.LOGERROR)


def setup_autostart_switch_logic():
    """确保 autostart.sh 中有分支切换逻辑"""
    xbmc.log(f"[DEBUG] 开始设置 autostart.sh 切换逻辑", xbmc.LOGDEBUG)
    if not os.path.exists(AUTOSTART_SCRIPT):
        xbmc.log(f"[DEBUG] autostart.sh 不存在，创建新文件", xbmc.LOGDEBUG)
        with open(AUTOSTART_SCRIPT, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
        os.chmod(AUTOSTART_SCRIPT, 0o755)
        xbmc.log(f"[DEBUG] autostart.sh 文件已创建并设置权限", xbmc.LOGDEBUG)

    switch_code = """
# GUI 分支切换逻辑
if [ -f "/storage/.config/switch_to_ce" ]; then
    cp "/storage/.resource/guisettingsce.xml" "/storage/.kodi/userdata/guisettings.xml"
    rm "/storage/.config/switch_to_ce"
elif [ -f "/storage/.config/switch_to_cpm" ]; then
    cp "/storage/.resource/guisettingscpm.xml" "/storage/.kodi/userdata/guisettings.xml"
    rm "/storage/.config/switch_to_cpm"
fi
"""

    with open(AUTOSTART_SCRIPT, "r", encoding="utf-8") as f:
        content = f.read()

    if "# GUI 分支切换逻辑" not in content:
        xbmc.log(f"[DEBUG] autostart.sh 中未找到切换逻辑，添加代码", xbmc.LOGDEBUG)
        with open(AUTOSTART_SCRIPT, "a", encoding="utf-8") as f:
            f.write(switch_code)
        xbmc.log(f"[DEBUG] 切换逻辑代码已添加到 autostart.sh", xbmc.LOGDEBUG)
    else:
        xbmc.log(f"[DEBUG] autostart.sh 中已存在切换逻辑", xbmc.LOGDEBUG)


def set_switch_marker(marker_file):
    """创建指定的切换标记文件"""
    xbmc.log(f"[DEBUG] 开始设置切换标记文件: {marker_file}", xbmc.LOGDEBUG)
    for m in [MARKER_CE, MARKER_CPM]:
        if os.path.exists(m):
            xbmc.log(f"[DEBUG] 删除旧标记文件: {m}", xbmc.LOGDEBUG)
            os.remove(m)
    with open(marker_file, "w", encoding="utf-8") as f:
        f.write("1")
    xbmc.log(f"[DEBUG] 创建新标记文件: {marker_file}", xbmc.LOGDEBUG)


def main():
    xbmc.log("[DEBUG] 开始执行 main 函数", xbmc.LOGDEBUG)
    has_ce = file_exists("KERNELce.img")
    has_cpm = file_exists("KERNELcpm.img")
    xbmc.log(f"[DEBUG] 检测到 KERNELce.img: {has_ce}, KERNELcpm.img: {has_cpm}", xbmc.LOGDEBUG)

    if has_ce and has_cpm:
        xbmc.log("[ERROR] 系统文件错误：同时存在 CE 和 CPM 内核文件", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", "系统文件错误，无法完成转换")
        return

    if not has_ce and not has_cpm:
        xbmc.log("[ERROR] 系统文件缺失：未找到 CE 或 CPM 内核文件", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("提示", "系统文件缺失，无法完成转换")
        return

    if not set_flash_writable():
        xbmc.log("[ERROR] 无法将 /flash 挂载为可写", xbmc.LOGERROR)
        return

    ensure_resource_dir()
    setup_autostart_switch_logic()

    build_date = get_build_date().lower()
    xbmc.log(f"[DEBUG] 获取到 BuildDate: {build_date}", xbmc.LOGDEBUG)
    dialog_title = "确认切换"
    dialog_message = ""

    if "cpm" in build_date:
        dialog_message = "将从 CPM 分支切换为原版，是否继续？"
    elif "ce" in build_date:
        dialog_message = "将从原版切换为 CPM 分支，是否继续？"
    else:
        dialog_message = "将切换CoreELEC的内核，是否继续？"

    if not xbmcgui.Dialog().yesno(dialog_title, dialog_message):
        xbmc.log("[DEBUG] 用户取消了操作", xbmc.LOGDEBUG)
        xbmcgui.Dialog().ok("已取消", "操作已取消")
        return

    build_date = get_build_date().lower()
    success_title = "完成"
    success_message = ""

    if has_ce:
        xbmc.log("[DEBUG] 检测到 CE 内核，开始切换到 CPM", xbmc.LOGDEBUG)
        rename_file("KERNEL.img", "KERNELcpm.img")
        rename_file("KERNEL.img.md5", "KERNELcpm.img.md5")
        rename_file("KERNELce.img", "KERNEL.img")
        rename_file("KERNELce.img.md5", "KERNEL.img.md5")

        rename_file("SYSTEM", "SYSTEMcpm")
        rename_file("SYSTEM.md5", "SYSTEMcpm.md5")
        rename_file("SYSTEMce", "SYSTEM")
        rename_file("SYSTEMce.md5", "SYSTEM.md5")

        clean_bind_settings()
        copy_gui_settings(GUI_SETTINGS_CURRENT, GUI_SETTINGS_CPM)
        set_switch_marker(MARKER_CE)

        if "cpm" in build_date:
            success_message = "已切换到原版(夜版)，系统将立即重启"
        elif "ce" in build_date:
            success_message = "已切换到CPM分支，系统将立即重启"
        else:
            success_message = "已完成切换CoreELEC内核，系统将立即重启"

    elif has_cpm:
        xbmc.log("[DEBUG] 检测到 CPM 内核，开始切换到 CE", xbmc.LOGDEBUG)
        rename_file("KERNEL.img", "KERNELce.img")
        rename_file("KERNEL.img.md5", "KERNELce.img.md5")
        rename_file("KERNELcpm.img", "KERNEL.img")
        rename_file("KERNELcpm.img.md5", "KERNEL.img.md5")

        rename_file("SYSTEM", "SYSTEMce")
        rename_file("SYSTEM.md5", "SYSTEMce.md5")
        rename_file("SYSTEMcpm", "SYSTEM")
        rename_file("SYSTEMcpm.md5", "SYSTEM.md5")

        clean_bind_settings()
        copy_gui_settings(GUI_SETTINGS_CURRENT, GUI_SETTINGS_CE)
        set_switch_marker(MARKER_CPM)

        if "cpm" in build_date:
            success_message = "已切换到原版(夜版)，系统将立即重启"
        elif "ce" in build_date:
            success_message = "已切换到CPM分支，系统将立即重启"
        else:
            success_message = "已完成切换CoreELEC内核，系统将立即重启"

    xbmcgui.Dialog().ok(success_title, success_message)
    xbmc.log(f"[DEBUG] 显示成功消息: {success_message}", xbmc.LOGDEBUG)
    reboot_system()


# ========== 获取指定目录下所有.tar后缀的内核文件 ========== 
def get_tar_kernel_files():
    """获取/storage/.resource/下所有.tar后缀文件，返回 纯净文件名列表 和 完整路径列表"""
    xbmc.log(f"[DEBUG] 开始扫描 {RESOURCE_DIR} 目录下的 .tar 文件", xbmc.LOGDEBUG)
    tar_file_names = []  # 存储 去掉.tar后缀的文件名，用于弹窗显示
    tar_file_paths = []  # 存储 完整的文件路径，用于删除操作
    if os.path.exists(RESOURCE_DIR):
        # 遍历目录下所有文件，筛选.tar后缀
        for file_name in os.listdir(RESOURCE_DIR):
            if file_name.endswith(".tar"):
                full_path = os.path.join(RESOURCE_DIR, file_name)
                tar_file_paths.append(full_path)
                clean_name = file_name.replace(".tar", "")
                tar_file_names.append(clean_name)
                xbmc.log(f"[DEBUG] 找到内核文件: {file_name} -> {clean_name}", xbmc.LOGDEBUG)
    xbmc.log(f"[DEBUG] 找到 {len(tar_file_names)} 个内核文件", xbmc.LOGDEBUG)
    return tar_file_names, tar_file_paths


# ========== 删除内核文件的核心逻辑 ========== 
def delete_kernel_files():
    """删除已下载的内核文件核心逻辑，完全匹配需求规则"""
    xbmc.log("[DEBUG] 开始执行删除内核文件操作", xbmc.LOGDEBUG)
    tar_names, tar_paths = get_tar_kernel_files()
    # 判断是否存在tar内核文件
    if not tar_names:
        xbmc.log("[DEBUG] 未发现已下载的内核文件", xbmc.LOGDEBUG)
        xbmcgui.Dialog().ok("提示", "未发现已下载的内核文件！")
        return

    # 构建二级删除选择框的选项列表
    delete_options = ["删除所有内核转换文件"]  # 第一项固定
    delete_options.extend(tar_names)  # 后续项为所有.tar文件的纯净名称

    # 弹出二级删除选择窗
    select_idx = xbmcgui.Dialog().select("选择要删除的内核文件", delete_options)
    xbmc.log(f"[DEBUG] 用户选择删除索引: {select_idx}", xbmc.LOGDEBUG)
    if select_idx == -1:
        xbmc.log("[DEBUG] 用户取消删除操作", xbmc.LOGDEBUG)
        return  # 用户取消选择，直接返回主选择窗

    try:
        if select_idx == 0:
            # 选择第一项：删除所有.tar内核文件
            xbmc.log("[DEBUG] 用户选择删除所有内核文件", xbmc.LOGDEBUG)
            for file_path in tar_paths:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    xbmc.log(f"[DEBUG] 已删除内核文件: {file_path}", xbmc.LOGDEBUG)
            xbmcgui.Dialog().ok("成功", "所有已下载的内核转换文件已全部删除！")
        else:
            # 选择单个文件：删除对应的.tar文件 (下标-1匹配对应路径)
            target_path = tar_paths[select_idx - 1]
            if os.path.exists(target_path):
                os.remove(target_path)
                xbmc.log(f"[DEBUG] 已删除单个内核文件: {target_path}", xbmc.LOGDEBUG)
                xbmcgui.Dialog().ok("成功", f"已删除内核文件：{delete_options[select_idx]}.tar")
    except Exception as e:
        xbmcgui.Dialog().ok("删除失败", f"文件删除出错：{str(e)}")
        xbmc.log(f"[ERROR] 删除内核tar文件失败: {str(e)}", xbmc.LOGERROR)

    # 核心规则：删除单个文件后，重新调用主选择窗，返回选择界面
    show_switch_select_dialog()


# ========== 获取目录可用空间函数 ========== 
def get_available_space(directory):
    """获取指定目录的可用空间（字节）- 使用shutil.disk_usage替代os.statvfs"""
    try:
        total, used, free = shutil.disk_usage(directory)
        xbmc.log(f"[DEBUG] 目录 {directory} 总空间: {total/(1024*1024):.2f}MB, 已用: {used/(1024*1024):.2f}MB, 可用: {free/(1024*1024):.2f}MB", xbmc.LOGDEBUG)
        return free  # 返回可用空间
    except Exception as e:
        xbmc.log(f"[ERROR] 获取目录 {directory} 可用空间失败: {str(e)}", xbmc.LOGERROR)
        return 0


def get_total_size_of_files(file_list, source_dir):
    """计算待移动文件的总大小（字节）"""
    total_size = 0
    for file_name in file_list:
        file_path = os.path.join(source_dir, file_name)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            total_size += size
            xbmc.log(f"[DEBUG] 文件 {file_path} 大小: {size} 字节 ({size/(1024*1024):.2f} MB)", xbmc.LOGDEBUG)
    xbmc.log(f"[DEBUG] 待移动文件总大小: {total_size} 字节 ({total_size/(1024*1024):.2f} MB)", xbmc.LOGDEBUG)
    return total_size


def check_space_during_copy(dest_dir, current_copied_size, total_size, source_dir, files_to_move):
    """在复制过程中动态检查空间，确保剩余空间始终大于待复制的数据量"""
    available_space = get_available_space(dest_dir)
    remaining_data_size = total_size - current_copied_size  # 剩余待复制的数据量
    
    if available_space < remaining_data_size:
        xbmc.log(f"[ERROR] 复制过程中空间不足 - 可用: {available_space/(1024*1024):.2f}MB, 剩余需复制: {remaining_data_size/(1024*1024):.2f}MB", xbmc.LOGERROR)
        return False, available_space, remaining_data_size
    else:
        xbmc.log(f"[DEBUG] 复制过程中空间充足 - 可用: {available_space/(1024*1024):.2f}MB, 剩余需复制: {remaining_data_size/(1024*1024):.2f}MB", xbmc.LOGDEBUG)
        return True, available_space, remaining_data_size


# ========== 带进度条的安全移动文件函数 ========== 
def safe_move_files(files_to_move, source_dir, dest_dir, operation_description):
    """安全移动文件，如果移动失败则清理不完整的文件，显示基于数据量的进度条，不再创建备份文件"""
    xbmc.log(f"[DEBUG] 开始安全移动文件操作: {operation_description}", xbmc.LOGDEBUG)
    xbmc.log(f"[DEBUG] 源目录: {source_dir}, 目标目录: {dest_dir}", xbmc.LOGDEBUG)
    xbmc.log(f"[DEBUG] 待移动文件列表: {files_to_move}", xbmc.LOGDEBUG)
    
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create("正在处理文件", f"正在{operation_description}...")
    
    temp_files = []
    total_files = len(files_to_move)
    processed_files = 0

    # 计算待移动文件的总大小
    total_size = get_total_size_of_files(files_to_move, source_dir)
    initial_available_space = get_available_space(dest_dir)
    xbmc.log(f"[DEBUG] 目标目录初始可用空间: {initial_available_space/(1024*1024):.2f}MB", xbmc.LOGDEBUG)
    xbmc.log(f"[DEBUG] 待移动文件总大小: {total_size/(1024*1024):.2f}MB", xbmc.LOGDEBUG)
    
    # 检查初始空间是否足够
    if total_size > initial_available_space:
        required_mb = total_size / (1024*1024)
        available_mb = initial_available_space / (1024*1024)
        xbmc.log(f"[ERROR] 存储空间不足 - 需要: {required_mb:.2f}MB, 可用: {available_mb:.2f}MB", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("存储空间不足", f"目标目录空间不足，需要 {required_mb:.2f}MB，但仅有 {available_mb:.2f}MB 可用。请释放空间后再试。")
        progress_dialog.close()
        return False

    try:
        # 直接移动文件，显示基于数据量的进度条
        xbmc.log("[DEBUG] 开始移动文件", xbmc.LOGDEBUG)
        current_copied_size = 0  # 记录当前已复制的文件大小
        
        for file_name in files_to_move:
            source_path = os.path.join(source_dir, file_name)
            dest_path = os.path.join(dest_dir, file_name)
            
            if os.path.exists(source_path):
                # 更新进度条 - 基于已复制的数据量
                progress_percent = min(int((current_copied_size / total_size) * 100), 100) if total_size > 0 else 0
                progress_dialog.update(progress_percent, f"正在移动文件 ({current_copied_size/(1024*1024):.2f}MB/{total_size/(1024*1024):.2f}MB) - {file_name}")
                xbmc.log(f"[DEBUG] 移动文件 {file_name}, 已复制: {current_copied_size/(1024*1024):.2f}MB, 总计: {total_size/(1024*1024):.2f}MB, 进度: {progress_percent}%", xbmc.LOGDEBUG)
                
                # 检查当前空间是否仍足够
                file_size = os.path.getsize(source_path)
                can_continue, available_space, remaining_size = check_space_during_copy(
                    dest_dir, current_copied_size, total_size, source_dir, files_to_move
                )
                
                if not can_continue:
                    # 空间不足，清理已移动的文件
                    xbmc.log("[DEBUG] 检测到移动过程中空间不足，开始清理已移动的文件", xbmc.LOGDEBUG)
                    for moved_file in temp_files:
                        if os.path.exists(moved_file):
                            os.remove(moved_file)
                            xbmc.log(f"[DEBUG] 已删除不完整文件: {moved_file}", xbmc.LOGDEBUG)
                    
                    progress_dialog.close()
                    xbmcgui.Dialog().ok("存储空间不足", f"移动文件 {file_name} 时磁盘空间不足，需要 {remaining_size/(1024*1024):.2f}MB，但仅剩 {available_space/(1024*1024):.2f}MB 可用。已清理不完整文件。")
                    return False
                
                try:
                    # 使用shutil.copy2然后os.remove来代替shutil.move，确保不传多余参数
                    shutil.copy2(source_path, dest_path)
                    os.remove(source_path)
                    temp_files.append(dest_path)
                    
                    # 更新当前已复制的大小
                    current_copied_size += file_size
                    xbmc.log(f"[DEBUG] 成功移动文件: {source_path} -> {dest_path}, 当前已复制: {current_copied_size/(1024*1024):.2f}MB", xbmc.LOGDEBUG)
                    
                    # 更新进度条 - 基于已复制的数据量
                    progress_percent = min(int((current_copied_size / total_size) * 100), 100) if total_size > 0 else 0
                    progress_dialog.update(progress_percent, f"正在移动文件 ({current_copied_size/(1024*1024):.2f}MB/{total_size/(1024*1024):.2f}MB) - {file_name}")
                    
                except OSError as e:
                    xbmc.log(f"[ERROR] 移动文件失败: {source_path} -> {dest_path}, 错误: {str(e)}", xbmc.LOGERROR)
                    if e.errno == 28:  # No space left on device
                        # 删除已移动的文件
                        xbmc.log("[DEBUG] 检测到磁盘空间不足，开始清理已移动的文件", xbmc.LOGDEBUG)
                        for moved_file in temp_files:
                            if os.path.exists(moved_file):
                                os.remove(moved_file)
                                xbmc.log(f"[DEBUG] 已删除不完整文件: {moved_file}", xbmc.LOGDEBUG)
                        
                        progress_dialog.close()
                        xbmcgui.Dialog().ok("存储空间不足", f"移动文件 {file_name} 时磁盘空间不足，请释放空间后再试。已清理不完整文件。")
                        return False
                    else:
                        # 删除已移动的文件
                        xbmc.log("[DEBUG] 发生其他错误，开始清理已移动的文件", xbmc.LOGDEBUG)
                        for moved_file in temp_files:
                            if os.path.exists(moved_file):
                                os.remove(moved_file)
                                xbmc.log(f"[DEBUG] 已删除不完整文件: {moved_file}", xbmc.LOGDEBUG)
                        
                        progress_dialog.close()
                        xbmcgui.Dialog().ok("移动文件失败", f"移动文件 {file_name} 时发生错误：{str(e)}")
                        return False

        progress_dialog.close()
        xbmc.log("[DEBUG] 安全移动文件操作完成", xbmc.LOGDEBUG)
        return True

    except Exception as e:
        xbmc.log(f"[ERROR] 移动文件过程中发生异常: {str(e)}", xbmc.LOGERROR)
        # 发生其他异常时清理临时文件
        xbmc.log("[DEBUG] 发生异常，开始清理临时文件", xbmc.LOGDEBUG)
        for moved_file in temp_files:
            if os.path.exists(moved_file):
                os.remove(moved_file)
                xbmc.log(f"[DEBUG] 已删除临时文件: {moved_file}", xbmc.LOGDEBUG)
                
        progress_dialog.close()
        xbmcgui.Dialog().ok("操作失败", f"移动文件时发生错误：{str(e)}")
        return False


def rollback_move_operation(moved_files, source_dir, original_files):
    """回滚移动操作，恢复到原始状态"""
    xbmc.log("[DEBUG] 开始执行回滚操作", xbmc.LOGDEBUG)
    for file_path in moved_files:
        if os.path.exists(file_path):
            # 移回原位置 - 使用copy2+remove代替move
            file_name = os.path.basename(file_path)
            original_source_path = os.path.join(source_dir, file_name)
            shutil.copy2(file_path, original_source_path)
            os.remove(file_path)
            xbmc.log(f"[DEBUG] 回滚文件: {file_path} -> {original_source_path}", xbmc.LOGDEBUG)
    
    # 恢复备份文件到原位置（如果移动失败）
    for file_name, backup_path in original_files.items():
        if os.path.exists(backup_path):
            original_path = os.path.join(source_dir, file_name)
            shutil.copy2(backup_path, original_path)
            os.remove(backup_path)
            xbmc.log(f"[DEBUG] 恢复备份文件: {backup_path} -> {original_path}", xbmc.LOGDEBUG)


# ========== CE双系统与单系统转换逻辑 ========== 
def ce_dual_single_conversion():
    """处理CE双系统与单系统之间的转换"""
    xbmc.log("[DEBUG] 开始执行 CE 双系统与单系统转换", xbmc.LOGDEBUG)
    if not set_flash_writable():
        xbmc.log("[ERROR] 无法将 /flash 挂载为可写，终止转换", xbmc.LOGERROR)
        return

    # 检查/flash文件夹内是否至少包含文件名为KERNELcpm.img、KERNELce.img、SYSTEMcpm、SYSTEMce中的一个文件
    flash_files = []
    xbmc.log("[DEBUG] 开始检测 /flash 目录中的双系统文件", xbmc.LOGDEBUG)
    for file_name in ["KERNELcpm.img", "KERNELce.img", "SYSTEMcpm", "SYSTEMce"]:
        if file_exists(file_name):
            flash_files.append(file_name)
            xbmc.log(f"[DEBUG] 在 /flash 中找到双系统文件: {file_name}", xbmc.LOGDEBUG)

    # 情况1：如果包含，则弹出对话窗口询问是否转换为单系统
    if flash_files:
        xbmc.log("[DEBUG] 检测到双系统文件，询问是否转换为单系统", xbmc.LOGDEBUG)
        # 当前为CE双系统，询问是否转换为单系统
        dialog_result = xbmcgui.Dialog().yesno(
            "CE双系统转换",
            "当前为CE双系统，是否转换为CE单系统？(释放系统分区空间，方便自行升级系统)"
        )
        if not dialog_result:
            # 用户选择否，返回上一个窗口
            xbmc.log("[DEBUG] 用户选择不转换为单系统，返回主菜单", xbmc.LOGDEBUG)
            show_switch_select_dialog()
            return

        xbmc.log("[DEBUG] 用户同意转换为单系统，开始移动文件", xbmc.LOGDEBUG)
        # 用户选择是，将存在的文件移动到/storage/.resource文件夹下
        success = safe_move_files(flash_files, FLASH_DIR, RESOURCE_DIR, "从闪存移动到资源目录")
        if success:
            # 弹出确认窗口
            xbmc.log("[DEBUG] 单系统转换完成", xbmc.LOGDEBUG)
            xbmcgui.Dialog().ok("转换完成", "已将内置的CE双系统转为CE单系统！")
        return

    else:
        xbmc.log("[DEBUG] 未检测到双系统文件，询问是否转换为双系统", xbmc.LOGDEBUG)
        # 情况2：如果不包含，则弹出对话窗口询问是否转换为双系统
        dialog_result = xbmcgui.Dialog().yesno(
            "CE单系统转换",
            "当前为CE单系统，是否转换为CE双系统？(占用系统分区空间，自行升级系统有可能失败！)"
        )
        if not dialog_result:
            # 用户选择否，返回上一个窗口
            xbmc.log("[DEBUG] 用户选择不转换为双系统，返回主菜单", xbmc.LOGDEBUG)
            show_switch_select_dialog()
            return

        # 检查/storage/.resource文件夹下是否有KERNELcpm.img和SYSTEMcpm两个文件或KERNELce.img、SYSTEMce两个文件
        resource_files = os.listdir(RESOURCE_DIR) if os.path.exists(RESOURCE_DIR) else []
        xbmc.log(f"[DEBUG] /storage/.resource 目录文件: {resource_files}", xbmc.LOGDEBUG)
        has_cpm_pair = "KERNELcpm.img" in resource_files and "SYSTEMcpm" in resource_files
        has_ce_pair = "KERNELce.img" in resource_files and "SYSTEMce" in resource_files

        # 如果既没有KERNELcpm.img和SYSTEMcpm两个文件，也没有KERNELce.img、SYSTEMce两个文件，
        # 又或者存在KERNELcpm.img、KERNELce.img、SYSTEMcpm、SYSTEMce四个文件中的三个文件
        if not has_cpm_pair and not has_ce_pair:
            xbmc.log("[ERROR] 双系统文件不完整，无法转换", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("转换失败", "双系统文件损坏，无法转换为CE双系统！")
            return

        # 将/storage/.resource文件夹下的成对文件移动到/flash文件夹下
        files_to_move = []
        if has_cpm_pair:
            files_to_move = ["KERNELcpm.img", "SYSTEMcpm"]
            xbmc.log("[DEBUG] 检测到 CPM 双系统文件对", xbmc.LOGDEBUG)
        elif has_ce_pair:
            files_to_move = ["KERNELce.img", "SYSTEMce"]
            xbmc.log("[DEBUG] 检测到 CE 双系统文件对", xbmc.LOGDEBUG)

        xbmc.log(f"[DEBUG] 开始将双系统文件对移动到 /flash: {files_to_move}", xbmc.LOGDEBUG)
        success = safe_move_files(files_to_move, RESOURCE_DIR, FLASH_DIR, "从资源目录移动到闪存")
        if success:
            # 弹出确认窗口
            xbmc.log("[DEBUG] 双系统转换完成", xbmc.LOGDEBUG)
            xbmcgui.Dialog().ok("转换完成", "已将内置的CE单系统转为CE双系统！")


# ========== 带进度条的文件复制函数 ========== 
def copy_file_with_progress(source_path, dest_path, file_size, progress_dialog, current_copied_size, total_size, file_name):
    """带进度条的文件复制函数"""
    try:
        # 打开源文件和目标文件
        with open(source_path, 'rb') as src_file, open(dest_path, 'wb') as dst_file:
            chunk_size = 8192  # 每次读取8KB
            copied = 0
            
            while True:
                chunk = src_file.read(chunk_size)
                if not chunk:
                    break
                dst_file.write(chunk)
                copied += len(chunk)
                
                # 更新进度
                overall_copied = current_copied_size + copied
                progress_percent = min(int((overall_copied / total_size) * 100), 100)
                progress_dialog.update(progress_percent, f"正在复制文件 ({overall_copied/(1024*1024):.2f}MB/{total_size/(1024*1024):.2f}MB) - {file_name}")
                
                # 日志记录
                xbmc.log(f"[DEBUG] 复制文件 {file_name}, 当前块: {copied/(1024*1024):.2f}MB, 总计: {overall_copied/(1024*1024):.2f}MB, 进度: {progress_percent}%", xbmc.LOGDEBUG)
        
        return True
    except Exception as e:
        xbmc.log(f"[ERROR] 复制文件失败: {source_path} -> {dest_path}, 错误: {str(e)}", xbmc.LOGERROR)
        return False


# ========== 网络路径检测函数 ========== 
def is_network_path(path):
    """检测路径是否为网络路径"""
    parsed = urllib.parse.urlparse(path)
    network_schemes = ['http', 'https', 'ftp', 'ftps', 'dav', 'davs', 'smb', 'nfs', 'afp']
    return parsed.scheme.lower() in network_schemes


# ========== 网络路径文件大小获取函数 ========== 
def get_network_file_size_via_xbmcvfs(network_path):
    """通过xbmcvfs获取网络文件大小"""
    try:
        # 尝试使用xbmcvfs.Stat获取文件信息
        stat_result = xbmcvfs.Stat(network_path)
        file_size = stat_result.st_size()
        xbmc.log(f"[DEBUG] 通过xbmcvfs获取网络文件大小: {network_path}, 大小: {file_size}", xbmc.LOGDEBUG)
        return file_size
    except:
        # 如果Stat失败，尝试通过复制到临时位置再获取大小
        try:
            import tempfile
            temp_dir = "/tmp"
            temp_filename = os.path.join(temp_dir, "temp_check_size")
            
            # 尝试复制一小部分文件来检查大小
            if xbmcvfs.copy(network_path, temp_filename):
                size = os.path.getsize(temp_filename)
                # 删除临时文件
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                return size
        except:
            pass
        return None


# ========== 监控更新目录大小的线程 ========== 
class UpdateDirSizeMonitor:
    def __init__(self, update_dir, base_size, progress_bar):
        self.update_dir = update_dir
        self.base_size = base_size
        self.progress_bar = progress_bar
        self.is_running = True
        self.thread = None

    def start_monitoring(self):
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()

    def _monitor_loop(self):
        while self.is_running:
            try:
                # 计算/storage/.update目录下的文件大小
                update_dir_size = 0
                if os.path.exists(self.update_dir):
                    for dirpath, dirnames, filenames in os.walk(self.update_dir):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            if os.path.isfile(filepath):  # 确保是文件而不是目录
                                update_dir_size += os.path.getsize(filepath)
                
                # 计算进度百分比 (以base_size为基准)
                progress_percent = min(int((update_dir_size / self.base_size) * 100), 100)
                
                # 更新进度条
                self.progress_bar.update(progress_percent, f"下载进度: {progress_percent}%", 
                                         f"已占用空间: {update_dir_size/(1024*1024):.2f}MB / {(self.base_size)/(1024*1024):.2f}MB")
                
                xbmc.log(f"[DEBUG] 实时监控 - 已占用空间: {update_dir_size/(1024*1024):.2f}MB, 进度: {progress_percent}%", xbmc.LOGDEBUG)
                
                # 每秒检测一次
                time.sleep(1)
                
            except Exception as e:
                xbmc.log(f"[ERROR] 监控更新目录大小时发生异常: {str(e)}", xbmc.LOGERROR)
                break

    def stop_monitoring(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)  # 最多等待2秒


# ========== 网络路径文件复制函数（使用ExtendedProgressBar）========== 
def copy_network_file_with_extended_progress(network_path, local_path, file_name):
    """从网络路径复制文件到本地，使用ExtendedProgressBar显示进度"""
    try:
        # 创建ExtendedProgressBar窗口
        progress_bar = xbmcgui.DialogProgressBG()
        progress_bar.create("正在下载文件", f"正在下载: {file_name}")
        
        # 创建并启动监控线程
        BASE_SIZE = 265 * 1024 * 1024  # 265MB in bytes
        monitor = UpdateDirSizeMonitor(UPDATE_DIR, BASE_SIZE, progress_bar)
        monitor.start_monitoring()
        
        # 尝试使用xbmcvfs.copy进行网络文件复制
        xbmc.log(f"[DEBUG] 尝试使用xbmcvfs.copy复制网络文件: {network_path} -> {local_path}", xbmc.LOGDEBUG)
        if xbmcvfs.copy(network_path, local_path):
            xbmc.log(f"[DEBUG] 成功通过xbmcvfs复制网络文件: {network_path} -> {local_path}", xbmc.LOGDEBUG)
            # 等待几秒让进度更新
            time.sleep(2)
            progress_bar.close()
            monitor.stop_monitoring()
            return True
        else:
            xbmc.log(f"[WARNING] xbmcvfs.copy复制网络文件失败，尝试备用方法", xbmc.LOGDEBUG)
            
            # 如果xbmcvfs.copy失败，尝试其他方法
            # 有些网络路径可能需要先挂载或使用特殊处理
            xbmc.log(f"[DEBUG] 使用urllib从网络路径下载文件: {network_path}", xbmc.LOGDEBUG)
            
            # 如果是HTTP/HTTPS，尝试使用urllib
            parsed = urllib.parse.urlparse(network_path)
            if parsed.scheme in ['http', 'https']:
                import urllib.request
                
                def reporthook(blocknum, blocksize, totalsize):
                    downloaded = blocknum * blocksize
                    if totalsize > 0:
                        percent = min(int(downloaded * 100 / totalsize), 100)
                        # 不直接更新进度条，而是依赖监控线程
                        xbmc.log(f"[DEBUG] 下载进度: {percent}% ({downloaded/(1024*1024):.2f}MB / {totalsize/(1024*1024):.2f}MB)", xbmc.LOGDEBUG)
                
                urllib.request.urlretrieve(network_path, local_path, reporthook)
                xbmc.log(f"[DEBUG] 通过urllib下载HTTP/HTTPS文件成功: {network_path} -> {local_path}", xbmc.LOGDEBUG)
                # 等待几秒让进度更新
                time.sleep(2)
                progress_bar.close()
                monitor.stop_monitoring()
                return True
            else:
                # 对于其他协议如dav/smb/nfs，尝试通过shell命令
                xbmc.log(f"[DEBUG] 尝试使用shell命令复制网络文件: {network_path}", xbmc.LOGDEBUG)
                cmd = f"cp '{network_path}' '{local_path}'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    xbmc.log(f"[DEBUG] 通过shell命令复制网络文件成功: {network_path} -> {local_path}", xbmc.LOGDEBUG)
                    # 等待几秒让进度更新
                    time.sleep(2)
                    progress_bar.close()
                    monitor.stop_monitoring()
                    return True
                else:
                    xbmc.log(f"[ERROR] 通过shell命令复制网络文件失败: {result.stderr}", xbmc.LOGDEBUG)
                    progress_bar.close()
                    monitor.stop_monitoring()
                    return False
                    
    except Exception as e:
        xbmc.log(f"[ERROR] 复制网络文件时发生异常: {str(e)}", xbmc.LOGERROR)
        return False


# ========== 处理单个文件选择的通用逻辑 ========== 
def process_selected_file(file_path):
    """处理用户选择的文件路径，执行复制和重启逻辑"""
    if not file_path:
        # 用户取消选择，返回主选择窗
        xbmc.log("[DEBUG] 用户取消选择，返回主菜单", xbmc.LOGDEBUG)
        show_switch_select_dialog()
        return

    # 检测是否为网络路径
    if is_network_path(file_path):
        xbmc.log(f"[DEBUG] 检测到网络路径: {file_path}", xbmc.LOGDEBUG)
        
        # 提示用户网络文件需要先下载到本地
        if not xbmcgui.Dialog().yesno(
            "网络文件确认", 
            f"检测到网络文件路径，需要先下载到本地再处理。\n\n文件: {os.path.basename(file_path)}\n\n是否继续？"
        ):
            show_switch_select_dialog()
            return
        
        # 获取网络文件大小 - 尝试多种方法
        file_size = get_network_file_size_via_xbmcvfs(file_path)
        if file_size is None:
            xbmc.log(f"[WARNING] 无法通过xbmcvfs获取网络文件大小，尝试直接复制", xbmc.LOGDEBUG)
            # 如果无法获取文件大小，我们仍然可以尝试复制，只是无法检查空间
            xbmc.log(f"[DEBUG] 继续处理，但无法预先检查空间", xbmc.LOGDEBUG)
        else:
            # 检查目标目录空间
            available_space = get_available_space(UPDATE_DIR)
            xbmc.log(f"[DEBUG] 目标目录可用空间: {available_space} 字节 ({available_space/(1024*1024):.2f}MB)", xbmc.LOGDEBUG)

            if file_size > available_space:
                required_mb = file_size / (1024*1024)
                available_mb = available_space / (1024*1024)
                xbmc.log(f"[ERROR] 目标目录空间不足 - 需要: {required_mb:.2f}MB, 可用: {available_mb:.2f}MB", xbmc.LOGERROR)
                xbmcgui.Dialog().ok("存储空间不足", f"目标目录空间不足，需要 {required_mb:.2f}MB，但仅有 {available_mb:.2f}MB 可用。请释放空间后再试。")
                show_switch_select_dialog()
                return

        # 获取文件名
        file_name = os.path.basename(file_path)
        xbmc.log(f"[DEBUG] 网络文件名: {file_name}", xbmc.LOGDEBUG)

        # 弹出确认窗口询问是否切换到此内核
        confirm = xbmcgui.Dialog().yesno("确认切换", f"您选择了 {file_name}，是否切换到此内核？")
        xbmc.log(f"[DEBUG] 用户确认切换: {confirm}", xbmc.LOGDEBUG)

        if not confirm:
            # 用户选择"否"，返回初始选择窗
            xbmc.log("[DEBUG] 用户取消切换，返回主菜单", xbmc.LOGDEBUG)
            show_switch_select_dialog()
            return

        try:
            # 目标路径
            dest_path = os.path.join(UPDATE_DIR, file_name)
            xbmc.log(f"[DEBUG] 开始从网络复制文件: {file_path} -> {dest_path}", xbmc.LOGDEBUG)

            # 调用网络路径复制函数（使用ExtendedProgressBar和实时监控）
            success = copy_network_file_with_extended_progress(file_path, dest_path, file_name)

            if success:
                xbmc.log(f"[DEBUG] 成功复制网络文件到: {dest_path}", xbmc.LOGDEBUG)

                # --- 优化逻辑开始：在重启确认前清空 langversion ---
                xbmc.log("[DEBUG] 执行 Skin.SetString(langversion,\"\") 以重置皮肤语言版本状态", xbmc.LOGDEBUG)
                xbmc.executebuiltin('Skin.SetString(langversion,"")')
                # --- 优化逻辑结束 ---

                # 复制完成后弹出确认窗，询问用户是否重启
                reboot_confirm = xbmcgui.Dialog().yesno("重启确认", "内核文件已复制完成，是否现在重启系统？")
                xbmc.log(f"[DEBUG] 用户确认重启: {reboot_confirm}", xbmc.LOGDEBUG)

                if reboot_confirm:
                    # 用户选择"是"，执行重启指令
                    xbmc.log("[DEBUG] 用户选择重启，执行重启指令", xbmc.LOGDEBUG)
                    xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,noask)')
                else:
                    # 用户选择"否"，返回初始选择窗
                    xbmc.log("[DEBUG] 用户选择不重启，返回主菜单", xbmc.LOGDEBUG)
                    show_switch_select_dialog()
            else:
                # 复制失败
                xbmc.log(f"[ERROR] 复制网络文件失败: {file_path} -> {dest_path}", xbmc.LOGERROR)
                xbmcgui.Dialog().ok("错误", "复制网络文件失败，请检查网络连接和文件路径！")
                show_switch_select_dialog()

        except Exception as e:
            xbmc.log(f"[ERROR] 复制网络文件失败: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", f"复制网络文件失败: {str(e)}")
            show_switch_select_dialog()
    else:
        # 本地路径处理逻辑（保持原有功能不变）
        # 验证文件扩展名
        if not file_path.lower().endswith('.tar'):
            xbmc.log(f"[ERROR] 选择的文件不是 .tar 格式: {file_path}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "请选择 .tar 格式的内核文件！")
            show_switch_select_dialog()
            return

        # 获取文件名
        file_name = os.path.basename(file_path)
        xbmc.log(f"[DEBUG] 选择的文件名: {file_name}", xbmc.LOGDEBUG)

        # 弹出确认窗口询问是否切换到此内核
        confirm = xbmcgui.Dialog().yesno("确认切换", f"您选择了 {file_name}，是否切换到此内核？")
        xbmc.log(f"[DEBUG] 用户确认切换: {confirm}", xbmc.LOGDEBUG)

        if not confirm:
            # 用户选择"否"，返回初始选择窗
            xbmc.log("[DEBUG] 用户取消切换，返回主菜单", xbmc.LOGDEBUG)
            show_switch_select_dialog()
            return

        try:
            # 获取源文件大小（使用xbmcvfs以支持更多路径类型）
            if xbmcvfs.exists(file_path):
                stat = xbmcvfs.Stat(file_path)
                file_size = stat.st_size()
            else:
                file_size = os.path.getsize(file_path)
            xbmc.log(f"[DEBUG] 源文件大小: {file_size} 字节 ({file_size/(1024*1024):.2f}MB)", xbmc.LOGDEBUG)

            # 检查目标目录空间
            available_space = get_available_space(UPDATE_DIR)
            xbmc.log(f"[DEBUG] 目标目录可用空间: {available_space} 字节 ({available_space/(1024*1024):.2f}MB)", xbmc.LOGDEBUG)

            if file_size > available_space:
                required_mb = file_size / (1024*1024)
                available_mb = available_space / (1024*1024)
                xbmc.log(f"[ERROR] 目标目录空间不足 - 需要: {required_mb:.2f}MB, 可用: {available_mb:.2f}MB", xbmc.LOGERROR)
                xbmcgui.Dialog().ok("存储空间不足", f"目标目录空间不足，需要 {required_mb:.2f}MB，但仅有 {available_mb:.2f}MB 可用。请释放空间后再试。")
                show_switch_select_dialog()
                return

            # 创建进度条对话框
            progress_dialog = xbmcgui.DialogProgress()
            progress_dialog.create("正在复制文件", f"正在复制: {file_name}...")
            xbmc.log(f"[DEBUG] 创建进度条对话框", xbmc.LOGDEBUG)

            # 目标路径
            dest_path = os.path.join(UPDATE_DIR, file_name)
            xbmc.log(f"[DEBUG] 开始复制文件: {file_path} -> {dest_path}", xbmc.LOGDEBUG)

            # 调用带进度条的复制函数
            success = copy_file_with_progress(file_path, dest_path, file_size, progress_dialog, 0, file_size, file_name)
            progress_dialog.close()

            if success:
                xbmc.log(f"[DEBUG] 成功复制文件到: {dest_path}", xbmc.LOGDEBUG)

                # --- 优化逻辑开始：在重启确认前清空 langversion ---
                xbmc.log("[DEBUG] 执行 Skin.SetString(langversion,\"\") 以重置皮肤语言版本状态", xbmc.LOGDEBUG)
                xbmc.executebuiltin('Skin.SetString(langversion,"")')
                # --- 优化逻辑结束 ---

                # 复制完成后弹出确认窗，询问用户是否重启
                reboot_confirm = xbmcgui.Dialog().yesno("重启确认", "内核文件已复制完成，是否现在重启系统？")
                xbmc.log(f"[DEBUG] 用户确认重启: {reboot_confirm}", xbmc.LOGDEBUG)

                if reboot_confirm:
                    # 用户选择"是"，执行重启指令
                    xbmc.log("[DEBUG] 用户选择重启，执行重启指令", xbmc.LOGDEBUG)
                    xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,noask)')
                else:
                    # 用户选择"否"，返回初始选择窗
                    xbmc.log("[DEBUG] 用户选择不重启，返回主菜单", xbmc.LOGDEBUG)
                    show_switch_select_dialog()
            else:
                # 复制失败
                xbmc.log(f"[ERROR] 复制文件失败: {file_path} -> {dest_path}", xbmc.LOGERROR)
                xbmcgui.Dialog().ok("错误", "复制文件失败，请检查文件和存储空间！")
                show_switch_select_dialog()

        except Exception as e:
            xbmc.log(f"[ERROR] 复制文件失败: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", f"复制文件失败: {str(e)}")
            show_switch_select_dialog()


# ========== R10/F10 特殊处理逻辑 (已优化 dovi5.ko 查找逻辑) ==========
def handle_dovi5_kernel(file_path, default_path=None):
    """
    处理包含 R10 或 F10 的内核文件，确保 dovi5.ko 存在并复制到 /flash
    :param file_path: .tar 文件的路径
    :param default_path: 文件选择器的默认打开路径
    """
    xbmc.log(f"[DEBUG] 检测到 R10/F10 内核，开始处理 dovi5.ko: {file_path}", xbmc.LOGDEBUG)
    
    # 1. 确保 /flash 可写
    if not set_flash_writable():
        xbmc.log("[ERROR] 无法挂载 /flash 为可写，终止 dovi5.ko 处理", xbmc.LOGERROR)
        return False

    flash_dovi5_dst = os.path.join(FLASH_DIR, "dovi5.ko")
    storage_dovi5_path = "/storage/dovi5.ko"
    resource_dovi5_path = os.path.join(RESOURCE_DIR, "dovi5.ko")

    # 新增优化逻辑：优先检查系统目录中是否已存在 dovi5.ko
    if os.path.exists(flash_dovi5_dst):
        xbmc.log(f"[DEBUG] 检测到 /flash 下已存在 dovi5.ko，跳过寻找和复制逻辑", xbmc.LOGDEBUG)
        return True
        
    if os.path.exists(storage_dovi5_path):
        xbmc.log(f"[DEBUG] 检测到 /storage 下已存在 dovi5.ko，跳过源目录寻找，直接复制到 /flash", xbmc.LOGDEBUG)
        try:
            shutil.copy2(storage_dovi5_path, flash_dovi5_dst)
            xbmc.log("[DEBUG] 成功从 /storage 复制 dovi5.ko 到 /flash", xbmc.LOGDEBUG)
            xbmcgui.Dialog().ok("成功", "dovi5.ko 已从 /storage 复制到 /flash 目录。")
            return True
        except Exception as e:
            xbmc.log(f"[ERROR] 从 /storage 复制 dovi5.ko 失败: {str(e)}，将继续尝试从源目录寻找", xbmc.LOGERROR)

    if os.path.exists(resource_dovi5_path):
        xbmc.log(f"[DEBUG] 检测到 {RESOURCE_DIR} 下已存在 dovi5.ko，跳过源目录寻找，直接复制到 /flash", xbmc.LOGDEBUG)
        try:
            shutil.copy2(resource_dovi5_path, flash_dovi5_dst)
            xbmc.log("[DEBUG] 成功从资源目录复制 dovi5.ko 到 /flash", xbmc.LOGDEBUG)
            xbmcgui.Dialog().ok("成功", "dovi5.ko 已从资源目录复制到 /flash 目录。")
            return True
        except Exception as e:
            xbmc.log(f"[ERROR] 从资源目录复制 dovi5.ko 失败: {str(e)}，将继续尝试从源目录寻找", xbmc.LOGERROR)

    # 2. 获取源文件所在目录 (原逻辑)
    source_dir = os.path.dirname(file_path)
    dovi5_src = os.path.join(source_dir, "dovi5.ko")
    
    # 检查源文件是否存在 (注意：xbmcvfs.exists 支持网络路径)
    dovi5_found = xbmcvfs.exists(dovi5_src)
    
    if not dovi5_found:
        # 情况1：未找到该文件
        xbmc.log(f"[DEBUG] 未在源目录找到 dovi5.ko: {dovi5_src}", xbmc.LOGDEBUG)
        
        # 弹出确认窗口
        confirm = xbmcgui.Dialog().yesno(
            "缺少驱动文件",
            "升级R10/F10内核需要“dovi5.ko”文件，但未在当前文件夹找到。\n\n请手动选择该文件。"
        )
        
        if not confirm:
            xbmc.log("[DEBUG] 用户取消手动选择 dovi5.ko", xbmc.LOGDEBUG)
            return False
            
        # 弹出文件选择窗口，并设置默认路径为 .tar 文件所在目录
        init_path = default_path if default_path else source_dir
        
        selected_ko = xbmcgui.Dialog().browseSingle(
            type=1, 
            heading="请选择 dovi5.ko 文件", 
            shares="", 
            mask=".ko",
            defaultt=init_path
        )
        
        if not selected_ko:
            xbmc.log("[DEBUG] 用户未选择 dovi5.ko 文件", xbmc.LOGDEBUG)
            return False
            
        dovi5_src = selected_ko
        xbmc.log(f"[DEBUG] 用户手动选择了 dovi5.ko: {dovi5_src}", xbmc.LOGDEBUG)
    else:
        # 情况2：找到了该文件
        xbmc.log(f"[DEBUG] 在源目录找到 dovi5.ko: {dovi5_src}", xbmc.LOGDEBUG)

    # 3. 复制文件到 /flash (原逻辑)
    try:
        xbmc.log(f"[DEBUG] 开始复制 dovi5.ko: {dovi5_src} -> {flash_dovi5_dst}", xbmc.LOGDEBUG)
        
        if is_network_path(dovi5_src):
            xbmc.log("[DEBUG] 检测到网络路径，使用 xbmcvfs.copy 进行复制", xbmc.LOGDEBUG)
            if not xbmcvfs.copy(dovi5_src, flash_dovi5_dst):
                raise Exception("xbmcvfs.copy 返回失败")
        else:
            xbmc.log("[DEBUG] 检测到本地路径，使用 shutil.copy2 进行复制", xbmc.LOGDEBUG)
            shutil.copy2(dovi5_src, flash_dovi5_dst)
            
        xbmc.log("[DEBUG] dovi5.ko 复制成功", xbmc.LOGDEBUG)
        xbmcgui.Dialog().ok("成功", "dovi5.ko 已成功复制到 /flash 目录。")
        return True
    except Exception as e:
        xbmc.log(f"[ERROR] 复制 dovi5.ko 失败: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"复制 dovi5.ko 失败:\n{str(e)}")
        return False


# ========== 手动选择.tar文件切换内核功能 ========== 
def manual_tar_selection():
    """手动选择.tar文件切换内核功能（优化版，支持网络路径，带复制进度条，支持R10/F10/0905特殊处理）"""
    xbmc.log("[DEBUG] 开始手动选择.tar文件切换内核", xbmc.LOGDEBUG)
    
    # 确保更新目录存在
    os.makedirs(UPDATE_DIR, exist_ok=True)
    xbmc.log(f"[DEBUG] 确保更新目录存在: {UPDATE_DIR}", xbmc.LOGDEBUG)
    
    # 第一步：选择来源类型
    source_options = [
        "选择挂载网盘中的.tar文件",
        "选择本地文件夹或局域网中的.tar文件"
    ]
    
    source_idx = xbmcgui.Dialog().select("请选择文件来源", source_options)
    xbmc.log(f"[DEBUG] 用户选择来源索引: {source_idx}", xbmc.LOGDEBUG)
    
    if source_idx == -1:
        # 用户取消，返回主菜单
        show_switch_select_dialog()
        return
    
    file_path = ""
    source_dir_for_dovi5 = "" # 用于记录源目录，供 dovi5 选择器使用
    
    if source_idx == 0:
        # 选择挂载网盘 (shares="files")
        file_path = xbmcgui.Dialog().browseSingle(type=1, heading="请选择 .tar 格式的内核文件", shares="files", mask=".tar")
    elif source_idx == 1:
        # 选择本地或局域网 (shares="")
        file_path = xbmcgui.Dialog().browseSingle(type=1, heading="请选择 .tar 格式的内核文件", shares="", mask=".tar")
    
    if not file_path:
        show_switch_select_dialog()
        return

    # 记录源目录，以便在需要选择 dovi5.ko 时作为默认路径
    if not is_network_path(file_path):
        source_dir_for_dovi5 = os.path.dirname(file_path)

    file_name_lower = os.path.basename(file_path).lower()
    
    # 1. 检查是否需要检测系统分区空间 (包含 R10, F10, 0905)
    need_space_check = "r10" in file_name_lower or "f10" in file_name_lower or "0905" in file_name_lower
    
    if need_space_check:
        xbmc.log(f"[DEBUG] 检测到特殊内核标识 (R10/F10/0905): {file_name_lower}，开始检测 /flash 空间", xbmc.LOGDEBUG)
        
        # 检测 /flash 分区剩余空间
        flash_free_space = get_available_space(FLASH_DIR)
        min_required_space = 50 * 1024 * 1024  # 50MB
        
        if flash_free_space < min_required_space:
            xbmc.log(f"[DEBUG] /flash 剩余空间不足 50MB (当前: {flash_free_space/(1024*1024):.2f}MB)，弹出警告窗口", xbmc.LOGDEBUG)
            confirm_convert = xbmcgui.Dialog().yesno(
                "空间不足警告",
                "检测到你的系统分区剩余空间过小，请先转为单系统！\n选择“是”立即转换，选择“否”则忽略警告继续执行。"
            )
            
            if confirm_convert:
                xbmc.log("[DEBUG] 用户选择立即转换为单系统", xbmc.LOGDEBUG)
                # 执行“内置CE双系统与CE单系统互转”的逻辑
                ce_dual_single_conversion()
                # 执行完毕后，继续后续逻辑
                xbmc.log("[DEBUG] 单系统转换逻辑执行完毕，继续处理 .tar 文件", xbmc.LOGDEBUG)
            else:
                xbmc.log("[DEBUG] 用户选择忽略警告，继续执行", xbmc.LOGDEBUG)
        else:
            xbmc.log(f"[DEBUG] /flash 剩余空间充足 (当前: {flash_free_space/(1024*1024):.2f}MB)，无需转换", xbmc.LOGDEBUG)

    # 2. 检查文件名是否包含 R10 或 F10 (不区分大小写，用于 dovi5.ko 处理，保持原逻辑)
    is_special_kernel = "r10" in file_name_lower or "f10" in file_name_lower

    if is_special_kernel:
        xbmc.log(f"[DEBUG] 检测到特殊内核标识 (R10/F10): {file_name_lower}", xbmc.LOGDEBUG)
        # 处理 dovi5.ko，传入源目录作为默认路径
        success = handle_dovi5_kernel(file_path, default_path=source_dir_for_dovi5)
        if not success:
            # 如果 dovi5.ko 处理失败或用户取消，返回主菜单
            xbmc.log("[DEBUG] dovi5.ko 处理未完成，返回主菜单", xbmc.LOGDEBUG)
            show_switch_select_dialog()
            return
        # 如果成功，继续执行后续的 tar 文件处理逻辑
        xbmc.log("[DEBUG] dovi5.ko 处理成功，继续处理 .tar 文件", xbmc.LOGDEBUG)

    # 调用通用处理逻辑
    process_selected_file(file_path)


# ========== 主选择弹窗逻辑 ========== 
def show_switch_select_dialog():
    """内核切换主选择窗口，含6个选项"""
    xbmc.log("[DEBUG] 显示主选择对话框", xbmc.LOGDEBUG)
    dialog_title = "内核切换模式选择"
    select_options = [
        "内置CE双系统与CE单系统互转",
        "内置CPM版与原版(夜版)切换",
        "远程下载内核切换(下载时间较长)",
        "删除已下载的内核文件",
        "强制切换内核(忽略CPM和原版/夜版兼容问题)",
        "手动选择.tar文件切换内核"
    ]

    select_index = xbmcgui.Dialog().select(dialog_title, select_options)
    xbmc.log(f"[DEBUG] 用户选择索引: {select_index}", xbmc.LOGDEBUG)

    if select_index == 0:
        xbmc.log("[DEBUG] 用户选择 CE 双系统与单系统转换", xbmc.LOGDEBUG)
        ce_dual_single_conversion()  # 调用CE双系统与单系统转换逻辑
    elif select_index == 1:
        xbmc.log("[DEBUG] 用户选择 CPM 版与原版切换", xbmc.LOGDEBUG)
        xbmc.executebuiltin('RunScript(special://skin/scripts/cetranscpm.py,inside)')
    elif select_index == 2:
        xbmc.log("[DEBUG] 用户选择远程下载内核切换", xbmc.LOGDEBUG)
        xbmc.executebuiltin('RunScript(special://skin/scripts/kernelupdate.py)')
    elif select_index == 3:
        xbmc.log("[DEBUG] 用户选择删除已下载的内核文件", xbmc.LOGDEBUG)
        delete_kernel_files()  # 调用删除内核文件逻辑
    elif select_index == 4:
        xbmc.log("[DEBUG] 用户选择强制切换内核", xbmc.LOGDEBUG)
        # 处理强制切换内核选项：先弹风险确认窗
        confirm = xbmcgui.Dialog().yesno(
            "风险确认",
            "强制切换内核可能导致设置项错乱，是否确认执行？"
        )
        if confirm:
            xbmc.log("[DEBUG] 用户确认强制切换内核", xbmc.LOGDEBUG)
            # 执行带nocheck参数的kernelupdate.py
            xbmc.executebuiltin('RunScript(special://skin/scripts/kernelupdate.py,nocheck)')
        else:
            xbmc.log("[DEBUG] 用户取消强制切换内核，返回主菜单", xbmc.LOGDEBUG)
            # 用户取消：返回主选择窗
            show_switch_select_dialog()
    elif select_index == 5:
        xbmc.log("[DEBUG] 用户选择手动选择.tar文件切换内核", xbmc.LOGDEBUG)
        manual_tar_selection()  # 调用手动选择.tar文件功能
    # 取消选择（select_index=-1）则无操作，静默退出
    xbmc.log("[DEBUG] 主选择对话框操作结束", xbmc.LOGDEBUG)


if __name__ == "__main__":
    xbmc.log("[DEBUG] 脚本启动，参数: " + str(sys.argv), xbmc.LOGDEBUG)
    # 完整参数优先级：select > inside > 无参静默退出
    if len(sys.argv) >= 2:
        if sys.argv[1] == "select":
            xbmc.log("[DEBUG] 执行主选择菜单", xbmc.LOGDEBUG)
            show_switch_select_dialog()
        elif sys.argv[1] == "inside":
            xbmc.log("[DEBUG] 执行内核切换操作", xbmc.LOGDEBUG)
            main()