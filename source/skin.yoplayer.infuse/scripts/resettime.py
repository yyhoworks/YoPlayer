import xbmc
import xbmcgui
import os
import re
import shutil

# 定义文件路径
USERDATA_DIR = '/storage/.kodi/userdata'
RESOURCE_DIR = '/storage/.resource'
GUISETTINGS_SRC = os.path.join(USERDATA_DIR, 'guisettings.xml')
GUISETTINGS_BAK = os.path.join(RESOURCE_DIR, 'guisettings.xml')
AUTOSTART_FILE = '/storage/.config/autostart.sh'

def show_dialog(header, message):
    """显示 Kodi 对话框"""
    dialog = xbmcgui.Dialog()
    return dialog.yesno(header, message)

def modify_guisettings():
    """备份并修改 guisettings.xml"""
    # 确保资源目录存在
    if not os.path.exists(RESOURCE_DIR):
        os.makedirs(RESOURCE_DIR)
    
    # 复制文件
    if os.path.exists(GUISETTINGS_SRC):
        shutil.copy2(GUISETTINGS_SRC, GUISETTINGS_BAK)
    else:
        xbmc.log("Error: guisettings.xml not found!", level=xbmc.LOGERROR)
        return False

    # 读取并修改内容
    try:
        # 显式指定 utf-8 编码读取
        with open(GUISETTINGS_BAK, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则替换 systemtotaluptime 的值
        # 匹配 <systemtotaluptime>任意内容</systemtotaluptime> 并替换为 1
        new_content = re.sub(r'<systemtotaluptime>.*?</systemtotaluptime>', '<systemtotaluptime>1</systemtotaluptime>', content, flags=re.DOTALL)
        
        # 显式指定 utf-8 编码写入
        with open(GUISETTINGS_BAK, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return True
    except Exception as e:
        xbmc.log(f"Error modifying guisettings.xml: {str(e)}", level=xbmc.LOGERROR)
        return False

def setup_autostart():
    """配置 autostart.sh 以在下次启动时恢复文件并清理自身"""
    
    # 定义要在 autostart.sh 中执行的 shell 命令
    restore_script = f"""
# --- START RESET TIME RESTORE ---
if [ -f "{GUISETTINGS_BAK}" ]; then
    cp -f "{GUISETTINGS_BAK}" "{GUISETTINGS_SRC}"
    rm -f "{GUISETTINGS_BAK}"
fi
# Remove this block from autostart.sh after execution
sed -i '/# --- START RESET TIME RESTORE ---/,/# --- END RESET TIME RESTORE ---/d' "{AUTOSTART_FILE}"
# --- END RESET TIME RESTORE ---
"""

    try:
        # 如果 autostart.sh 不存在，创建一个空的
        if not os.path.exists(AUTOSTART_FILE):
            # 创建时指定 utf-8
            with open(AUTOSTART_FILE, 'w', encoding='utf-8') as f:
                f.write("#!/bin/sh\n")
            os.chmod(AUTOSTART_FILE, 0o755)
        
        # 读取现有内容 - 关键修复点：指定 encoding='utf-8'
        with open(AUTOSTART_FILE, 'r', encoding='utf-8') as f:
            existing_content = f.read()
            
        # 检查是否已经包含相同的恢复代码，避免重复添加
        if "# --- START RESET TIME RESTORE ---" not in existing_content:
            # 追加写入时指定 encoding='utf-8'
            with open(AUTOSTART_FILE, 'a', encoding='utf-8') as f:
                f.write(restore_script)
                
        # 确保有执行权限
        os.chmod(AUTOSTART_FILE, 0o755)
        
        return True
    except Exception as e:
        xbmc.log(f"Error setting up autostart.sh: {str(e)}", level=xbmc.LOGERROR)
        return False

def main():
    # 1. 弹出确认窗口
    header = "系统提示"
    message = "复位系统累计使用时间需要重启系统,是否继续?"
    
    confirmed = show_dialog(header, message)
    
    if not confirmed:
        xbmc.log("User cancelled reset time operation.", level=xbmc.LOGINFO)
        return

    # 2. 修改 guisettings.xml
    if not modify_guisettings():
        xbmcgui.Dialog().ok("错误", "修改配置文件失败!")
        return

    # 3. 设置 autostart.sh
    if not setup_autostart():
        xbmcgui.Dialog().ok("错误", "设置自动启动脚本失败!")
        return

    # 4. 执行重启脚本
    xbmc.log("Executing reboot script...", level=xbmc.LOGINFO)
    try:
        # 注意：RunScript 第一个参数是路径，第二个参数是 wait/async 等选项，这里是 noask
        # 假设 rebootoff.py 在同级目录或已知路径
        reboot_script_path = "special://skin/scripts/rebootoff.py"
        xbmc.executebuiltin(f"RunScript({reboot_script_path}, noask)")
    except Exception as e:
        xbmc.log(f"Failed to execute reboot script: {str(e)}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().ok("提示", "配置已保存，请手动重启系统以生效。")

if __name__ == "__main__":
    main()