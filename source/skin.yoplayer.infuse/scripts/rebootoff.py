#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import time
import os
import xbmc
import xbmcgui

def reboot_system():
    """先同步数据再强制重启"""
    xbmc.log("同步数据并强制重启", xbmc.LOGINFO)
    try:
        subprocess.run(["sync"], timeout=2, check=True)
    except subprocess.TimeoutExpired:
        xbmc.log("数据同步同步超时，继续执行重启", xbmc.LOGWARNING)
    subprocess.run(["reboot", "-f"])

def poweroff_system():
    """
    完全按正常流程关机，显示输出延后1秒关闭，不强制终止任何插件。
    增加30秒超时监控，若未关机则执行强制断电逻辑。
    """
    xbmc.log("同步数据并执行KODI安全关机", xbmc.LOGINFO)
    
    # 1. 同步数据（限制2秒超时）
    try:
        subprocess.run(["sync"], timeout=2, check=True)
    except subprocess.TimeoutExpired:
        xbmc.log("数据同步超时，继续执行关机", xbmc.LOGWARNING)

    # 2. 显示通知（1.5秒）
    xbmcgui.Dialog().notification(
        "系统提示", 
        "正在关机...",
        xbmcgui.NOTIFICATION_INFO, 
        1500
    )

    # 3. 延后1秒关闭显示输出
    time.sleep(1)  # 延后1秒执行关闭显示
    try:
        display_path = "/sys/class/graphics/fb0/blank"
        if os.path.exists(display_path) and os.access(display_path, os.W_OK):
            with open(display_path, 'w') as f:
                f.write("1\n")
            xbmc.log(f"已通过 {display_path} 关闭视频输出", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"关闭视频输出失败: {str(e)}", xbmc.LOGERROR)

    # 4. 短暂等待后执行正常关机
    time.sleep(0.2)
    xbmc.log("发送 Powerdown() 指令", xbmc.LOGINFO)
    xbmc.executebuiltin("Powerdown()")  # 完全依赖KODI正常关机流程

    # 5. 【新增】超时监控与强制关机逻辑
    xbmc.log("开始监控关机状态，超时阈值: 30秒", xbmc.LOGINFO)
    
    timeout_seconds = 30
    check_interval = 1  # 每秒检查一次
    
    for i in range(timeout_seconds):
        xbmc.sleep(check_interval * 1000)  # xbmc.sleep 单位是毫秒
        # 注意：一旦 Powerdown() 成功执行，Kodi 进程通常会终止，脚本也会随之停止。
        # 如果脚本还能执行到这里，说明 Kodi 可能卡住或未能完全断电。
        
    # 如果循环结束仍未退出，执行强制关机
    xbmc.log("检测到关机超时 (30s)，执行强制关机逻辑", xbmc.LOGWARNING)
    
    # 再次同步数据，确保强制关机前的数据安全
    try:
        subprocess.run(["sync"], timeout=2, check=True)
    except:
        pass

    nandscript = '/usr/sbin/poweroff'
    if os.path.exists(nandscript):
        xbmc.executebuiltin('Notification(正在等待关机)')
        try:
            subprocess.call(nandscript)
        except Exception as e:
            xbmc.log(f"执行 {nandscript} 失败: {e}", xbmc.LOGERROR)
            
        xbmc.sleep(300)  # 等待300ms
        
        try:
            subprocess.call(['poweroff', '-f'])
        except Exception as e:
            xbmc.log(f"执行 poweroff -f 失败: {e}", xbmc.LOGERROR)
    else:
        xbmc.executebuiltin('Notification(poweroff, not available)')
        xbmc.log("/usr/sbin/poweroff 不存在，尝试直接退出脚本", xbmc.LOGWARNING)
    
    # 最终退出
    xbmc.log("脚本执行完毕，准备退出", xbmc.LOGINFO)
    sys.exit(0)

def confirm_and_reboot():
    """弹出确认窗口，用户确认后执行重启"""
    dialog = xbmcgui.Dialog()
    result = dialog.yesno(
        "系统配置更新",
        "系统配置更新需要重启生效，选择\"是\"立刻自动重启，选择\"否\"请稍后手动重启。"
    )
    
    if result:  # 用户选择了"是"
        xbmc.log("用户确认重启，开始执行重启操作", xbmc.LOGINFO)
        reboot_system()
    else:  # 用户选择了"否"
        xbmc.log("用户取消重启，不执行任何操作", xbmc.LOGINFO)

def auto_reboot_no_confirm():
    """无确认直接重启"""
    xbmc.log("检测到noask参数，跳过确认直接重启", xbmc.LOGINFO)
    reboot_system()

def get_arch_type():
    """
    读取 /etc/os-release 文件中包含 ARCH 的行，判断类型。
    返回: 'ng', 'no', 或 'unknown'
    """
    arch_type = 'unknown'
    os_release_path = "/etc/os-release"
    
    try:
        if os.path.exists(os_release_path):
            with open(os_release_path, 'r') as f:
                for line in f:
                    # 查找包含 ARCH 的行，不区分大小写匹配键名
                    # 假设行格式类似 ARCH=something 或包含 ARCH 关键字
                    if 'ARCH' in line.upper():
                        line_lower = line.lower()
                        # 优先检查 ng，因为 ng 可能包含在 longer words 中，但通常 ARCH 值是简短的
                        # 根据需求：包括 "ng" 字样
                        if 'ng' in line_lower:
                            arch_type = 'ng'
                            break
                        # 检查 no 字样
                        elif 'no' in line_lower:
                            arch_type = 'no'
                            break
        else:
            xbmc.log(f"文件 {os_release_path} 不存在", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"读取 {os_release_path} 失败: {str(e)}", xbmc.LOGERROR)
        
    xbmc.log(f"检测到 ARCH 类型: {arch_type}", xbmc.LOGINFO)
    return arch_type

def handle_turnoff_logic():
    """
    处理 turnoff 参数的复杂逻辑：
    1. 读取 ARCH 类型。
    2. 获取 Skin.String(no22) 的值。
    3. 根据类型和 no22 的值执行不同操作。
    """
    arch_type = get_arch_type()
    
    # 获取当前 Skin.String(no22) 的值
    # xbmc.getInfoLabel 可以获取 Skin 字符串的值，如果未设置则返回空字符串
    current_no22_value = xbmc.getInfoLabel('Skin.String(no22)')
    xbmc.log(f"当前 Skin.String(no22) 值: '{current_no22_value}'", xbmc.LOGINFO)
    
    if arch_type == 'ng':
        # 情况1：包含 "ng"
        xbmc.log("ARCH 包含 ng，执行情况1逻辑", xbmc.LOGINFO)
        xbmc.executebuiltin("Skin.SetString(no22,0)")
        poweroff_system()
        
    elif arch_type == 'no':
        # 情况2 和 3：包含 "no"
        xbmc.log("ARCH 包含 no，检查 no22 状态", xbmc.LOGINFO)
        
        # 判断是否等于 "1"
        # 注意：InfoLabel 返回的是字符串
        is_no22_one = (current_no22_value == "1")
        
        if not is_no22_one:
            # 情况2：no22 不等于 1 (即 != 1)
            xbmc.log("情况2: no22 不等于 1，设置 no22=1 并执行 shutdown -h now", xbmc.LOGINFO)
            xbmc.executebuiltin("Skin.SetString(no22,1)")
            
            # 执行 shutdown -h now
            try:
                xbmc.log("执行 shutdown -h now", xbmc.LOGINFO)
                # 同步数据以防万一
                subprocess.run(["sync"], timeout=2, check=True)
                subprocess.run(["shutdown", "-h", "now"], check=True)
            except Exception as e:
                xbmc.log(f"执行 shutdown -h now 失败: {str(e)}", xbmc.LOGERROR)
                # 如果 shutdown 失败，可以选择回退到原逻辑或仅记录错误
                # 这里选择回退到原逻辑以保证最终能关机
                poweroff_system()
        else:
            # 情况3：no22 等于 1
            xbmc.log("情况3: no22 等于 1，执行原逻辑", xbmc.LOGINFO)
            poweroff_system()
            
    else:
        # 未知类型，执行原逻辑
        xbmc.log(f"未知 ARCH 类型 ({arch_type})，执行原逻辑", xbmc.LOGWARNING)
        poweroff_system()

def auto_poweroff():
    """自动关机入口，现在调用新的逻辑处理函数"""
    xbmc.log("检测到turnoff参数，执行自动关机逻辑判断", xbmc.LOGINFO)
    handle_turnoff_logic()

if __name__ == "__main__":
    args = sys.argv[1:]
    xbmc.log(f"接收到的参数: {args}", xbmc.LOGINFO)
    
    if args:
        # 检查第一个参数
        first_arg = args[0].lower()
        
        if first_arg == "reboot":
            if len(args) > 1 and args[1].lower() == "noask":
                # 调用: script.py reboot noask -> 直接重启无需确认
                auto_reboot_no_confirm()
            else:
                # 调用: script.py reboot -> 需要确认
                confirm_and_reboot()
        elif first_arg == "turnoff":
            # 调用: script.py turnoff -> 执行新的关机逻辑
            auto_poweroff()
        elif first_arg == "noask":
            # 调用: script.py noask -> 直接重启无需确认
            auto_reboot_no_confirm()
        else:
            xbmc.log(f"未知参数: {first_arg}，不执行任何操作。", xbmc.LOGWARNING)
    else:
        # 不带参数运行时，弹出用户确认窗口
        confirm_and_reboot()