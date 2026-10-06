"""
KODI脚本：监测控件标签并智能设置皮肤变量
运行方式：RunScript(special://skin/scripts/9input.py)
功能：监测ID为309的控件标签内容，根据内容智能设置皮肤变量basepy
"""

import xbmc

def log_message(message):
    """记录日志消息"""
    xbmc.log(message, level=xbmc.LOGINFO)

def get_skin_string(variable_name):
    """获取皮肤变量的值"""
    return xbmc.getInfoLabel(f'Skin.String({variable_name})')

def check_and_set_basepy_variable():
    """检查控件标签并智能设置皮肤变量"""
    try:
        # 获取按钮标签
        button_label = xbmc.getInfoLabel('Control.GetLabel(309)')
        
        if button_label and "basepy" in button_label.lower():
            # 标签包含"BasePY"，检查当前皮肤变量值
            current_value = get_skin_string('basepy')
            
            if current_value != '1':
                log_message(f"标签包含'BasePY'，当前basepy值为'{current_value}'，设置Skin.SetString(basepy,1)")
                xbmc.executebuiltin('Skin.SetString(basepy,1)')
            else:
                log_message(f"标签包含'BasePY'，当前basepy值为'1'，无需更改")
        else:
            # 标签不包含"BasePY"或获取失败，检查当前皮肤变量值
            current_value = get_skin_string('basepy')
            
            if current_value != '0':
                log_message(f"标签不包含'BasePY'或获取失败，当前basepy值为'{current_value}'，设置Skin.SetString(basepy,0)")
                xbmc.executebuiltin('Skin.SetString(basepy,0)')
            else:
                log_message(f"标签不包含'BasePY'或获取失败，当前basepy值为'0'，无需更改")
                
    except Exception as e:
        log_message(f"检查控件标签或设置变量时出错: {str(e)}")
        # 出错时确保变量被设置为默认值
        current_value = get_skin_string('basepy')
        if current_value != '0':
            xbmc.executebuiltin('Skin.SetString(basepy,0)')

def main():
    """主函数"""
    log_message("开始执行脚本 special://skin/scripts/9input.py")
    
    # 持续监测虚拟键盘是否可见
    monitor = xbmc.Monitor()
    
    while not monitor.abortRequested():
        # 检查虚拟键盘是否可见
        virtual_keyboard_visible = xbmc.getCondVisibility('Window.IsVisible(VirtualKeyboard)')
        
        if virtual_keyboard_visible:
            # 虚拟键盘可见，检查控件标签并设置变量
            check_and_set_basepy_variable()
            log_message("虚拟键盘可见，继续监测...")
        else:
            # 虚拟键盘不可见，退出脚本
            log_message("虚拟键盘不可见，退出脚本")
            break
        
        # 等待1秒后再次检查，避免过度占用CPU
        if monitor.waitForAbort(1):
            # 如果等待期间收到终止信号，退出循环
            break
    
    log_message("脚本执行完成")

# 执行主函数
if __name__ == "__main__":
    main()