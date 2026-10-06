import xbmc
import xbmcvfs
import os

def main():
    # 定义路径 - 使用 xbmcvfs.translatePath 替代 xbmc.translatePath
    skin_script_path = xbmcvfs.translatePath('special://skin/scripts/playerstreams.py')
    addon_lib_path = xbmcvfs.translatePath('special://home/addons/script.skinvariables/resources/lib/lists/playerstreams.py')
    
    # 检查addon_lib_path文件是否存在
    if not xbmcvfs.exists(addon_lib_path):
        xbmc.log("Addon file does not exist: {}".format(addon_lib_path), level=xbmc.LOGINFO)
        # 不退出，继续执行后续操作
    else:
        # 读取addon_lib_path文件的第一行
        try:
            with xbmcvfs.File(addon_lib_path, 'r') as file:
                first_line = file.readBytes().decode('utf-8').split('\n')[0]
        except Exception as e:
            xbmc.log("Error reading file {}: {}".format(addon_lib_path, str(e)), level=xbmc.LOGERROR)
            return
        
        # 检查第一行是否包含"Minsk"
        if "Minsk-R2" in first_line:
            xbmc.log("File already contains 'Minsk', exiting script")
            return

    # 检查皮肤脚本文件是否存在
    if not xbmcvfs.exists(skin_script_path):
        xbmc.log("Skin script file does not exist: {}".format(skin_script_path), level=xbmc.LOGERROR)
        return
    
    # 复制皮肤脚本文件到addon目录
    try:
        # 读取源文件
        with xbmcvfs.File(skin_script_path, 'r') as src_file:
            content = src_file.readBytes().decode('utf-8')
        
        # 写入目标文件
        with xbmcvfs.File(addon_lib_path, 'w') as dst_file:
            dst_file.write(content.encode('utf-8'))
            
        xbmc.log("Successfully copied {} to {}".format(skin_script_path, addon_lib_path))
    except Exception as e:
        xbmc.log("Error copying file: {}".format(str(e)), level=xbmc.LOGERROR)
        return
    
    # 设置皮肤字符串变量
    xbmc.executebuiltin('Skin.SetString(zysort,1)')
    xbmc.log("Set skin string zysort to 1")

if __name__ == '__main__':
    main()