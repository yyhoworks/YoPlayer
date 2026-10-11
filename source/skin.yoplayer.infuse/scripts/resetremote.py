import os
import time
import xbmc
import xbmcgui
import xbmcvfs

def log(msg):
    """统一日志输出格式"""
    xbmc.log(f"[ResetRemote] {msg}", xbmc.LOGINFO)

def clear_folder(path):
    """清空指定文件夹下的所有文件"""
    try:
        if path.startswith('special://'):
            if hasattr(xbmcvfs, 'translatePath'):
                translated_path = xbmcvfs.translatePath(path)
            else:
                translated_path = xbmc.translatePath(path)
        else:
            translated_path = path
            
        if xbmcvfs.exists(translated_path):
            dirs, files = xbmcvfs.listdir(translated_path)
            log(f"Clearing {len(files)} files in {path}")
            for f in files:
                file_path = os.path.join(translated_path, f)
                xbmcvfs.delete(file_path)
        else:
            log(f"Path does not exist: {path}")
    except Exception as e:
        log(f"Error clearing {path}: {e}")

# --- 主程序开始 ---
log("Script started.")

# 1. 删除文件
clear_folder('special://userdata/keymaps/')
clear_folder('/storage/.config/hwdb.d/')

# 2. 重置 Skin 设置
remotes = [
    '6bur02remote', '6bur02R1', 'zidoov12', 'zidoov10', 'g20pro',
    'dune', 'huaweir22', 'CMCC2remote', 'mx3remote', 'CMBremote'
]

for remote in remotes:
    condition = f'Skin.HasSetting({remote})'
    if xbmc.getCondVisibility(condition):
        log(f"Toggling off: {remote}")
        xbmc.executebuiltin(f'Skin.ToggleSetting({remote})')

# 3. 弹窗确认
dialog = xbmcgui.Dialog()
heading = "提示"
message = "已重置遥控器配置文件，需要重新选择预设遥控器，重启后生效。\n选择“是”弹出预设遥控器选择窗口，选择“否”则稍后自行选择。"

user_choice = dialog.yesno(heading, message)
log(f"User choice from yesno dialog: {user_choice}")

if user_choice:
    # 4. 执行 SelectBool（皮肤选择弹窗期间显示遥控器图鉴配图）
    select_cmd = "Skin.SelectBool(31408, 31457|mx3remote, 31409|CMBremote, 31456|CMCC2remote, 31410|6bur02remote, 31451|6bur02R1, 31419|zidoov12, 31428|zidoov10, 31429|dune, 31424|g20pro, 31452|huaweir22)"
    log(f"Executing SelectBool: {select_cmd}")
    xbmc.executebuiltin('Skin.SetString(YoPlayer.RemoteGuide,1)')
    xbmc.executebuiltin(select_cmd)
    
    # 5. 【关键修改】使用轮询机制等待用户选择
    # 设置最大等待时间（例如 30 秒），避免无限循环
    max_wait_time = 30
    start_time = time.time()
    found_selection = False
    
    script_mapping = {
        'mx3remote': 'cmbremote.py',
        'CMBremote': 'cmbremote.py',
        'CMCC2remote': 'cmcc2remote.py',
        '6bur02remote': '6bur02remote.py',
        '6bur02R1': '6bur02R1.py',
        'zidoov12': 'zidoov12.py',
        'zidoov10': 'zidoov10.py',
        'g20pro': 'g20pro.py',
        'dune': 'dune.py',
        'huaweir22': 'R22.py'
    }
    
    log("Start polling for user selection...")
    
    while (time.time() - start_time) < max_wait_time:
        # 每 0.5 秒检查一次
        time.sleep(0.5)
        
        for setting_name, script_file in script_mapping.items():
            if xbmc.getCondVisibility(f'Skin.HasSetting({setting_name})'):
                log(f"Detected selection: {setting_name}")
                log(f"Executing: RunScript(special://skin/scripts/{script_file})")
                xbmc.executebuiltin(f'RunScript(special://skin/scripts/{script_file})')
                found_selection = True
                break
        
        if found_selection:
            break

    xbmc.executebuiltin('Skin.SetString(YoPlayer.RemoteGuide,0)')
    if not found_selection:
        log("Timeout or no selection made. Exiting.")
else:
    log("User selected No. Exiting.")

log("Script finished.")