# -*- coding: utf-8 -*-
import xbmc
import os

def get_pretty_name():
    """
    读取/etc/os-release文件中的PRETTY_NAME参数值
    返回值：提取出的PRETTY_NAME字符串（无引号），读取失败返回空字符串
    """
    pretty_name = ""
    try:
        # 以UTF-8编码打开文件，兼容不同系统字符编码
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                clean_line = line.strip()
                # 定位PRETTY_NAME行，仅分割1次避免值中含等号
                if clean_line.startswith("PRETTY_NAME="):
                    key_value = clean_line.split("=", 1)
                    if len(key_value) == 2:
                        value = key_value[1]
                        # 去除值两侧的单/双引号
                        if value.startswith(('"', "'")) and value.endswith(('"', "'")):
                            pretty_name = value[1:-1]
                        else:
                            pretty_name = value
                    break
    # 捕获文件不存在、权限不足等异常，静默处理
    except (FileNotFoundError, PermissionError, OSError, IOError):
        pass
    return pretty_name

def main():
    # 1. 获取系统PRETTY_NAME值
    system_name = get_pretty_name()
    
    # 2. 验证：读取失败/不含avdvplus则静默退出（不区分大小写）
    if not system_name or "avdvplus" not in system_name.lower():
        return
    
    # 3. 获取KODI列表项的文件路径和名称
    file_path = xbmc.getInfoLabel("ListItem.FilenameAndPath")
    
    # 4. 仅当路径长度超过300时设置皮肤字符串（值为1，无引号），否则直接退出
    if len(file_path) > 300:
        xbmc.executebuiltin('Skin.SetString(pathtl, 1)')

if __name__ == "__main__":
    main()