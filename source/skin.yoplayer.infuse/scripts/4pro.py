
import os
import xbmc
import xbmcgui
import xbmcvfs
import subprocess
import hashlib

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
        src_dir = xbmcvfs.translatePath("special://home/addons/skin.yoplayer.infuse/extras/4pro")
        
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

def calculate_file_hash(file_path):
    """计算文件的哈希值"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # 分块读取文件以处理大文件
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        raise Exception(f"计算文件哈希值失败: {str(e)}")

def compare_hwdb_files(source_dir, hwdb_dir):
    """
    比较源目录中的4pro.hwdb文件和目标目录中的同名文件
    返回值: (need_copy, is_first_time)
    need_copy: 是否需要复制文件
    is_first_time: 是否是首次配置（目标文件不存在或内容不同）
    """
    source_hwdb_path = os.path.join(source_dir, "4pro.hwdb")
    target_hwdb_path = os.path.join(hwdb_dir, "4pro.hwdb")
    
    # 检查目标文件是否存在
    if not xbmcvfs.exists(target_hwdb_path):
        return True, True  # 需要复制，首次配置
    
    # 计算源文件和目标文件的哈希值进行比较
    source_hash = calculate_file_hash(source_hwdb_path)
    target_hash = calculate_file_hash(target_hwdb_path)
    
    if source_hash != target_hash:
        return True, True  # 需要复制，首次配置（内容不同）
    else:
        return False, False  # 不需要复制，非首次配置

def copy_files(source_dir, check_hwdb_content=True):
    """复制文件到目标位置"""
    try:
        keymaps_dir = get_kodi_keymaps_path()
        hwdb_dir = get_hwdb_path()
        flash_dir = "/flash/"
        
        # 如果需要检查hwdb文件内容
        need_copy_hwdb = True
        is_first_time_config = False
        if check_hwdb_content:
            need_copy_hwdb, is_first_time_config = compare_hwdb_files(source_dir, hwdb_dir)
        
        file_operations = [
            ("gen.xml", keymaps_dir)
        ]
        
        # 根据比较结果决定是否添加hwdb文件到复制列表
        if need_copy_hwdb:
            file_operations.append(("4pro.hwdb", hwdb_dir))
        
        failed = []
        
        if any(op[1] == flash_dir for op in file_operations):
            set_flash_writable()
        
        for file_name, target_dir in file_operations:
            source_path = os.path.join(source_dir, file_name)
            target_path = os.path.join(target_dir, file_name)
            
            try:
                if not xbmcvfs.copy(source_path, target_path):
                    failed.append(f"{file_name} (复制操作返回失败)")
                else:
                    xbmc.log(f"成功复制文件: {source_path} -> {target_path}", xbmc.LOGINFO)
            except Exception as e:
                failed.append(f"{file_name} (错误: {str(e)})")
        
        return failed, is_first_time_config
    except Exception as e:
        raise Exception(f"文件复制过程出错: {str(e)}")

def main():
    if not is_coreelec():
        xbmcgui.Dialog().ok("系统不支持", "此脚本仅适用于CoreELEC系统！")
        return
    
    if not xbmcgui.Dialog().yesno(
        "确认操作", 
        "此设置将执行以下操作：\n"
        "将CoreELEC系统适配腾讯极光4pro遥控器按键设置\n"
        "是否继续？"
    ):
        xbmcgui.Dialog().ok("已取消", "操作已取消")
        return
    
    try:
        source_dir = get_skin_extras_ur02_path()
        failed, is_first_time_config = copy_files(source_dir)
        
        if not failed:
            # 如果不是首次配置，按原逻辑执行
            if not is_first_time_config:
                xbmc.executebuiltin('action(reloadkeymaps)')
                xbmcgui.Dialog().ok("适配完成", "适配已完成，腾讯极光4pro遥控器配置已生效。")
            else:
                # 如果是首次配置，显示新的提示对话框
                reboot_choice = xbmcgui.Dialog().yesno(
                    "适配完成", 
                    "适配已完成，但检测到您首次适配腾讯极光4pro遥控器，需要重启后才能生效，点击\"是\"立即重启！点击\"否\"请稍后手动重启！"
                )
                
                if reboot_choice:
                    # 用户选择立即重启
                    xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,noask)')
                else:
                    # 用户选择稍后重启，直接退出
                    return
        else:
            xbmcgui.Dialog().ok("部分失败", "以下操作失败：\n" + "\n".join(failed))
        
    except Exception as e:
        xbmcgui.Dialog().ok("错误", str(e))
        xbmc.log(f"华为R22配置复制脚本错误: {str(e)}", xbmc.LOGERROR)

if __name__ == "__main__":
    main()
