import xbmc
import xbmcgui
import os
import shutil
import time
import re

# 定义文件路径常量
SYS_DISP_CAP_PATH = "/sys/class/amhdmitx/amhdmitx0/disp_cap"
USER_DISP_CAP_PATH = "/storage/.kodi/userdata/disp_cap"

def read_file_content(filepath):
    """读取文件内容，如果文件不存在或读取失败则返回 None"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception as e:
        xbmc.log(f"[HandonScript] Error reading {filepath}: {str(e)}", xbmc.LOGERROR)
    return None

def get_screen_height():
    """获取当前屏幕分辨率的高度值"""
    try:
        res_str = xbmc.getInfoLabel("System.ScreenResolution")
        if not res_str:
            return 0
        # 匹配格式如 "1920x1080" 或 "1920x1080@60" 中的高度值
        match = re.search(r'x(\d+)', res_str)
        if match:
            return int(match.group(1))
    except Exception as e:
        xbmc.log(f"[HandonScript] Error parsing resolution: {str(e)}", xbmc.LOGERROR)
    return 0

def copy_disp_cap_file():
    """将系统 disp_cap 文件复制到 userdata 目录下"""
    try:
        # 确保目标目录存在
        os.makedirs(os.path.dirname(USER_DISP_CAP_PATH), exist_ok=True)
        shutil.copy2(SYS_DISP_CAP_PATH, USER_DISP_CAP_PATH)
        xbmc.log(f"[HandonScript] Successfully copied {SYS_DISP_CAP_PATH} to {USER_DISP_CAP_PATH}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[HandonScript] Failed to copy file: {str(e)}", xbmc.LOGERROR)

def show_reboot_prompt():
    """弹出重启确认窗口，并根据用户选择执行相应操作"""
    dialog = xbmcgui.Dialog()
    message = "检测到您的显示端握手信息发生变化，建议您重启！点击“是”立即重启，点击“否”忽略该提示信息。"
    
    # 弹出 yesno 对话框，返回 True 表示选择“是”，False 表示选择“否”
    user_choice = dialog.yesno("系统提示", message)
    
    if user_choice:
        xbmc.log("[HandonScript] User chose to reboot.", xbmc.LOGINFO)
        xbmc.executebuiltin("RunScript(special://skin/scripts/rebootoff.py,noask)")
    else:
        xbmc.log("[HandonScript] User chose to ignore.", xbmc.LOGINFO)

def main():
    xbmc.log("[HandonScript] Script started. Waiting for 40 seconds...", xbmc.LOGINFO)

    # --- 新增：等待40秒 ---
    wait_time = 40
    for i in range(wait_time, 0, -1):
        # 每10秒记录一次日志，避免日志刷屏，同时让用户知道脚本在运行
        if i % 10 == 0 or i == 1:
            xbmc.log(f"[HandonScript] Waiting... {i} seconds remaining.", xbmc.LOGDEBUG)
        time.sleep(1)
    xbmc.log("[HandonScript] Wait completed. Starting logic execution.", xbmc.LOGINFO)
    # ---------------------

    # 1. 轮询检查 /sys/class/amhdmitx/amhdmitx0/disp_cap 直到内容不为空
    sys_disp_content = ""
    while True:
        content = read_file_content(SYS_DISP_CAP_PATH)
        if content and len(content) > 0:
            sys_disp_content = content
            break
        xbmc.log("[HandonScript] Waiting for disp_cap to be non-empty...", xbmc.LOGDEBUG)
        time.sleep(1)

    # 2. 读取本地缓存文件内容
    user_disp_content = read_file_content(USER_DISP_CAP_PATH)

    # 3. 获取当前屏幕高度
    current_height = get_screen_height()
    xbmc.log(f"[HandonScript] Current Screen Height: {current_height}", xbmc.LOGINFO)
    height_str = str(current_height)

    # 4. 判断文件内容是否一致
    is_content_match = (user_disp_content is not None) and (sys_disp_content == user_disp_content)

    if is_content_match:
        # ================= 情况 1 =================
        xbmc.log("[HandonScript] Case 1: Files match.", xbmc.LOGINFO)
        
        if current_height <= 1080:
            xbmc.log("[HandonScript] Height <= 1080, closing script.", xbmc.LOGINFO)
            return
        
        # 高度 > 1080
        if height_str in sys_disp_content:
            xbmc.log("[HandonScript] Height found in cap, closing script.", xbmc.LOGINFO)
            return
        else:
            xbmc.log("[HandonScript] Height NOT found in cap, running resolution.py.", xbmc.LOGINFO)
            xbmc.executebuiltin("RunScript(special://skin/scripts/resolution.py)")
            return

    else:
        # ================= 情况 2 =================
        xbmc.log("[HandonScript] Case 2: Files mismatch or local file missing.", xbmc.LOGINFO)
        
        if current_height <= 1080:
            # 高度 <= 1080 的新增逻辑
            xbmc.log("[HandonScript] Height <= 1080, copying file and prompting reboot.", xbmc.LOGINFO)
            copy_disp_cap_file()
            show_reboot_prompt()
            return
        
        # 高度 > 1080
        if height_str in sys_disp_content:
            # ================= 情况 2.1 =================
            xbmc.log("[HandonScript] Case 2.1: Height > 1080 and found in cap.", xbmc.LOGINFO)
            copy_disp_cap_file()
            show_reboot_prompt()
            return
        else:
            # ================= 情况 2.2 =================
            xbmc.log("[HandonScript] Case 2.2: Height > 1080 and NOT found in cap.", xbmc.LOGINFO)
            
            # 执行 resolution.py
            xbmc.executebuiltin("RunScript(special://skin/scripts/resolution.py)")
            
            # 等待 resolution.py 执行完毕 
            # (注：Kodi 的 RunScript 为异步调用，此处使用 Monitor 等待 2 秒作为缓冲，确保分辨率切换完成)
            monitor = xbmc.Monitor()
            monitor.waitForAbort(2)
            
            # 复制文件并弹窗
            copy_disp_cap_file()
            show_reboot_prompt()
            return

if __name__ == "__main__":
    main()