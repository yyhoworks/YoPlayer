"""
KODI音乐播放脚本监控器
用于监控歌词显示状态并在特定条件下按顺序聚焦并选择控件
检测到时间重置后根据控件可见性执行不同的焦点选择操作
"""

import xbmc
import xbmcgui
import xbmcaddon
import time
import threading
from datetime import datetime
import os
import sys

class MusicPlayMonitor:
    def __init__(self):
        # 移除addon初始化，因为脚本不是作为addon运行的
        self.monitor = xbmc.Monitor()
        self.player = xbmc.Player()
        self.is_running = True
        self.last_time = ""
        self.log("MusicPlayMonitor 初始化完成")
        
    def log(self, message):
        """记录日志信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[MusicPlayMonitor] {timestamp} - {message}"
        xbmc.log(log_message, xbmc.LOGINFO)
        
    def get_player_time(self):
        """获取当前播放时间"""
        try:
            player_time = xbmc.getInfoLabel("Player.Time(hh:mm:ss)")
            return player_time
        except Exception as e:
            self.log(f"获取播放时间失败: {str(e)}")
            return ""
            
    def is_lyrics_window_visible(self):
        """检查歌词窗口是否可见"""
        try:
            # 检查script-cu-lrclyrics-main.xml窗口是否激活
            return xbmc.getCondVisibility('Window.IsActive(script-cu-lrclyrics-main.xml)')
        except Exception as e:
            self.log(f"检查歌词窗口可见性失败: {str(e)}")
            return False
            
    def is_control_visible(self, control_id):
        """检查控件是否可见"""
        try:
            return xbmc.getCondVisibility(f'Control.IsVisible({control_id})')
        except Exception as e:
            self.log(f"检查控件可见性失败 {control_id}: {str(e)}")
            return False
    
    def set_focus_and_select(self, control_id):
        """设置焦点并选择控件"""
        try:
            # 设置焦点到指定控件
            xbmc.executebuiltin(f'SetFocus({control_id})')
            self.log(f"已设置焦点到控件: {control_id}")
            
            # 执行选择动作
            xbmc.executebuiltin('Action(Select)')
            self.log("已执行选择动作")
        except Exception as e:
            self.log(f"设置焦点并选择失败 {control_id}: {str(e)}")
            
    def parse_time_to_seconds(self, time_str):
        """将hh:mm:ss格式的时间转换为总秒数"""
        try:
            if not time_str or len(time_str) != 8:
                return None
                
            # 解析时间字符串
            parts = time_str.split(':')
            if len(parts) != 3:
                return None
                
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            
            total_seconds = hours * 3600 + minutes * 60 + seconds
            return total_seconds
        except Exception as e:
            self.log(f"解析时间字符串失败: {time_str}, 错误: {str(e)}")
            return None
    
    def check_time_reset(self, current_time):
        """检查播放时间是否重置（只有当前时间比上一次时间小才算重置）"""
        try:
            current_seconds = self.parse_time_to_seconds(current_time)
            previous_seconds = getattr(self, 'previous_seconds', None)
            
            # 如果无法解析当前时间，跳过检查
            if current_seconds is None:
                return False
            
            # 如果这是第一次检查，只记录时间值
            if previous_seconds is None:
                self.previous_seconds = current_seconds
                return False
            
            # 只有当前时间比上一次时间小时才认为是重置
            time_reset_detected = current_seconds < previous_seconds
            self.previous_seconds = current_seconds
            
            if time_reset_detected:
                self.log(f"检测到时间重置: {self.last_time} -> {current_time} ({self.parse_time_to_seconds(self.last_time)}s -> {current_seconds}s)")
                return True
            else:
                return False
                
        except Exception as e:
            self.log(f"检查时间重置时出错: {str(e)}")
            return False
    
    def monitor_loop(self):
        """主监控循环"""
        self.log("开始监控循环")
        
        while self.is_running and not self.monitor.abortRequested():
            try:
                # 检查歌词窗口是否可见
                if not self.is_lyrics_window_visible():
                    self.log("歌词窗口不可见，停止监控")
                    break
                    
                # 获取当前播放时间
                current_time = self.get_player_time()
                
                # 检查时间是否重置
                if current_time != self.last_time:
                    if self.last_time and self.check_time_reset(current_time):
                        # 时间重置且满足条件，根据控件可见性执行不同操作
                        self.log("检测到时间重置，开始执行焦点选择操作")
                        
                        # 检查控件701是否可见
                        if self.is_control_visible(701):
                            self.log("控件701可见，执行双控件操作")
                            
                            # 设置焦点到701并执行选择动作
                            if self.is_lyrics_window_visible():
                                self.set_focus_and_select(701)
                            else:
                                self.log("歌词窗口已不可见，取消操作")
                                continue
                            
                            # 延迟0.5秒
                            xbmc.sleep(500)
                            
                            # 设置焦点到1701并执行选择动作
                            if self.is_lyrics_window_visible():
                                self.set_focus_and_select(1701)
                            else:
                                self.log("歌词窗口已不可见，取消操作")
                        else:
                            self.log("控件701不可见，只执行1701控件操作")
                            
                            # 延迟0.5秒
                            xbmc.sleep(500)
                            
                            # 设置焦点到1701并执行选择动作
                            if self.is_lyrics_window_visible():
                                self.set_focus_and_select(1701)
                            else:
                                self.log("歌词窗口已不可见，取消操作")
                        
                    self.last_time = current_time
                    
                # 短暂休眠，避免过度占用CPU
                xbmc.sleep(1000)
                
            except Exception as e:
                self.log(f"监控循环中出现错误: {str(e)}")
                xbmc.sleep(1000)
                
        self.log("监控循环结束")
        
    def start(self):
        """启动监控器"""
        self.log("启动音乐播放监控器")
        
        while self.is_running:
            try:
                # 启动监控循环
                self.monitor_loop()
                
                # 如果循环结束但is_running仍为True，说明是因歌词窗口不可见而退出
                # 等待一段时间后重新检查
                if self.is_running:
                    self.log("等待歌词窗口重新激活...")
                    
                    # 等待歌词窗口重新出现
                    wait_count = 0
                    max_wait = 60  # 最多等待60秒
                    
                    while (self.is_running and 
                           not self.monitor.abortRequested() and 
                           wait_count < max_wait and
                           not self.is_lyrics_window_visible()):
                        xbmc.sleep(1000)
                        wait_count += 1
                        
                    if not self.is_lyrics_window_visible():
                        self.log("等待超时，歌词窗口仍未出现，退出监控器")
                        break
                    else:
                        self.log("歌词窗口重新激活，继续监控")
                        
            except Exception as e:
                self.log(f"监控器主循环中出现错误: {str(e)}")
                xbmc.sleep(5000)  # 错误后等待5秒再重试
                
        self.log("音乐播放监控器完全停止")
        
    def stop(self):
        """停止监控器"""
        self.log("正在停止音乐播放监控器")
        self.is_running = False

def check_single_instance():
    """检查是否已有实例在运行"""
    try:
        # 使用Kodi的内置属性来跟踪脚本运行状态
        # 创建一个临时窗口来存储运行状态
        window_id = 10000  # Home window
        property_name = "musicplay_monitor_running"
        
        # 检查是否已有实例在运行
        existing_value = xbmcgui.Window(window_id).getProperty(property_name)
        
        if existing_value == "true":
            xbmc.log("[MusicPlayMonitor] 检测到已有实例在运行，退出当前实例", xbmc.LOGINFO)
            return False
        
        # 设置实例运行标志
        xbmcgui.Window(window_id).setProperty(property_name, "true")
        
        # 为了确保在脚本异常退出时也能清理标志，我们注册一个清理函数
        import atexit
        atexit.register(cleanup_instance_flag)
        
        return True
    except Exception as e:
        xbmc.log(f"[MusicPlayMonitor] 检查单实例运行时出错: {str(e)}", xbmc.LOGINFO)
        # 出错时假设没有其他实例在运行，继续执行
        return True

def cleanup_instance_flag():
    """清理实例运行标志"""
    try:
        window_id = 10000  # Home window
        property_name = "musicplay_monitor_running"
        xbmcgui.Window(window_id).clearProperty(property_name)
    except Exception as e:
        xbmc.log(f"[MusicPlayMonitor] 清理实例标志时出错: {str(e)}", xbmc.LOGINFO)

def main():
    """主函数"""
    # 检查是否已有实例在运行
    if not check_single_instance():
        xbmc.log("[MusicPlayMonitor] 脚本已在运行，当前实例退出", xbmc.LOGINFO)
        return
    
    monitor = MusicPlayMonitor()
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.log("收到中断信号，停止监控器")
    except Exception as e:
        monitor.log(f"监控器运行时出现严重错误: {str(e)}")
    finally:
        monitor.stop()
        cleanup_instance_flag()

if __name__ == "__main__":
    main()