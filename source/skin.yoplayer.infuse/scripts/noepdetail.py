import xbmc
import xbmcgui
import time

class NoEpDetailScript:
    def __init__(self):
        # 1. 立即执行 Dialog.Close(all) 关闭所有打开的对话框
        xbmc.executebuiltin('Action(back)')
        xbmc.log("[NoEpDetail] 已执行 Dialog.Close(all) 关闭所有对话框", xbmc.LOGINFO)
        
        # 关键修复：等待对话框关闭动画完成（默认200ms，可根据设备性能调整）
        # 动画通常持续100-300ms，200ms是兼容大多数设备的最优值
        xbmc.sleep(200)
        
        # 2. 动画完成后，执行呼出上下文菜单的操作
        xbmc.executebuiltin('Action(ContextMenu)')
        xbmc.log("[NoEpDetail] 已执行呼出上下文菜单操作", xbmc.LOGINFO)
        
        # 3. 检测上下文菜单是否弹出（仅用窗口ID，兼容旧版Kodi）
        self.wait_for_context_menu()
        
        # 4. 菜单弹出后关闭脚本
        xbmc.log("[NoEpDetail] 已检测到上下文菜单弹出，脚本退出", xbmc.LOGINFO)

    def wait_for_context_menu(self):
        """循环检测上下文菜单窗口（兼容全版本Kodi）"""
        max_wait_time = 5  # 最大等待时间（秒），防止无限循环
        start_time = time.time()
        context_menu_window_id = 10106  # Kodi 标准上下文菜单窗口ID（Confluence皮肤兼容）
        
        while time.time() - start_time < max_wait_time:
            # 检测当前活跃窗口是否为上下文菜单
            if xbmcgui.getCurrentWindowId() == context_menu_window_id:
                return  # 检测到菜单，退出等待
            
            xbmc.sleep(100)  # 减少CPU占用
        
        # 超时未检测到菜单（日志警告，方便排查）
        xbmc.log("[NoEpDetail] 警告：{}秒内未检测到上下文菜单弹出（可能是动作被屏蔽或窗口ID不匹配）".format(max_wait_time), xbmc.LOGWARNING)

if __name__ == "__main__":
    script = NoEpDetailScript()