import xbmc
import xbmcgui
import time
import sys

def time_to_seconds(time_str):
    """将时间字符串转换为秒数，支持数字字符串或hh:mm:ss格式"""
    if not time_str:
        return 0
    
    # 检查是否包含冒号，决定是时间格式还是纯数字
    if ':' in time_str:
        # 处理 hh:mm:ss 格式
        parts = time_str.split(':')
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
        # 处理纯数字字符串（秒数）
        try:
            return int(time_str)
        except ValueError:
            return 0
    
    return 0

def calculate_and_seek():
    """计算时间差并执行跳转（差值减2秒）"""
    # 获取皮肤字符串值
    skin_string_value = xbmc.getInfoLabel('Skin.String(epintro)')
    xbmc.log(f"Skin.String(epintro) value: {skin_string_value}", xbmc.LOGDEBUG)
    
    # 获取当前播放时间
    current_time = xbmc.getInfoLabel('Player.Time(hh:mm:ss)')
    xbmc.log(f"Current Player Time: {current_time}", xbmc.LOGDEBUG)
    
    try:
        # 将时间字符串转换为秒数
        skin_time_seconds = time_to_seconds(skin_string_value)
        current_time_seconds = time_to_seconds(current_time)
        
        xbmc.log(f"Skin time in seconds: {skin_time_seconds}", xbmc.LOGDEBUG)
        xbmc.log(f"Current time in seconds: {current_time_seconds}", xbmc.LOGDEBUG)
        
        # 计算差值
        diff = skin_time_seconds - current_time_seconds
        
        xbmc.log(f"Time difference: {diff} seconds", xbmc.LOGDEBUG)
        
        # 计算差值减2秒
        adjusted_diff = diff - 2
        
        xbmc.log(f"Adjusted time difference (minus 2 seconds): {adjusted_diff} seconds", xbmc.LOGDEBUG)
        
        # 执行跳转
        if adjusted_diff != 0:
            abs_adjusted_diff = abs(adjusted_diff)
            if adjusted_diff < 0:
                xbmc.log(f"Seeking backward by {abs_adjusted_diff} seconds", xbmc.LOGDEBUG)
                xbmc.executebuiltin(f'Seek(-{abs_adjusted_diff})')
            else:
                xbmc.log(f"Seeking forward by {abs_adjusted_diff} seconds", xbmc.LOGDEBUG)
                xbmc.executebuiltin(f'Seek({abs_adjusted_diff})')
            
            xbmc.log(f"Seek executed with {adjusted_diff} seconds", xbmc.LOGDEBUG)
        else:
            xbmc.log("No seek needed, adjusted time difference is zero", xbmc.LOGDEBUG)
            
    except Exception as e:
        xbmc.log(f"Error in time calculation or seeking: {e}", xbmc.LOGERROR)

def main(skip_mode=False):
    if skip_mode:
        xbmc.log("Skip mode activated: calculating time difference and seeking", xbmc.LOGDEBUG)
        calculate_and_seek()
        return
    
    # 记录开始
    xbmc.log("Script started: Focus control and auto-click for control 11211", xbmc.LOGDEBUG)
    
    # 立即执行 SetFocus(11211)
    xbmc.executebuiltin('SetFocus(11211)')
    xbmc.log("Executed: SetFocus(11211)", xbmc.LOGDEBUG)
    
    # 等待一小段时间让焦点设置生效
    xbmc.sleep(500)
    xbmc.log("Waited 500ms for focus to take effect", xbmc.LOGDEBUG)
    
    # 初始化变量
    timeout_duration = 3  # 3秒超时
    focus_11211_time = None  # 记录焦点到达11211的时间
    
    # 监控焦点状态
    monitor = xbmc.Monitor()
    iteration_count = 0
    
    while not monitor.abortRequested():
        try:
            iteration_count += 1
            xbmc.log(f"Iteration #{iteration_count}: Checking focus status", xbmc.LOGDEBUG)
            
            # 使用KODI的内置条件来检查焦点
            has_focus_11211 = xbmc.getCondVisibility('Control.HasFocus(11211)')
            window_visible = xbmc.getCondVisibility('Window.IsVisible(1121)')
            
            xbmc.log(f"Control.HasFocus(11211): {has_focus_11211}", xbmc.LOGDEBUG)
            xbmc.log(f"Window.IsVisible(1121): {window_visible}", xbmc.LOGDEBUG)
            
            if has_focus_11211:
                # 如果焦点在控件ID 11211上
                xbmc.log("Focus detected on control 11211", xbmc.LOGDEBUG)
                
                if focus_11211_time is None:
                    # 第一次检测到焦点在11211上，记录时间
                    focus_11211_time = time.time()
                    xbmc.log(f"First time focus detected on 11211 at: {focus_11211_time}", xbmc.LOGDEBUG)
                
                # 检查是否超过了3秒
                elapsed_time = time.time() - focus_11211_time
                xbmc.log(f"Time elapsed since focus on 11211: {elapsed_time:.2f}s", xbmc.LOGDEBUG)
                
                if elapsed_time >= timeout_duration:
                    # 超时，使用Action来模拟点击
                    xbmc.log("Timeout reached! Using Action to click control 11211...", xbmc.LOGDEBUG)
                    
                    # 使用Action(select)来激活当前焦点控件
                    xbmc.executebuiltin('Action(select)')
                    xbmc.log("Action(select) executed to click focused control", xbmc.LOGDEBUG)
                    
                    # 点击后退出循环
                    xbmc.log("Auto-click completed, exiting script", xbmc.LOGDEBUG)
                    break
            else:
                # 焦点不在控件11211上
                xbmc.log("Focus is NOT on control 11211", xbmc.LOGDEBUG)
                
                if focus_11211_time is not None:
                    # 焦点曾经在11211上但现在离开了，重置计时器
                    xbmc.log("Focus left control 11211 before timeout, resetting timer", xbmc.LOGDEBUG)
                    focus_11211_time = None
                
                # 检查窗口是否仍然可见
                if not window_visible:
                    # 窗口不可见，退出脚本
                    xbmc.log("Window 1121 is no longer visible, exiting script", xbmc.LOGDEBUG)
                    break
                else:
                    # 窗口仍然可见，继续等待焦点回到11211
                    xbmc.log("Window 1121 is still visible, waiting for focus to return to control 11211", xbmc.LOGDEBUG)
                
            # 短暂休眠以减少CPU占用
            xbmc.sleep(200)
            
        except Exception as e:
            # 发生异常时退出循环
            xbmc.log(f"Error in script: {e}", xbmc.LOGERROR)
            break
    
    xbmc.log("Script ended", xbmc.LOGDEBUG)

# 运行主函数
if __name__ == "__main__":
    # 检查命令行参数
    skip_mode = False
    if len(sys.argv) > 1 and sys.argv[1] == "skip":
        skip_mode = True
    
    main(skip_mode)