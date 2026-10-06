import xbmc

def main():
    # 获取皮肤字符串中的预告片URL
    maoyan_url = xbmc.getInfoLabel('Skin.String(maoyanurl)')
    if not maoyan_url:
        xbmc.log("MaoYanClick: No URL found in Skin.String(maoyanurl)", xbmc.LOGERROR)
        # 不使用Dialog，因为这会导致其他问题
        return
    
    # 播放媒体
    xbmc.executebuiltin(f'PlayMedia({maoyan_url},False,1)')
    
    # 等待一段时间以确认播放是否开始
    wait_time = 5  # 等待5秒以检查播放状态
    waited = 0
    
    while waited < wait_time:
        if xbmc.Player().isPlayingVideo():
            # 播放已经开始，设置皮肤变量notrailer为0
            xbmc.executebuiltin('Skin.SetString(notrailer,0)')
            
            # 监听播放状态直到播放结束
            while xbmc.Player().isPlayingVideo():
                xbmc.sleep(1000)  # 每秒检查一次
            
            # 播放结束，设置皮肤变量notrailer为1
            xbmc.executebuiltin('Skin.SetString(notrailer,1)')
            return
        
        xbmc.sleep(1000)
        waited += 1
    
    # 如果等待时间结束后仍未开始播放，记录错误并退出
    xbmc.log("MaoYanClick: Trailer did not start playing within timeout period", xbmc.LOGERROR)
    # 不使用Dialog，因为在脚本模式下调用可能导致问题
    return

if __name__ == '__main__':
    main()