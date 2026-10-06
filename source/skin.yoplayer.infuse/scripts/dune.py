import os
import xbmc
import xbmcgui
import xbmcvfs
import subprocess

def is_coreelec():
    """检测当前系统是否为CoreELEC"""
    try:
        if xbmcvfs.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                content = f.read().lower()
                if "coreelec" in content:
                    return True
        
        if xbmcvfs.exists("/storage/.kodi") and xbmcvfs.exists("/flash"):
            return True
            
        return False
    except Exception as e:
        xbmc.log(f"系统检测错误: {str(e)}", xbmc.LOGERROR)
        return False

def get_kodi_keymaps_path():
    """获取Kodi的keymaps文件夹路径"""
    try:
        keymaps_path = xbmcvfs.translatePath("special://userdata/keymaps/")
        if not xbmcvfs.exists(keymaps_path):
            xbmcvfs.mkdirs(keymaps_path)
            xbmc.log(f"创建keymaps目录: {keymaps_path}", xbmc.LOGINFO)
        return keymaps_path
    except Exception as e:
        raise Exception(f"获取Kodi keymaps路径失败: {str(e)}")

def get_hwdb_path():
    """获取hwdb.d文件夹路径"""
    try:
        hwdb_path = "/storage/.config/hwdb.d/"
        if not xbmcvfs.exists(hwdb_path):
            xbmcvfs.mkdirs(hwdb_path)
            xbmc.log(f"创建hwdb.d目录: {hwdb_path}", xbmc.LOGINFO)
        return hwdb_path
    except Exception as e:
        raise Exception(f"获取hwdb.d路径失败: {str(e)}")

def get_skin_extras_ur02_path():
    """使用 special://home 路径获取ur02文件夹"""
    try:
        src_dir = xbmcvfs.translatePath("special://home/addons/skin.yoplayer.infuse/extras/dune")
        
        if not xbmcvfs.exists(src_dir) and not os.path.exists(src_dir):
            raise Exception(f"源目录不存在: {src_dir}")
            
        return src_dir
    except Exception as e:
        raise Exception(f"获取extras/zidoo路径失败: {str(e)}")

def set_flash_writable():
    """将 /flash 挂载为可读写"""
    try:
        xbmc.log("尝试将 /flash 重新挂载为可读写", xbmc.LOGINFO)
        result = subprocess.run(
            ["mount", "-o", "remount,rw", "/flash"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"挂载 /flash 为可写失败: {result.stderr}")
        xbmc.log("/flash 已设置为可读写", xbmc.LOGINFO)
        return True
    except Exception as e:
        raise Exception(f"处理 /flash 权限时出错: {str(e)}")

def copy_files(source_dir):
    """复制文件到目标位置"""
    try:
        keymaps_dir = get_kodi_keymaps_path()
        hwdb_dir = get_hwdb_path()
        flash_dir = "/flash/"
        
        file_operations = [
            ("gen.xml", keymaps_dir),
            ("dune.hwdb", hwdb_dir)
        ]
        
        failed = []
        
        if any(op[1] == flash_dir for op in file_operations):
            set_flash_writable()
        
        for file_name, target_dir in file_operations:
            source_path = os.path.join(source_dir, file_name)
            target_path = os.path.join(target_dir, file_name)
            
            try:
                if not xbmcvfs.copy(source_path, target_path):
                    failed.append(f"{file_name} (复制操作返回失败)")
            except Exception as e:
                failed.append(f"{file_name} (错误: {str(e)})")
        
        return failed
    except Exception as e:
        raise Exception(f"文件复制过程出错: {str(e)}")

def main():
    if not is_coreelec():
        xbmcgui.Dialog().ok("系统不支持", "此脚本仅适用于CoreELEC系统！")
        return
    
    if not xbmcgui.Dialog().yesno(
        "确认操作", 
        "此设置将执行以下操作：\n"
        "将CoreELEC系统适配DUNE杜恩遥控器按键设置\n"
        "是否继续？"
    ):
        xbmcgui.Dialog().ok("已取消", "操作已取消")
        return
    
    try:
        source_dir = get_skin_extras_ur02_path()
        failed = copy_files(source_dir)
        
        if not failed:
            # 直接执行重载键位映射，不再弹出重启确认窗
            xbmc.executebuiltin('action(reloadkeymaps)')
            xbmcgui.Dialog().ok("适配完成", "适配已完成，DUNE杜恩遥控器配置已生效。")
        else:
            xbmcgui.Dialog().ok("部分失败", "以下操作失败：\n" + "\n".join(failed))
        
    except Exception as e:
        xbmcgui.Dialog().ok("错误", str(e))
        xbmc.log(f"UR02配置复制脚本错误: {str(e)}", xbmc.LOGERROR)

if __name__ == "__main__":
    main()