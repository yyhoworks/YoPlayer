#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：filterlink.py
功能：
1. 接收remote参数：检查指定ControlGroup焦点，执行back或直接setfocus(5080)
2. 接收menu参数：检查指定ControlGroup焦点，执行back或延时0.5秒setfocus(5080)
"""
import xbmc
import xbmcgui  # 导入xbmcgui用于延时功能
import sys

def check_control_focus():
    """封装焦点检查逻辑，避免重复代码"""
    # 定义需要检查焦点的ControlGroup ID列表
    control_ids = [5080, 5081, 5082, 5083, 5084, 5086]
    # 构建KODI条件判断字符串
    focus_conditions = " | ".join([f"ControlGroup({cid}).HasFocus" for cid in control_ids])
    # 返回焦点检查结果
    return xbmc.getCondVisibility(focus_conditions)

def main():
    # 检查是否传入参数
    if len(sys.argv) < 2:
        xbmc.log("[filterlink.py] 未传入任何参数，脚本退出", level=xbmc.LOGINFO)
        return
    
    # 获取并标准化参数（转小写，提高兼容性）
    cmd_param = sys.argv[1].lower()
    
    # 1. 处理remote参数（原有逻辑）
    if cmd_param == "remote":
        has_focus = check_control_focus()
        if has_focus:
            xbmc.log("[filterlink.py] [remote参数] 检测到目标ControlGroup有焦点，执行Action(back)", level=xbmc.LOGINFO)
            xbmc.executebuiltin("Action(back)")
        else:
            xbmc.log("[filterlink.py] [remote参数] 未检测到目标ControlGroup焦点，执行SetFocus(5080)", level=xbmc.LOGINFO)
            xbmc.executebuiltin("SetFocus(5080)")
    
    # 2. 处理menu参数（新增逻辑）
    elif cmd_param == "menu":
        has_focus = check_control_focus()
        if has_focus:
            xbmc.log("[filterlink.py] [menu参数] 检测到目标ControlGroup有焦点，执行Action(back)", level=xbmc.LOGINFO)
            xbmc.executebuiltin("Action(back)")
        else:
            xbmc.log("[filterlink.py] [menu参数] 未检测到目标ControlGroup焦点，延时0.5秒执行SetFocus(5080)", level=xbmc.LOGINFO)
            xbmc.sleep(300)  # 延时0.5秒（单位：毫秒）
            xbmc.executebuiltin("SetFocus(5080)")
    
    # 3. 未知参数处理
    else:
        xbmc.log(f"[filterlink.py] 不支持的参数：{sys.argv[1]}，仅支持remote/menu参数", level=xbmc.LOGWARNING)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 异常日志记录，便于调试
        xbmc.log(f"[filterlink.py] 脚本执行出错: {str(e)}", level=xbmc.LOGERROR)