# -*- coding: utf-8 -*-
import xbmc
import xbmcvfs
import time

# ===== 核心修复：新版KODI专用 兼容所有版本的路径转换方法 =====
# 替代被移除的 xbmc.translatePath，完美兼容KODI18/19/20/21 + CoreELEC + Windows
userdata_path = xbmcvfs.translatePath('special://userdata/')
# 原有收藏夹文件路径
fav_file = xbmcvfs.validatePath(userdata_path + 'favourites.xml')

# 定义核心监测执行函数
def fav_monitor():
    # 初始化文件最后修改时间戳，0适配「文件不存在」的初始状态
    last_modify_time_fav = 0  # 收藏夹文件时间戳
    last_plot_content = ""    # 记录上次的Plot内容，避免重复触发
    # 创建KODI播放器实例，检测播放状态
    kodi_player = xbmc.Player()
    
    xbmc.log("[FAVCHECK] 收藏夹+Plot字符数监测脚本已启动(修复版)，常驻运行中...", xbmc.LOGINFO)
    xbmc.log(f"[FAVCHECK] 监测收藏夹文件: {fav_file}", xbmc.LOGINFO)
    xbmc.log(f"[FAVCHECK] 监测ListItem.Plot字符数，阈值：350个字符", xbmc.LOGINFO)

    # 无限循环实现常驻监测核心逻辑
    while True:
        # ===== 优先级最高：播放中暂停所有监测，零干扰播放稳定性 =====
        if kodi_player.isPlayingVideo() or kodi_player.isPlaying():
            time.sleep(3)  # 播放中休眠3秒，极致降低CPU占用
            continue

        # ===== 非播放状态，执行监测逻辑 =====
        # ---------------------- 原有：监测favourites.xml ----------------------
        try:
            file_stat_fav = xbmcvfs.Stat(fav_file)
            current_modify_time_fav = file_stat_fav.st_mtime()
            
            if current_modify_time_fav > last_modify_time_fav:
                xbmc.log("[FAVCHECK] 检测到 favourites.xml 新增/修改 ✔️，执行 favfenku.py", xbmc.LOGINFO)
                xbmc.executebuiltin('RunScript(special://skin/scripts/favfenku.py)')
                last_modify_time_fav = current_modify_time_fav

        except FileNotFoundError:
            pass
        except Exception:
            pass

        # ---------------------- 新增：监测ListItem.Plot字符数 ----------------------
        try:
            # 获取KODI当前ListItem.Plot的内容
            current_plot = xbmc.getInfoLabel("ListItem.Plot")
            # 避免空内容/重复内容触发：仅当内容变化且字符数超350时执行
            if current_plot != last_plot_content and len(current_plot) > 350:
                xbmc.log(f"[FAVCHECK] 检测到ListItem.Plot字符数超标 ✔️（当前：{len(current_plot)}字符），执行 R5plot.py", xbmc.LOGINFO)
                xbmc.executebuiltin('RunScript(special://skin/scripts/R5plot.py)')
                # 更新上次Plot内容，防止重复触发
                last_plot_content = current_plot
            # 若Plot内容清空/变化但字符数未超，仅更新记录不执行脚本
            elif current_plot != last_plot_content:
                last_plot_content = current_plot

        except Exception as e:
            # 捕获异常并记录，不中断程序
            xbmc.log(f"[FAVCHECK] 监测ListItem.Plot时出错：{str(e)}", xbmc.LOGWARNING)
            pass

        # 监测间隔2秒，兼顾响应速度和资源占用
        time.sleep(2)

# ===== 主程序入口：异常自动重启 + 永久常驻内存 =====
if __name__ == "__main__":
    # 无限循环：任何报错/异常/退出 → 自动重启，永不失效
    while True:
        try:
            fav_monitor()
        except Exception as err:
            # 捕获所有异常并记录日志
            error_info = f"[FAVCHECK] 脚本异常，5秒后自动重启 | 异常信息: {str(err)}"
            xbmc.log(error_info, xbmc.LOGERROR)
            # 重启前休眠5秒，避免极端情况无限重启
            time.sleep(5)