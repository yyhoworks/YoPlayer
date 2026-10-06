import xbmc
import xbmcgui
import random
import time

class DemoTrailer:
    def __init__(self):
        pass
        
    def run(self):
        # 首先设置allowdemo为1
        xbmc.executebuiltin('Skin.SetString(allowdemo,1)')
        time.sleep(0.1)
        
        # 执行回退操作
        xbmc.executebuiltin('Action(back)')
        time.sleep(0.1)
        
        # 检查refreshrate设置
        refresh_rate_value = xbmc.getInfoLabel('Skin.String(refreshrate)')
        if '关' not in refresh_rate_value:
            xbmc.executebuiltin('RunScript(special://skin/scripts/refreshrate.py,off)')
        
        # 主循环
        while True:
            # 检查退出条件
            if not self.check_conditions():
                break
            
            # 获取当前控件ID和项目数量
            current_control_id = xbmc.getInfoLabel('System.CurrentControlID')
            try:
                num_items = int(xbmc.getInfoLabel('Container.NumItems'))
            except ValueError:
                num_items = 1
            
            if num_items < 1:
                num_items = 1
            
            # 循环逻辑开始
            xbmc.executebuiltin('Skin.SetString(nextdemo,"")')
            time.sleep(0.5)
            
            # 在1到num_items之间随机选择
            random_item = random.randint(1, num_items)
            
            # 设置焦点到随机项目
            xbmc.executebuiltin(f'SetFocus({current_control_id},{random_item},absolute)')
            time.sleep(0.1)
            
            # 运行bilitrailer脚本
            xbmc.executebuiltin('RunScript(special://skin/scripts/bilitrailer.py,demo)')
            time.sleep(2)
            
            # 监测视频播放状态（最多等待10秒）
            start_time = time.time()
            video_playing = False
            
            while time.time() - start_time < 10:
                if not self.check_conditions():
                    break
                
                if xbmc.getCondVisibility('Player.HasVideo'):
                    video_playing = True
                    break
                time.sleep(0.5)
            
            if not video_playing:
                # 10秒内没有检测到视频播放
                xbmc.executebuiltin('setfocus(2601)')
                xbmc.executebuiltin('PlayerControl(Stop)')
                xbmc.executebuiltin('setfocus(50)')
                xbmc.executebuiltin('Skin.SetString(demoplaying,0)')
                continue  # 返回循环开始
            else:
                # 延时1秒后执行setfocus和设置demoplaying
                time.sleep(2)
                xbmc.executebuiltin('setfocus(2601)')
                xbmc.executebuiltin('Skin.SetString(demoplaying,1)')
                
                # 监测结束条件
                start_time = time.time()
                
                initial_current_item = xbmc.getInfoLabel('Container.CurrentItem')
                
                while True:
                    if not self.check_conditions():
                        break
                    
                    # 检查时间剩余、nextdemo状态或当前项目变化
                    time_remaining = xbmc.getInfoLabel('Player.TimeRemaining')
                    
                    try:
                        # 解析时间字符串，格式可能是 00:00:02 或 00:02
                        parts = time_remaining.split(':')
                        if len(parts) == 2:  # MM:SS
                            minutes = int(parts[0])
                            seconds = int(parts[1])
                            total_seconds = minutes * 60 + seconds
                        elif len(parts) == 3:  # HH:MM:SS
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            seconds = int(parts[2])
                            total_seconds = hours * 3600 + minutes * 60 + seconds
                        else:
                            total_seconds = 999  # 默认值，继续监测
                    except:
                        total_seconds = 999  # 解析失败，默认值，继续监测
                    
                    next_demo_status = xbmc.getInfoLabel('Skin.String(nextdemo)')
                    current_item = xbmc.getInfoLabel('Container.CurrentItem')
                    
                    if (total_seconds <= 2 or 
                        next_demo_status == '1' or 
                        current_item != initial_current_item):
                        
                        xbmc.executebuiltin('PlayerControl(Stop)')
                        xbmc.executebuiltin('setfocus(50)')
                        xbmc.executebuiltin('Skin.SetString(demoplaying,0)')
                        time.sleep(0.2)
                        break
                    
                    time.sleep(0.5)
        
        # 脚本退出前的清理工作
        xbmc.executebuiltin('PlayerControl(Stop)')
        xbmc.executebuiltin('Skin.SetString(allowdemo,0)')
        
        rate_change_status = xbmc.getInfoLabel('Skin.String(ratechange)')
        if rate_change_status != '1':
            return  # 直接退出
        else:
            xbmc.executebuiltin('RunScript(special://skin/scripts/refreshrate.py,on)')
            return
    
    def check_conditions(self):
        """
        检查是否满足继续运行的条件
        """
        videos_visible = xbmc.getCondVisibility('Window.IsVisible(videos)')
        allow_demo = xbmc.getInfoLabel('Skin.String(allowdemo)')
        
        if not videos_visible or allow_demo != '1':
            xbmc.executebuiltin('PlayerControl(Stop)')
            xbmc.executebuiltin('Skin.SetString(allowdemo,0)')
            
            rate_change_status = xbmc.getInfoLabel('Skin.String(ratechange)')
            if rate_change_status != '1':
                return False  # 退出脚本
            else:
                xbmc.executebuiltin('RunScript(special://skin/scripts/refreshrate.py,on)')
                return False  # 退出脚本
        
        return True

if __name__ == '__main__':
    demo_trailer = DemoTrailer()
    demo_trailer.run()