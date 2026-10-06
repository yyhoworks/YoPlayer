#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoreELEC/Kodi 专用R4更新脚本（增强版）
功能：
1. 更新数据库中的视频版本类型 (update模式)
2. [新增] 在update模式下，同步检查并安装匹配内核版本的中文语言包
3. 手动触发语言包匹配与更新 (manaul模式)
"""
import xbmc
import xbmcvfs
import xbmcgui
import sys
import os
import sqlite3
import zipfile
import shutil

# 版本类型映射字典
VERSION_TYPE_MAPPING = {
    'standard edition': '标准版', 'extended edition': '加长版',
    'unrated version': '未分级版', 'uncut version': '未删减版',
    'remastered version': '重制版', 'theatrical cut': '剧场版',
    'director\'s cut': '导演剪辑版', 'special edition': '特别版',
    'limited edition': '限量版', 'complete edition': '完整版',
    'the final cut': '最终剪辑版', 'super duper cut': '超级剪辑版',
    'collector\'s edition': '收藏家版', 'ultimate collector\'s edition': '终极收藏家版',
    'criterion collection edition': '标准收藏版', 'fan edit': '粉丝剪辑版',
    'black and white edition': '黑白版', '10th anniversary edition': '10周年纪念版',
    '20th anniversary edition': '20周年纪念版', '25th anniversary edition': '25周年纪念版',
    '30th anniversary edition': '30周年纪念版', '40th anniversary edition': '40周年纪念版',
    '50th anniversary edition': '50周年纪念版'
}

def log(message, level=xbmc.LOGINFO):
    """日志函数"""
    prefix = "[R4.py] "
    timestamp = xbmc.getInfoLabel('System.Time(HH:MM:SS)')
    xbmc.log(f"{prefix}[{timestamp}] {message}", level)

def update_video_version_types(db_path):
    """更新数据库中的视频版本类型"""
    if not xbmcvfs.exists(db_path): 
        log(f"数据库文件不存在: {db_path}", xbmc.LOGERROR)
        return False
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM videoversiontype")
    updated = False
    for rid, name in cursor.fetchall():
        if name:
            lower_name = name.lower().strip()
            if lower_name in VERSION_TYPE_MAPPING:
                new_name = VERSION_TYPE_MAPPING[lower_name]
                if name != new_name:
                    cursor.execute("UPDATE videoversiontype SET name=? WHERE id=?", (new_name, rid))
                    updated = True
    if updated: 
        conn.commit()
    conn.close()
    return updated

def extract_kernel_version(build_date_str):
    """
    从BuildDate字符串中提取内核版本
    格式示例: "avdvplus-内核版本-20260904"
    返回: 内核版本字符串, 如果提取失败返回 None
    """
    if not build_date_str:
        return None
    parts = build_date_str.split('-')
    # 假设格式固定为 prefix-kernel-date，取中间部分
    if len(parts) >= 2:
        return parts[1]
    return build_date_str

def sync_language_package_by_kernel(kernel_version):
    """
    核心逻辑：根据内核版本同步语言包
    1. 检查 strings.po 第一行是否包含 kernel_version
    2. 如果不包含，查找 special://skin/language/ 下匹配的 zip
    3. 解压覆盖并提示重启
    4. 始终更新 Skin.String(langversion)
    """
    log(f"开始同步语言包，目标内核版本: '{kernel_version}'")
    
    po_path = xbmcvfs.translatePath("special://home/addons/resource.language.zh_cn/resources/strings.po")
    po_exists = xbmcvfs.exists(po_path)
    is_matched = False
    
    # 1. 检查现有 strings.po
    if po_exists:
        try:
            with open(po_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
            log(f"strings.po第一行: {first_line}")
            if kernel_version in first_line:
                is_matched = True
        except Exception as e:
            log(f"读取strings.po失败: {e}", xbmc.LOGERROR)
            # 读取失败视为不匹配，尝试重新安装
            is_matched = False
    else:
        log("strings.po 文件不存在，视为不匹配")

    # 2. 分支处理
    if is_matched:
        log("strings.po 已包含当前内核版本，无需更新文件。")
        # 即使文件匹配，也更新标记，确保状态一致
        xbmc.executebuiltin(f'Skin.SetString(langversion,{kernel_version})')
        return

    # 如果不匹配，开始查找 Zip 包
    log("strings.po 不匹配，开始查找语言包 Zip...")
    
    lang_dir = xbmcvfs.translatePath("special://skin/language/")
    target_zip = None
    latest_time = 0
    
    if xbmcvfs.exists(lang_dir):
        try:
            files = os.listdir(lang_dir)
            for f in files:
                # 寻找类似 "strings-语言包版本.zip"
                if f.startswith("strings-") and f.endswith(".zip"):
                    # 提取文件名中间的部分作为版本标识
                    pkg_ver_identifier = f[8:-4] # 去掉 "strings-" 和 ".zip"
                    
                    # 检查这个标识符是否包含内核版本
                    if kernel_version in pkg_ver_identifier:
                        f_path = os.path.join(lang_dir, f)
                        try:
                            mtime = os.path.getmtime(f_path)
                            if mtime > latest_time:
                                latest_time = mtime
                                target_zip = f_path
                        except Exception as e:
                            log(f"获取文件时间失败 {f}: {e}")
        except Exception as e:
            log(f"遍历语言包目录失败: {e}", xbmc.LOGERROR)

    # 3. 处理未找到文件的情况
    if not target_zip:
        log("未找到匹配的语言包zip文件")
        xbmc.executebuiltin(f'Skin.SetString(langversion,{kernel_version})')
        # 这里可以选择是否弹窗提示用户未找到，根据需求静默处理或提示
        # xbmcgui.Dialog().ok("提示", "未找到匹配的内核语言包")
        return

    # 4. 处理找到文件的情况：解压覆盖
    log(f"找到匹配的最新语言包: {target_zip}")
    
    try:
        # 确保目标目录存在
        po_dir = os.path.dirname(po_path)
        if not xbmcvfs.exists(po_dir):
            xbmcvfs.mkdirs(po_dir)

        with zipfile.ZipFile(target_zip, 'r') as z:
            found_po = False
            for name in z.namelist():
                # 寻找zip内的strings.po文件
                if name.endswith('strings.po'):
                    with z.open(name) as src, open(po_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    found_po = True
                    log(f"从zip中提取并覆盖: {name}")
                    break
            
            if not found_po:
                raise Exception("Zip文件中未找到strings.po")

        log("解压覆盖strings.po成功")
        xbmc.executebuiltin(f'Skin.SetString(langversion,{kernel_version})')
        
        # 弹出重启确认窗
        msg = "已按照内核版本进行了汉化，重启生效，是否现在重启？\n选择“是”立即重启，选择“否”关闭窗口。"
        if xbmcgui.Dialog().yesno("中文汉化提示", msg):
            reboot_script = xbmcvfs.translatePath("special://skin/scripts/rebootoff.py")
            xbmc.executebuiltin(f'RunScript({reboot_script},noask)')
            log("用户选择立即重启")
        else:
            log("用户选择暂不重启")
            
    except Exception as e:
        log(f"解压或设置过程发生异常: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"汉化过程中发生错误: {str(e)}")

def manual_mode():
    """
    手动模式逻辑：
    1. 获取BuildDate并提取内核版本
    2. 检查strings.po第一行是否匹配
    3. 根据匹配结果和用户选择执行相应操作
    """
    log("进入手动模式 (manaul)")
    
    # 1. 获取BuildDate并提取内核版本
    build_date = xbmc.getInfoLabel('Skin.String(BuildDate)')
    log(f"获取到的BuildDate: {build_date}")
    
    kernel_version = extract_kernel_version(build_date)
    if not kernel_version:
        log("无法提取内核版本", xbmc.LOGERROR)
        return

    log(f"提取的内核版本: {kernel_version}")

    # 2. 检查strings.po第一行
    po_path = xbmcvfs.translatePath("special://home/addons/resource.language.zh_cn/resources/strings.po")
    first_line = ""
    po_exists = xbmcvfs.exists(po_path)
    is_matched = False
    
    if po_exists:
        try:
            with open(po_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
            log(f"strings.po第一行内容: {first_line}")
            # 判断是否包含内核版本
            if kernel_version in first_line:
                is_matched = True
        except Exception as e:
            log(f"读取strings.po失败: {e}", xbmc.LOGERROR)
            po_exists = False 

    # 3. 分支处理
    if is_matched:
        # 情况1：包含内核版本字符
        log("strings.po已包含当前内核版本")
        
        # 弹出确认窗口
        msg = "当前中文包与内核匹配，是否强制安装中文包？\n选择“是”则强制安装中文包，选择“否”退出。"
        if xbmcgui.Dialog().yesno("中文汉化提示", msg):
            # 用户选择“是”，继续执行安装流程
            log("用户选择强制安装，开始查找语言包...")
            sync_language_package_by_kernel(kernel_version)
        else:
            # 用户选择“否”，退出脚本
            log("用户选择不强制安装，退出脚本")
            # 即使不安装，也更新一下langversion标记，保持一致性
            xbmc.executebuiltin(f'Skin.SetString(langversion,{kernel_version})')
            return
    else:
        # 情况2：不包含内核版本字符
        log("strings.po不包含当前内核版本，开始查找语言包...")
        sync_language_package_by_kernel(kernel_version)

def main():
    """主函数：脚本入口"""
    log("脚本启动")
    
    # 检查参数
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    has_manual = any("manaul" in arg for arg in args)
    has_update = any("update" in arg for arg in args)

    try:
        if has_manual:
            manual_mode()
        elif has_update:
            log("检测到update参数，开始更新流程")
            
            # 1. 执行数据库版本类型更新
            db_path = xbmcvfs.translatePath("special://userdata/Database/MyVideos131.db")
            log("开始执行数据库版本类型更新...")
            update_video_version_types(db_path)
            log("数据库更新完成")
            
            # 2. [新增] 执行语言包同步逻辑
            log("开始执行语言包同步检查...")
            build_date = xbmc.getInfoLabel('Skin.String(BuildDate)')
            kernel_version = extract_kernel_version(build_date)
            
            if kernel_version:
                sync_language_package_by_kernel(kernel_version)
            else:
                log("无法获取BuildDate或内核版本，跳过语言包同步", xbmc.LOGWARNING)
                
        else:
            log("未传入有效参数 (manaul 或 update)，脚本退出", xbmc.LOGWARNING)
            
    except Exception as e:
        log(f"脚本执行异常: {str(e)}", xbmc.LOGERROR)
        
    log("脚本结束")

if __name__ == "__main__":
    main()