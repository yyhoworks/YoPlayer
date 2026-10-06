# -*- coding: utf-8 -*-
"""
special://skin/scripts/restartkodi.py
Kodi重启脚本，实现安全的Kodi进程重启功能
"""

import os
import sys
import xbmc
import xbmcgui

def restart_kodi():
    """
    重启Kodi进程，采用安全的重启机制
    """
    # 检查平台兼容性
    if not xbmc.getCondVisibility("System.Platform.Linux") or xbmc.getCondVisibility("System.Platform.Android"):
        xbmcgui.Dialog().notification(
            "重启失败", 
            "当前系统不支持此操作", 
            xbmcgui.NOTIFICATION_ERROR, 
            3000
        )
        return

    # 记录日志
    xbmc.log("Kodi Restart Script: Executing system level Kodi restart (kill -TERM -> wait -> kill -KILL)", xbmc.LOGINFO)
    
    # 显示重启通知
    xbmcgui.Dialog().notification(
        "Kodi重启", 
        "正在发送重启指令...", 
        xbmcgui.NOTIFICATION_INFO, 
        1000
    )
    
    # 等待1秒让用户看到通知
    xbmc.sleep(1000)
    
    # 获取当前Kodi进程ID
    kodi_pid = os.getpid()
    
    # 构建重启脚本命令
    # 该脚本会先发送SIGTERM信号优雅关闭Kodi，若未成功则发送SIGKILL强制关闭
    kill_script = (
        f"kill -TERM {kodi_pid} 2>/dev/null; "
        f"for i in $(seq 1 10); do "
        f"  kill -0 {kodi_pid} 2>/dev/null || exit 0; "  # 检查进程是否存在，如果不存在则退出
        f"  sleep 1; "  # 等待1秒
        f"done; "
        f"kill -KILL {kodi_pid} 2>/dev/null"  # 如果进程仍然存在，发送SIGKILL强制终止
    )
    
    # 使用nohup确保脚本在Kodi退出后继续运行，完全脱离Kodi进程
    cmd = f"nohup sh -c '{kill_script}' >/dev/null 2>&1 &"
    
    # 执行重启命令
    xbmc.log(f"Kodi Restart Script: Executing command: {cmd}", xbmc.LOGINFO)
    os.system(cmd)
    
    # 通知用户重启已启动
    xbmc.log("Kodi Restart Script: Restart command executed successfully", xbmc.LOGINFO)

def main():
    """
    主函数 - 直接执行重启，无需用户确认
    """
    restart_kodi()

if __name__ == "__main__":
    main()