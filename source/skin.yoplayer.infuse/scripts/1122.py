import xbmc
import xbmcgui
import time

def main():
    # 记录开始
    xbmc.log("Script started: Focus control and auto-click using Action", xbmc.LOGDEBUG)
    
    # 执行 SetFocus(11220, $INFO[VideoPlayer.Episode], absolute)
    episode_info = xbmc.getInfoLabel("VideoPlayer.Episode")
    xbmc.log(f"Episode info retrieved: {episode_info}", xbmc.LOGDEBUG)
    xbmc.executebuiltin(f'SetFocus(11220,{episode_info},absolute)')
    xbmc.log("Executed: SetFocus(11220,...)", xbmc.LOGDEBUG)
    
    # 执行 SetFocus(11221)
    xbmc.executebuiltin('SetFocus(11221)')
    xbmc.log("Executed: SetFocus(11221)", xbmc.LOGDEBUG)
    
    # 等待一小段时间让焦点设置生效
    xbmc.sleep(500)
    xbmc.log("Waited 500ms for focus to take effect", xbmc.LOGDEBUG)
    
    # 初始化变量
    timeout_duration = 3  # 3秒超时
    start_time = time.time()
    initial_focus_time = None  # 记录焦点到达11221的时间
    
    # 监控焦点状态
    monitor = xbmc.Monitor()
    iteration_count = 0
    
    while not monitor.abortRequested():
        try:
            iteration_count += 1
            xbmc.log(f"Iteration #{iteration_count}: Checking focus status", xbmc.LOGDEBUG)
            
            # 使用KODI的内置条件来检查焦点
            has_focus_11221 = xbmc.getCondVisibility('Control.HasFocus(11221)')
            xbmc.log(f"Control.HasFocus(11221): {has_focus_11221}", xbmc.LOGDEBUG)
            
            if has_focus_11221:
                # 如果焦点在控件ID 11221上
                xbmc.log("Focus detected on control 11221", xbmc.LOGDEBUG)
                
                if initial_focus_time is None:
                    # 第一次检测到焦点在11221上，记录时间
                    initial_focus_time = time.time()
                    xbmc.log(f"First time focus detected on 11221 at: {initial_focus_time}", xbmc.LOGDEBUG)
                
                # 检查是否达到了3秒
                if initial_focus_time is not None:
                    elapsed_time = time.time() - initial_focus_time
                    xbmc.log(f"Time elapsed since focus on 11221: {elapsed_time:.2f}s", xbmc.LOGDEBUG)
                    
                    if elapsed_time >= timeout_duration:
                        # 超时，使用Action来模拟点击
                        xbmc.log("Timeout reached! Using Action to click control 11221...", xbmc.LOGDEBUG)
                        
                        # 使用Action(7)即Select action来激活当前焦点控件
                        xbmc.executebuiltin('Action(select)')
                        xbmc.log("Action(select) executed to click focused control", xbmc.LOGDEBUG)
                        
                        # 点击后退出循环
                        xbmc.log("Auto-click completed, exiting script", xbmc.LOGDEBUG)
                        break
            else:
                # 焦点不在控件11221上
                xbmc.log("Focus is NOT on control 11221", xbmc.LOGDEBUG)
                
                # 如果之前焦点在11221上但现在不在了，则退出脚本
                if initial_focus_time is not None:
                    xbmc.log("Focus left control 11221 before timeout, exiting script", xbmc.LOGDEBUG)
                    break
                
                # 否则继续监控
                initial_focus_time = None
                
            # 短暂休眠以减少CPU占用
            xbmc.sleep(200)
            
        except Exception as e:
            # 发生异常时退出循环
            xbmc.log(f"Error in script: {e}", xbmc.LOGERROR)
            break
    
    xbmc.log("Script ended", xbmc.LOGDEBUG)

# 运行主函数
if __name__ == "__main__":
    main()
