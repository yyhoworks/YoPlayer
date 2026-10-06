# -*- coding: utf-8 -*-
"""
KODI运行脚本：处理MyVideos131.db中超长c01字段
运行路径：special://skin/scripts/R5plot.py
功能：校验系统版本后截断tvshow/episode表超长文本，有修改则重载皮肤
"""
import xbmc
import sqlite3
import os
import re

def get_pretty_name():
    """
    读取/etc/os-release文件中的PRETTY_NAME值
    返回：成功返回字符串，失败返回None
    """
    os_release_path = "/etc/os-release"
    # 检查文件是否存在
    if not os.path.exists(os_release_path):
        xbmc.log("R5plot.py: /etc/os-release 文件不存在", level=xbmc.LOGERROR)
        return None
    
    try:
        # 读取文件内容（兼容不同编码）
        with open(os_release_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 匹配PRETTY_NAME字段（兼容单/双引号、空格）
        pretty_name_pattern = re.compile(r'^PRETTY_NAME\s*=\s*["\'](.*?)["\']', re.M)
        match = pretty_name_pattern.search('\n'.join(lines))
        
        if match:
            pretty_name = match.group(1).strip()
            xbmc.log(f"R5plot.py: 读取到PRETTY_NAME = {pretty_name}", level=xbmc.LOGINFO)
            return pretty_name
        else:
            xbmc.log("R5plot.py: /etc/os-release中未找到PRETTY_NAME字段", level=xbmc.LOGERROR)
            return None
            
    except Exception as e:
        xbmc.log(f"R5plot.py: 读取/etc/os-release失败 - {str(e)}", level=xbmc.LOGERROR)
        return None

def check_table_exists(cursor, table_name):
    """
    检查数据库中是否存在指定名称的表
    参数：
        cursor: 数据库游标对象
        table_name: 表名称
    返回：存在返回True，不存在返回False
    """
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def process_database():
    """
    处理MyVideos131.db数据库中的tvshow和episode表的c01字段
    截断规则：超过330字符时，从第330位向前找最近的。？！，替换为...
    返回：是否有数据修改（True/False）
    """
    db_path = "/storage/.kodi/userdata/Database/MyVideos131.db"
    modified = False
    conn = None
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        xbmc.log(f"R5plot.py: 数据库文件 {db_path} 不存在", level=xbmc.LOGERROR)
        return modified
    
    try:
        # 连接数据库（设置超时避免锁死，开启写权限）
        conn = sqlite3.connect(db_path, timeout=15)
        cursor = conn.cursor()
        
        # 需要处理的数据表（tvshow和episode）
        tables = ["tvshow", "episode"]
        # 字符长度阈值（从350改为330）
        char_limit = 330
        # 目标标点符号
        target_puncts = ["。", "？", "！"]
        # 替换用的省略号（从......改为...）
        ellipsis = "..."
        
        for table in tables:
            # 检查表是否存在
            if not check_table_exists(cursor, table):
                xbmc.log(f"R5plot.py: 数据库中未找到表 {table}，跳过处理", level=xbmc.LOGWARNING)
                continue
            
            # 确定主键字段（tvshow表主键是idShow，episode表是idEpisode）
            primary_key = "idShow" if table == "tvshow" else "idEpisode"
            
            # 查询c01字段长度超过阈值的记录
            query_sql = f"SELECT {primary_key}, c01 FROM {table} WHERE LENGTH(c01) > ?"
            cursor.execute(query_sql, (char_limit,))
            records = cursor.fetchall()
            
            if not records:
                xbmc.log(f"R5plot.py: 表 {table} 中无超过{char_limit}字符的c01字段记录", level=xbmc.LOGINFO)
                continue
            
            # 逐个处理超长记录
            for record_id, c01_content in records:
                original_len = len(c01_content)
                # 第330个字符的索引（从0开始，所以是329）
                search_end = min(char_limit - 1, original_len - 1)
                cut_pos = -1
                
                # 从330字符位置向前查找最近的目标标点
                for pos in range(search_end, -1, -1):
                    if c01_content[pos] in target_puncts:
                        cut_pos = pos
                        break
                
                # 未找到指定标点则跳过
                if cut_pos == -1:
                    xbmc.log(f"R5plot.py: 表{table} ID{record_id} 未找到截断标点（。？！），跳过", level=xbmc.LOGINFO)
                    continue
                
                # 截断文本并替换标点为省略号
                new_content = c01_content[:cut_pos] + ellipsis
                new_len = len(new_content)
                
                # 更新数据库记录
                update_sql = f"UPDATE {table} SET c01 = ? WHERE {primary_key} = ?"
                cursor.execute(update_sql, (new_content, record_id))
                modified = True
                
                # 记录修改日志
                xbmc.log(
                    f"R5plot.py: 表{table} ID{record_id} 处理完成 - "
                    f"原长度{original_len} → 新长度{new_len}",
                    level=xbmc.LOGINFO
                )
        
        # 提交修改（仅当有修改时）
        if modified:
            conn.commit()
            xbmc.log("R5plot.py: 数据库修改已提交", level=xbmc.LOGINFO)
        else:
            xbmc.log("R5plot.py: 无数据库记录需要修改", level=xbmc.LOGINFO)
            
    except Exception as e:
        xbmc.log(f"R5plot.py: 处理数据库失败 - {str(e)}", level=xbmc.LOGERROR)
        if conn:
            conn.rollback()  # 出错回滚
    finally:
        if conn:
            conn.close()  # 关闭数据库连接
    
    return modified

# 主程序逻辑
if __name__ == "__main__":
    # 1. 获取系统PRETTY_NAME并校验
    pretty_name = get_pretty_name()
    if not pretty_name or "avdvplus" not in pretty_name.lower():
        xbmc.log("R5plot.py: 系统版本校验失败，静默退出", level=xbmc.LOGINFO)
        exit(0)
    
    # 2. 处理数据库
    has_modified = process_database()
    
    # 3. 有修改则重新加载皮肤
    if has_modified:
        xbmc.log("R5plot.py: 检测到数据修改，执行皮肤重载", level=xbmc.LOGINFO)
        xbmc.executebuiltin("ReloadSkin()")
    
    # 4. 静默退出
    exit(0)