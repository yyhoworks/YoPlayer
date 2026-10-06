# -*- coding: utf-8 -*-
"""
KODI Skin Helper Script: favjump.py

功能:
1. 当以 "favpage" 为参数调用时:
   - 【已修改】首先在脚本内部获取 $INFO[ListItem.FolderPath] 的值。
   - 然后执行 Dialog.Close(all) 指令。
   - 接着执行 ActivateWindow(Videos,获取到的路径字符串,return) 指令。
   - 最后执行 Skin.SetString(favjump,1)。

2. 当以 "poster" 为参数调用时:
   - 首先延时0.2秒，等待可能的视频加载。
   - 检查播放器是否正在加载视频播放。
   - 如果没有加载视频播放，则执行 ActivateWindow(1119)。
   - 最后，执行 Skin.SetString(favjump,0)。

如何在KODI中调用:
- 调用favpage功能: RunScript(special://skin/scripts/favjump.py, favpage)
- 调用poster功能: RunScript(special://skin/scripts/favjump.py, poster)
"""

import xbmc
import xbmcgui
import sys
import time

def log(message):
    """一个简单的日志记录函数，方便调试"""
    xbmc.log(f"[favjump.py] {message}", level=xbmc.LOGINFO)

def main():
    """脚本主执行函数"""
    if len(sys.argv) > 1:
        param = sys.argv[1]
        log(f"接收到参数: {param}")

        if param == "favpage":
            # --- 处理 "favpage" 参数 (已修改) ---
            log("开始处理 'favpage' 请求...")
            
            # 【修改点】1. 在脚本内部获取 ListItem.FolderPath 的值
            folder_path = xbmc.getInfoLabel("ListItem.FolderPath")
            log(f"成功获取到 ListItem.FolderPath: '{folder_path}'")

            # 检查路径是否为空，避免执行无效命令
            if folder_path:
                # 【修改点】2. 使用f-string将获取到的路径字符串动态拼接进命令中
                # 并用引号包裹路径，防止路径中包含空格等特殊字符时出错
                activate_command = f'ActivateWindow(Videos,"{folder_path}",return)'
                
                log("执行窗口关闭和激活操作...")
                xbmc.executebuiltin("Dialog.Close(all)")
                xbmc.executebuiltin(activate_command) # 执行拼接好的命令
                xbmc.executebuiltin("Skin.SetString(favjump,1)")
                log("'favpage' 操作执行完毕。")
            else:
                log("错误: 获取到的 ListItem.FolderPath 为空，无法执行 ActivateWindow。")

        elif param == "poster":
            # --- 处理 "poster" 参数 (逻辑不变) ---
            log("开始处理 'poster' 请求...")
            
            delay = 0.2
            log(f"延时 {delay} 秒，等待视频加载...")
            time.sleep(delay)

            has_media = xbmc.getInfoLabel("Player.HasMedia").lower() == "true"
            log(f"延时后检查播放器状态 - HasMedia: {has_media}")

            if not has_media:
                log("播放器未加载媒体，激活全屏海报窗口 (ID 1119)。")
                xbmc.executebuiltin("ActivateWindow(1119)")
            
            xbmc.executebuiltin("Skin.SetString(favjump,0)")
            log("'poster' 操作执行完毕。")

        else:
            log(f"错误: 收到未知参数 '{param}'")
    else:
        log("错误: 未提供任何参数。")

if __name__ == "__main__":
    main()