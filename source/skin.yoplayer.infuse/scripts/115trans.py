import xbmc
import xbmcgui
import sqlite3
import os
import time

def get_database_path():
    """获取KODI数据库路径"""
    # 使用xbmcvfs替代已弃用的translatePath
    try:
        # 尝试使用新的xbmcvfs.translatePath
        import xbmcvfs
        userdata_path = xbmcvfs.translatePath('special://userdata/')
    except AttributeError:
        # 如果新API不可用，则使用旧的xbmc.translatePath
        userdata_path = xbmc.translatePath('special://userdata/')
    
    db_path = os.path.join(userdata_path, 'Database', 'MyVideos131.db')
    return db_path

def replace_115open_to_115(db_path):
    """将115open替换为115"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有包含115open的路径（不区分大小写）
        cursor.execute("SELECT idPath, strPath FROM path WHERE LOWER(strPath) LIKE '%115open%';")
        records = cursor.fetchall()
        
        updated_count = 0
        for record in records:
            old_path = record[1]
            # 不区分大小写替换第一个匹配的115open为115
            new_path = replace_first_ignore_case(old_path, '115open', '115')
            
            if new_path != old_path:
                # 更新数据库记录
                cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (new_path, record[0]))
                updated_count += 1
        
        conn.commit()
        conn.close()
        xbmc.log(f"115open to 115 conversion completed. Updated {updated_count} records", xbmc.LOGINFO)
        return updated_count
    except Exception as e:
        xbmc.log(f"Error converting 115open to 115: {str(e)}", xbmc.LOGERROR)
        return -1

def replace_115_to_115open(db_path):
    """将115替换为115open"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有包含115但不包含115open的路径
        cursor.execute("SELECT idPath, strPath FROM path WHERE LOWER(strPath) LIKE '%115%' AND LOWER(strPath) NOT LIKE '%115open%';")
        records = cursor.fetchall()
        
        updated_count = 0
        for record in records:
            old_path = record[1]
            # 替换第一个115为115open
            new_path = old_path.replace('115', '115open', 1)
            
            if new_path != old_path:
                # 更新数据库记录
                cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (new_path, record[0]))
                updated_count += 1
        
        conn.commit()
        conn.close()
        xbmc.log(f"115 to 115open conversion completed. Updated {updated_count} records", xbmc.LOGINFO)
        return updated_count
    except Exception as e:
        xbmc.log(f"Error converting 115 to 115open: {str(e)}", xbmc.LOGERROR)
        return -1

def replace_first_ignore_case(text, old, new):
    """不区分大小写替换第一个匹配项"""
    import re
    # 使用正则表达式查找第一个匹配项（不区分大小写）
    pattern = re.compile(re.escape(old), re.IGNORECASE)
    match = pattern.search(text)
    if match:
        start = match.start()
        end = match.end()
        return text[:start] + new + text[end:]
    return text

def run_backup_script():
    """运行备份脚本"""
    try:
        xbmc.executebuiltin('RunScript(special://skin/scripts/backuplib.py)')
        return True
    except Exception as e:
        xbmc.log(f"Error running backup script: {str(e)}", xbmc.LOGERROR)
        return False

def main():
    # 创建选择对话框
    dialog = xbmcgui.Dialog()
    options = [
        "将媒体库115open新接口全部转为115老接口",
        "将媒体库115老接口全部转为115open新接口",
        "备份/恢复媒体库(只备份数据库,不含海报)"
    ]
    
    selected_option = dialog.select("请选择操作", options)
    
    if selected_option == -1:  # 用户取消选择
        return
    
    db_path = get_database_path()
    
    if not os.path.exists(db_path):
        dialog.ok("错误", f"数据库文件不存在:\n{db_path}")
        return
    
    if selected_option == 0:  # 115open转115
        result = replace_115open_to_115(db_path)
        if result >= 0:
            if result > 0:
                message = f"115open转115操作已完成\n共转换了 {result} 个路径"
                # 显示转换结果，用户点击确定后继续
                dialog.ok("转换完成", message)
                
                # 只有在实际转换发生时才执行后续操作
                # 重载皮肤
                xbmc.executebuiltin('ReloadSkin()')
                # 延时0.5秒
                time.sleep(0.5)
                # 设置焦点
                xbmc.executebuiltin('SetFocus(9000)')
            else:
                message = "115open转115操作已完成\n未发现需要转换的路径"
                dialog.ok("转换完成", message)
                # 未发生转换时不执行后续操作
        else:
            dialog.ok("错误", "115open转115操作失败，请查看日志")
    
    elif selected_option == 1:  # 115转115open
        result = replace_115_to_115open(db_path)
        if result >= 0:
            if result > 0:
                message = f"115转115open操作已完成\n共转换了 {result} 个路径"
                # 显示转换结果，用户点击确定后继续
                dialog.ok("转换完成", message)
                
                # 只有在实际转换发生时才执行后续操作
                # 重载皮肤
                xbmc.executebuiltin('ReloadSkin()')
                # 延时0.5秒
                time.sleep(0.5)
                # 设置焦点
                xbmc.executebuiltin('SetFocus(9000)')
            else:
                message = "115转115open操作已完成\n未发现需要转换的路径"
                dialog.ok("转换完成", message)
                # 未发生转换时不执行后续操作
        else:
            dialog.ok("错误", "115转115open操作失败，请查看日志")
    
    elif selected_option == 2:  # 备份/恢复媒体库
        run_backup_script()

if __name__ == "__main__":
    main()