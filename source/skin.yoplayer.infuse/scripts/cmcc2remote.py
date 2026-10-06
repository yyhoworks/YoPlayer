import os
import xbmc
import xbmcgui
import xbmcvfs
import subprocess

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

def get_cmbremote_source_path():
    """获取cmbremote文件夹路径"""
    try:
        src_dir = xbmcvfs.translatePath("special://home/addons/skin.yoplayer.infuse/extras/cmcc2")
        
        if not xbmcvfs.exists(src_dir) and not os.path.exists(src_dir):
            raise Exception(f"源目录不存在: {src_dir}")
            
        return src_dir
    except Exception as e:
        raise Exception(f"获取cmbremote路径失败: {str(e)}")

def check_source_files(source_dir):
    """检查cmbremote目录下必要文件是否存在"""
    required_files = [
        os.path.join(source_dir, "gen.xml"),
        os.path.join(source_dir, "cmcc2.hwdb"),
        os.path.join(source_dir, "remote.conf")
    ]
    
    missing = [f for f in required_files if not xbmcvfs.exists(f) and not os.path.exists(f)]
    
    if missing:
        raise Exception(f"缺少必要的源文件:\n" + "\n".join(missing))

def copy_and_clean_files(source_dir):
    """复制gen.xml到keymaps，复制CMCC.hwdb到hwdb.d，复制remote.conf到/flash（处理/flash读写权限）"""
    try:
        keymaps_dir = get_kodi_keymaps_path()
        hwdb_dir = "/storage/.config/hwdb.d/"
        flash_dir = "/flash/"
        
        failed = []
        
        # 1. 复制 gen.xml 到 keymaps 目录
        gen_src = os.path.join(source_dir, "gen.xml")
        gen_dst = os.path.join(keymaps_dir, "gen.xml")
        try:
            if not xbmcvfs.copy(gen_src, gen_dst):
                failed.append(f"gen.xml (复制操作返回失败)")
        except Exception as e:
            failed.append(f"gen.xml (错误: {str(e)})")
        
        # 2. 删除 keymaps 目录下的 keyboard.xml
        keyboard_path = os.path.join(keymaps_dir, "keyboard.xml")
        try:
            if xbmcvfs.exists(keyboard_path) and not xbmcvfs.delete(keyboard_path):
                failed.append(f"删除 keyboard.xml 失败")
        except Exception as e:
            failed.append(f"删除 keyboard.xml 错误: {str(e)}")
        
        # 3. 复制 CMCC.hwdb 到 hwdb.d 目录
        cmcc_src = os.path.join(source_dir, "cmcc2.hwdb")
        cmcc_dst = os.path.join(hwdb_dir, "cmcc2.hwdb")
        try:
            if not xbmcvfs.exists(hwdb_dir):
                xbmcvfs.mkdirs(hwdb_dir)
            
            if not xbmcvfs.copy(cmcc_src, cmcc_dst):
                failed.append(f"cmcc2.hwdb (复制操作返回失败)")
        except Exception as e:
            failed.append(f"cmcc2.hwdb (错误: {str(e)})")
        
        # 4. 复制 remote.conf 到 /flash 目录（先处理/flash读写权限）
        remote_src = os.path.join(source_dir, "remote.conf")
        remote_dst = os.path.join(flash_dir, "remote.conf")
        try:
            # 检查/flash是否存在
            if not xbmcvfs.exists(flash_dir):
                xbmcvfs.mkdirs(flash_dir)
                xbmc.log(f"创建/flash目录: {flash_dir}", xbmc.LOGINFO)
            
            # 将/flash重新挂载为可读写模式（CoreELEC默认只读）
            mount_cmd = ["mount", "-o", "remount,rw", "/flash"]
            result = subprocess.run(mount_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"挂载/flash为可读写失败: {result.stderr}")
            xbmc.log("/flash已挂载为可读写模式", xbmc.LOGINFO)
            
            # 复制remote.conf到/flash
            if not xbmcvfs.copy(remote_src, remote_dst):
                failed.append(f"remote.conf (复制到/flash失败)")
            else:
                xbmc.log(f"remote.conf已复制到: {remote_dst}", xbmc.LOGINFO)
            
            # 复制完成后，将/flash恢复为只读模式
            umount_cmd = ["mount", "-o", "remount,ro", "/flash"]
            result = subprocess.run(umount_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                xbmc.log(f"恢复/flash为只读失败: {result.stderr}", xbmc.LOGWARNING)
                failed.append(f"remote.conf (复制成功，但恢复/flash只读模式失败)")
            else:
                xbmc.log("/flash已恢复为只读模式", xbmc.LOGINFO)
        
        except Exception as e:
            failed.append(f"remote.conf (错误: {str(e)})")
        
        return failed
    except Exception as e:
        raise Exception(f"文件操作过程出错: {str(e)}")

def main():
    if not xbmcgui.Dialog().yesno(
        "确认操作", 
        "此设置将执行以下操作：\n"
        
        "将CoreELEC系统适配中国移动遥控器2.4G(适用于确认键无效版)按键设置\n"
       
        "是否继续？"
    ):
        xbmcgui.Dialog().ok("已取消", "操作已取消")
        return
    
    try:
        source_dir = get_cmbremote_source_path()
        check_source_files(source_dir)  # 检查源文件是否齐全
        
        failed = copy_and_clean_files(source_dir)
        
        if not failed:
            # 执行重新加载按键映射
            xbmc.executebuiltin('action(reloadkeymaps)')
            xbmcgui.Dialog().ok("适配完成", "适配已完成，中国移动遥控器2.4G(适用于确认键无效版)配置已生效。")
        else:
            # 有错误
            xbmcgui.Dialog().ok("部分失败", "以下操作失败：\n" + "\n".join(failed))
        
    except Exception as e:
        xbmcgui.Dialog().ok("错误", str(e))
        xbmc.log(f"CMBRemote配置脚本错误: {str(e)}", xbmc.LOGERROR)

if __name__ == "__main__":
    main()