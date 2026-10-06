#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：rating.py - 优化版（按需归零+tvshow负数处理）
核心优化：
  1. 仅当Skin字符串值为1时才执行归零（0/空值跳过），减少系统调用
  2. 保留原有数据库读写、容器刷新等核心功能
  3. 新增跳过日志，便于排查参数状态
  4. 新增tvshow表idShow列负数处理：最后一位置0 → 除以-10000
"""
import sys
import os
import re
import sqlite3
import xbmc
import xbmcvfs

def get_kodi_version():
    """获取KODI主版本号（用于路径转换兼容）"""
    version_str = xbmc.getInfoLabel('System.BuildVersion')
    try:
        return int(version_str.split('.')[0])
    except (ValueError, IndexError):
        return 18

def translate_path(virtual_path):
    """兼容新旧版本的KODI路径转换，返回实际字符串路径"""
    kodi_ver = get_kodi_version()
    if kodi_ver >= 19:
        path = xbmcvfs.translatePath(virtual_path)
    else:
        path = xbmc.translatePath(virtual_path)
    
    # 统一编码为字符串（兼容Python 2/3）
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    return str(path)

def extract_numbers(input_str):
    """从字符串中提取所有数字字符，返回纯数字字符串（处理idFile）"""
    if not input_str or not isinstance(input_str, str if sys.version_info >= (3,) else (str, unicode)):
        return ""
    numbers = re.findall(r'\d+', input_str)
    return ''.join(numbers)

def delete_spec_suffix_from_movie(db_path):
    """数据库写操作：删除movie表中所有idFile的ge/ar/ye/ra后缀（含大小写）"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 批量删除ge/ar/ye/ra（含大小写），按顺序替换避免遗漏
        cursor.execute("""
            UPDATE movie 
            SET idFile = REPLACE(REPLACE(REPLACE(REPLACE(
                           REPLACE(REPLACE(REPLACE(REPLACE(
                               IFNULL(idFile, ''), 'ge', ''), 'GE', ''),
                               'ar', ''), 'AR', ''),
                               'ye', ''), 'YE', ''),
                               'ra', ''), 'RA', '')
            WHERE idFile LIKE '%ge%' OR idFile LIKE '%GE%'
               OR idFile LIKE '%ar%' OR idFile LIKE '%AR%'
               OR idFile LIKE '%ye%' OR idFile LIKE '%YE%'
               OR idFile LIKE '%ra%' OR idFile LIKE '%RA%'
        """)
        update_count = cursor.rowcount
        conn.commit()
        xbmc.log(f"数据库操作：已删除movie表中{update_count}条记录的ge/ar/ye/ra（含大小写）后缀", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"删除指定后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def process_tvshow_idshow_negative(db_path):
    """
    处理tvshow表idShow列负数：
    1. 提取idShow列所有负数
    2. 负数最后一位数字置0
    3. 结果除以-10000
    4. 更新回数据库
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 1. 查询tvshow表中idShow为负数的记录（获取idShow值和主键）
        # tvshow表主键为idShow，因此直接查询idShow < 0的记录
        cursor.execute("SELECT idShow FROM tvshow WHERE idShow < 0")
        negative_records = cursor.fetchall()
        if not negative_records:
            xbmc.log("数据库操作：tvshow表idShow列无负数记录，无需处理", level=xbmc.LOGINFO)
            return 0
        
        update_count = 0
        for (id_show,) in negative_records:
            original_val = id_show  # 原始负数，如-12345
            # 2. 最后一位数字置0（数学方法实现，避免字符串操作误差）
            # 步骤：取绝对值 → 整除10 → 乘以10 → 恢复负号
            abs_val = abs(original_val)
            val_with_zero_last = (abs_val // 10) * 10
            new_val_before_div = -val_with_zero_last  # 如-12340
            # 3. 除以-10000
            final_val = new_val_before_div / -10000  # 如-12340 / -10000 = 1.234
            
            # 4. 更新数据库（按主键idShow精准更新）
            cursor.execute("""
                UPDATE tvshow 
                SET idShow = ? 
                WHERE idShow = ?
            """, (final_val, original_val))
            update_count += 1
            xbmc.log(
                f"数据库操作：tvshow表idShow更新 - 原始值：{original_val} → 处理后值：{final_val}",
                level=xbmc.LOGDEBUG
            )
        
        conn.commit()
        xbmc.log(f"数据库操作：已处理tvshow表中{update_count}条idShow负数记录", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"处理tvshow表idShow负数失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def init_skin_strings():
    """
    优化版：按需归零（仅值为1时执行）
    1. 检查Skin.String值，仅当等于"1"时归零
    2. 0/空值跳过，减少系统调用，提升性能
    """
    try:
        # 定义需要初始化的参数配置（按用户要求的分隔规则）
        skin_config = [
            {
                "prefix": "genre",
                "params": "dz/xj/aq/kh/fz/mx/kb/dh/zz/xy/ls/yy/jl/jt/jq/qh/js/dp",
                "suffix": "mo"
            },
            {
                "prefix": "area",
                "params": "ch/hk/tw/mg/rb/hg/tg/yd/yg/fg/dg/els/qt",
                "suffix": "mo"
            },
            {
                "prefix": "year",
                "params": "1960/1970/1980/1990/2000/2010/2020",
                "suffix": "mo"
            },
            {
                "prefix": "rating",
                "params": "4/5/6/7/8/9",
                "suffix": "mo"
            }
        ]
        
        # 遍历配置，按需归零
        total_exec = 0  # 实际执行归零的数量
        total_skip = 0  # 跳过的数量（0/空值）
        for config in skin_config:
            prefix = config["prefix"]
            params_list = config["params"].split("/")  # 按/拆分参数
            suffix = config["suffix"]
            
            for param in params_list:
                # 拼接无下划线的Skin键名
                skin_key = f"{prefix}{param}{suffix}"
                # 获取当前Skin.String的值（返回字符串类型）
                current_value = xbmc.getInfoLabel(f"Skin.String({skin_key})").strip()
                
                # 仅当值为"1"时执行归零操作
                if current_value == "1":
                    cmd = f"Skin.SetString({skin_key},0)"
                    xbmc.executebuiltin(cmd)
                    xbmc.log(f"执行Skin字符串归零：{cmd}（原值为1）", level=xbmc.LOGINFO)
                    total_exec += 1
                else:
                    # 跳过0/空值，记录日志（可选，也可注释掉减少日志量）
                    xbmc.log(f"跳过Skin字符串归零：{skin_key}（原值为{current_value}，无需处理）", level=xbmc.LOGDEBUG)
                    total_skip += 1
        
        xbmc.log(f"Skin字符串初始化完成：执行归零{total_exec}个，跳过{total_skip}个（0/空值）", level=xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log(f"初始化Skin字符串失败：{str(e)}", level=xbmc.LOGERROR)
        raise Exception(f"初始化Skin字符串失败：{str(e)}")

def refresh_current_container():
    """刷新KODI当前容器（界面实时更新）"""
    try:
        xbmc.executebuiltin("Container.Refresh")
        xbmc.log("已执行当前容器刷新操作", level=xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log(f"刷新容器失败：{str(e)}", level=xbmc.LOGERROR)
        raise Exception(f"刷新容器失败：{str(e)}")

def update_movie_idfile_ra(db_path, target_id_numbers, add_ra=True):
    """【保留】批量更新movie表的idFile后缀（添加/删除ra）"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
        all_movie_ids = [str(row[0]) for row in cursor.fetchall()]
        
        update_count = 0
        for movie_id_str in all_movie_ids:
            movie_id_num = extract_numbers(movie_id_str)
            is_target = movie_id_num in target_id_numbers
            
            if add_ra:
                if is_target and "ra" not in movie_id_str.lower():
                    new_id = f"{movie_id_str}ra"
                    cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                    update_count += 1
            else:
                if is_target and "ra" in movie_id_str.lower():
                    new_id = movie_id_str.replace("ra", "").replace("RA", "")
                    cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                    update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：{'添加' if add_ra else '删除'}ra后缀，共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"批量更新idFile失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def query_movie_rating_range(db_path, min_rating=None, max_rating=None):
    """【保留】查询指定评分范围的movie_view.idFile纯数字列表"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        conditions = ["idFile IS NOT NULL"]
        params = []
        if min_rating is not None:
            conditions.append("rating >= ?")
            params.append(min_rating)
        if max_rating is not None:
            conditions.append("rating <= ?")
            params.append(max_rating)
        
        query_sql = f"SELECT idFile FROM movie_view WHERE {' AND '.join(conditions)}"
        cursor.execute(query_sql, params)
        
        raw_id_files = [str(row[0]) for row in cursor.fetchall() if row[0] is not None]
        target_id_numbers = list(set([extract_numbers(idf) for idf in raw_id_files]))
        target_id_numbers = [num for num in target_id_numbers if num]
        
        xbmc.log(f"数据库操作：查询到{len(target_id_numbers)}条符合评分范围的idFile", level=xbmc.LOGINFO)
        return target_id_numbers
    except sqlite3.Error as e:
        raise Exception(f"查询评分范围失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def get_myvideos_db_path():
    """【保留】获取KODI MyVideos数据库路径（优先MyVideos131.db）"""
    userdata_path = translate_path('special://userdata')
    db_dir = os.path.join(userdata_path, 'Database')
    
    db_versions = ['MyVideos131.db', 'MyVideos119.db', 'MyVideos129.db']
    for db_name in db_versions:
        db_path = os.path.join(db_dir, db_name)
        if xbmcvfs.exists(db_path):
            return db_path
    raise FileNotFoundError("未找到有效的MyVideos数据库文件（优先查找MyVideos131.db）")

# 主执行逻辑
if __name__ == "__main__":
    # Python 2编码兼容
    if sys.version_info < (3,):
        reload(sys)
        sys.setdefaultencoding('utf-8')
    
    try:
        # 步骤1：按需初始化Skin字符串参数（仅值为1时归零）
        init_skin_strings()
        
        # 步骤2：获取数据库路径
        db_path = get_myvideos_db_path()
        print(f"数据库路径：{db_path}")
        
        # 步骤3：删除movie表idFile中的ge/ar/ye/ra后缀
        delete_count = delete_spec_suffix_from_movie(db_path)
        print(f"删除ge/ar/ye/ra后缀数量：{delete_count}")
        
        # 步骤4：新增 - 处理tvshow表idShow列负数
        tvshow_update_count = process_tvshow_idshow_negative(db_path)
        print(f"处理tvshow表idShow负数数量：{tvshow_update_count}")
        
        # 步骤5：刷新当前容器
        refresh_current_container()
        
        print("所有操作执行完成！")
        
    except Exception as e:
        print(f"操作失败：{str(e)}")
        xbmc.log(f"脚本执行失败：{str(e)}", level=xbmc.LOGERROR)