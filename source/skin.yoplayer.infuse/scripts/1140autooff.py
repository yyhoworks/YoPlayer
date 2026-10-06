import xbmc
import xbmcgui

def get_current_info():
    """
    获取当前播放信息
    优先获取 VideoPlayer.Episode，如果为空则获取 Player.Title
    """
    episode = xbmc.getInfoLabel('VideoPlayer.Episode')
    if episode:
        return episode.strip()
    else:
        title = xbmc.getInfoLabel('Player.Title')
        return title.strip()

def main():
    # 获取初始信息值
    initial_info_value = get_current_info()
    
    while True:
        # 检查窗口1140是否可见
        if xbmc.getCondVisibility('Window.IsVisible(1140)'):
            # 监测信息值是否变化
            current_info_value = get_current_info()
            
            if current_info_value != initial_info_value:
                # 延时0.5秒
                xbmc.sleep(500)
                
                # 关闭对话框
                xbmc.executebuiltin('Dialog.Close(1140)')
                
                # 退出脚本
                break
        else:
            # 窗口不可见，退出脚本
            break
        
        # 短暂休眠，避免过度占用CPU
        xbmc.sleep(100)

if __name__ == '__main__':
    main()