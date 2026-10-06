import xbmc
import xbmcaddon
import xbmcgui

def get_skin_string(name):
    """获取皮肤字符串值"""
    return xbmc.getInfoLabel(f'Skin.String({name})')

def set_skin_string(name, value):
    """设置皮肤字符串值"""
    xbmc.executebuiltin(f'Skin.SetString({name},{value})')

def has_skin_setting(setting_name):
    """检查皮肤设置是否存在（返回True/False）"""
    # 在Kodi中，Skin.HasSetting 返回空字符串表示false，非空表示true
    result = xbmc.getCondVisibility(f'Skin.HasSetting({setting_name})')
    return result == 1

def is_player_has_video():
    """检查是否有视频正在播放"""
    return xbmc.getCondVisibility('Player.HasVideo') == 1

def is_window_visible(window_id):
    """检查窗口是否可见"""
    return xbmc.getCondVisibility(f'Window.IsVisible({window_id})') == 1

def play_media(url):
    """播放媒体"""
    xbmc.executebuiltin(f'PlayMedia({url},1,noresume)')

def run_trailer_script():
    """运行trailer.py脚本"""
    xbmc.executebuiltin('RunScript(special://skin/scripts/trailer.py,info)')

def close_dialog(dialog_id):
    """关闭对话框"""
    xbmc.executebuiltin(f'Dialog.Close({dialog_id})')

def main():
    # 获取命令行参数
    import sys
    args = sys.argv
    
    # 检查是否带有info参数
    if len(args) < 2 or args[1] != 'info':
        return  # 如果没有info参数，则退出
    
    # 获取trailerurl值
    trailer_url = get_skin_string('trailerurl')
    
    if not trailer_url or trailer_url.strip() == '':
        # 如果trailerurl为空值，执行trailer.py脚本
        run_trailer_script()
        return
    else:
        # 如果trailerurl不为空值，播放预告片
        play_media(trailer_url)
        
        # 等待一段时间让播放器启动
        xbmc.sleep(2000)
        
        # 检测预告片是否正常播放
        if not is_player_has_video():
            # 如果预告片没有正常播放，执行trailer.py脚本
            run_trailer_script()
            return
        
        # 预告片正常播放，设置notrailer为0
        set_skin_string('notrailer', '0')
        
        # 检查trailerloop设置
        if not has_skin_setting('trailerloop'):
            # 如果trailerloop为"否"（即设置不存在或为false）
            # 监测Player.HasVideo直到为"假"
            while is_player_has_video():
                xbmc.sleep(500)  # 等待0.5秒后再次检查
            
            # Player.HasVideo不为"真"时，设置notrailer为1并关闭对话框
            set_skin_string('notrailer', '1')
            close_dialog(1130)
        else:
            # 如果trailerloop为"真"（即设置存在且为true）
            dialog_id = 1130
            while True:
                # 循环监测Player.HasVideo直到为"假"
                while is_player_has_video():
                    xbmc.sleep(500)  # 等待0.5秒后再次检查
                
                # 检测窗口是否可见
                if is_window_visible(dialog_id):
                    # 如果窗口可见，重复播放预告片
                    play_media(trailer_url)
                    xbmc.sleep(2000)  # 等待播放器启动
                    
                    # 如果播放失败，跳出循环
                    if not is_player_has_video():
                        break
                else:
                    # 窗口不可见，结束循环
                    break

if __name__ == '__main__':
    main()