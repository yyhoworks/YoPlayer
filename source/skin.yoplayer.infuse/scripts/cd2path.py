import xbmc
import xbmcgui
import xbmcvfs
import sys
import os
import time

def is_directory_not_empty(path):
    """检查目录是否存在且不为空"""
    if not path:
        return False
    
    if not path.endswith('/'):
        path += '/'
        
    exists = xbmcvfs.exists(path)
    
    if not exists:
        return False
        
    dirs, files = xbmcvfs.listdir(path)
    total_items = len(dirs) + len(files)
    
    return total_items > 0

def wait_for_file_browser_close():
    """等待文件浏览器窗口关闭"""
    # 1. 等待窗口出现
    wait_appear_count = 0
    while not xbmc.getCondVisibility("Window.IsActive(filebrowser)"):
        xbmc.sleep(100)
        wait_appear_count += 1
        if wait_appear_count > 50: # 超时5秒
            break
            
    # 2. 等待窗口关闭
    wait_close_count = 0
    while xbmc.getCondVisibility("Window.IsActive(filebrowser)"):
        xbmc.sleep(100)
        wait_close_count += 1
        if wait_close_count > 300: # 超时30秒
            break

def main():
    # 获取启动参数
    is_home_mode = len(sys.argv) > 1 and sys.argv[1] == 'home'

    # 检查当前设置的路径是否有效
    current_path = xbmc.getInfoLabel('Skin.String(cd2path)')
    
    path_valid = False
    
    if current_path and is_directory_not_empty(current_path):
        path_valid = True
    else:
        path_valid = False

    final_target_path = None
    
    if path_valid:
        # 如果当前路径有效，Home模式下直接使用，配置模式下直接退出
        final_target_path = current_path
        if is_home_mode:
            xbmc.executebuiltin(f'ActivateWindow(Videos,{final_target_path},return)')
            return
        else:
            return
    else:
        # 当前路径无效，需要寻找新路径
        if is_home_mode:
            pass
        else:
            pass

        # 尝试预设路径
        preset_paths = [
            "/storage/videos/CloudNAS/CloudDrive",
            "/storage/CloudNAS/CloudDrive",
            "/storage/CloudDrive"
        ]
        
        found_preset = False
        for preset_path in preset_paths:
            if is_directory_not_empty(preset_path):
                final_target_path = preset_path
                found_preset = True
                
                # 如果是配置模式，需要写入设置
                if not is_home_mode:
                    xbmc.executebuiltin(f'Skin.SetString(cd2path,{preset_path})')
                    xbmc.sleep(200) 
                break
        
        if not found_preset:
            # 预设都无效，进入手动选择流程
            if is_home_mode:
                pass
            else:
                pass

            # 弹出确认窗 - 根据是否为home模式显示不同内容
            if is_home_mode:
                dialog_text = "未找到您的挂载网盘文件夹，点击\"是\"则手动指定挂载的网盘文件夹，点击\"否\"则关闭该窗口。"
            else:
                dialog_text = "未找到您的挂载网盘文件夹，点击\"是\"则手动指定挂载的网盘文件夹，点击\"否\"则永久关闭开机检测挂载路径功能。"

            choice = xbmcgui.Dialog().yesno(
                "CD2PATH", 
                dialog_text
            )
            
            if choice:
                xbmc.executebuiltin('Skin.SetPath(cd2path)')
                
                # 监测窗口关闭
                wait_for_file_browser_close()
                
                # 延时0.5秒
                xbmc.sleep(500)
                
                # 检查值
                new_path = xbmc.getInfoLabel('Skin.String(cd2path)')
                
                if not new_path:
                    return
                else:
                    xbmcgui.Dialog().ok("CD2PATH", f'已将主页面网盘路径设置为"{new_path}"!')
                    return
            else:
                # 根据运行模式决定后续行为
                if is_home_mode:
                    # Home模式下选择"否"，直接退出
                    return
                else:
                    # 配置模式下选择"否"，根据checkcd2path设置状态执行不同操作
                    has_check_setting = xbmc.getCondVisibility('!Skin.HasSetting(checkcd2path)')
                    
                    if has_check_setting:
                        # !Skin.HasSetting(checkcd2path) 为真，执行切换设置
                        xbmc.executebuiltin('Skin.ToggleSetting(checkcd2path)')
                    
                    # 弹出确认窗口
                    xbmcgui.Dialog().ok(
                        "CD2PATH", 
                        "已关闭开机检测挂载路径功能，如需重新打开，请在设置-皮肤设置-常规页面，打开\"启用开机检测挂载网盘路径\"选项!"
                    )
                    
                    # 退出脚本
                    return

    # 如果找到了有效路径 (无论是预设的还是原有的)，且是Home模式，执行跳转
    if is_home_mode and final_target_path:
        xbmc.executebuiltin(f'ActivateWindow(Videos,{final_target_path},return)')

if __name__ == '__main__':
    main()