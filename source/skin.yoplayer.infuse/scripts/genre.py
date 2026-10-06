#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：rating.py - 新增all参数重置逻辑
核心功能：
  1. 原有数据库读写核心功能（保留）
  2. 类型参数x处理：根据Skin.String(genre{x}mo)状态修改movie表idFile的ge后缀
  3. all参数处理：重置所有genrexxmo为0 + 全局删除ge后缀 + 刷新容器
  类型映射：dz=动作/xj=喜剧/aq=爱情/kh=科幻/fz=犯罪/mx=冒险/kb=恐怖/dh=动画/zz=战争/xy=悬疑/ls=历史/yy=音乐/jl=纪录/jt=家庭/jq=剧情/qh=奇幻/js=惊悚/dp=短片
"""
import sys
import os
import re
import sqlite3
import xbmc
import xbmcvfs

# ======================== 核心常量：类型映射 ========================
GENRE_MAPPING = {
    "dz": "动作",
    "xj": "喜剧",
    "aq": "爱情",
    "kh": "科幻",
    "fz": "犯罪",
    "mx": "冒险",
    "kb": "恐怖",
    "dh": "动画",
    "zz": "战争",
    "xy": "悬疑",
    "ls": "历史",
    "yy": "音乐",
    "jl": "纪录",
    "jt": "家庭",
    "jq": "剧情",
    "qh": "奇幻",
    "js": "惊悚",
    "dp": "短片"
}
ALL_GENRE_CODES = list(GENRE_MAPPING.keys())

# ======================== 原有基础函数（保留） ========================
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
    
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    return str(path)

def extract_numbers(input_str):
    """从字符串中提取所有数字字符，返回纯数字字符串（处理idFile）"""
    if not input_str or not isinstance(input_str, str if sys.version_info >= (3,) else (str, unicode)):
        return ""
    numbers = re.findall(r'\d+', input_str)
    return ''.join(numbers)

def delete_all_ra_from_movie(db_path):
    """【数据库写操作】删除movie表中所有idFile的ra/RA后缀"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE movie 
            SET idFile = REPLACE(REPLACE(IFNULL(idFile, ''), 'ra', ''), 'RA', '')
            WHERE idFile LIKE '%ra%' OR idFile LIKE '%RA%'
        """)
        update_count = cursor.rowcount
        conn.commit()
        xbmc.log(f"数据库操作：已删除movie表中{update_count}条记录的ra/RA后缀", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"删除ra后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def update_movie_idfile_ra(db_path, target_id_numbers, add_ra=True):
    """【数据库写操作】批量更新movie表的idFile的ra后缀"""
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
    """【数据库读操作】查询指定评分范围的movie_view.idFile"""
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
    """强制获取MyVideos131.db数据库路径"""
    userdata_path = translate_path('special://userdata')
    db_dir = os.path.join(userdata_path, 'Database')
    db_path = os.path.join(db_dir, 'MyVideos131.db')
    if not xbmcvfs.exists(db_path):
        raise FileNotFoundError(f"未找到指定数据库文件：{db_path}")
    return db_path

# ======================== Skin.String 操作函数 ========================
def get_skin_string(skin_key):
    """获取KODI Skin.String值，空值/非数字统一返回"0" """
    raw_val = xbmc.getInfoLabel(f"Skin.String({skin_key})")
    clean_val = raw_val.strip() if raw_val else ""
    return "1" if clean_val == "1" else "0"

def set_skin_string(skin_key, value):
    """设置KODI Skin.String值"""
    xbmc.executebuiltin(f'Skin.SetString({skin_key},{value})')
    xbmc.log(f"Skin.String操作：设置 {skin_key} = {value}", level=xbmc.LOGINFO)

def refresh_container():
    """刷新KODI当前容器（视图）"""
    xbmc.executebuiltin("Container.Refresh")
    xbmc.log("容器操作：刷新当前视图完成", level=xbmc.LOGINFO)

def check_other_genre_skin_string_1(current_x_code):
    """检查除当前x对应的类型外，其他所有genre{code}mo是否至少有一个值为1"""
    for code in ALL_GENRE_CODES:
        if code == current_x_code:
            continue
        skin_key = f"genre{code}mo"
        val = get_skin_string(skin_key)
        if val == "1":
            xbmc.log(f"Skin.String检查：{skin_key} = 1（排除当前{current_x_code}后仍有启用的类型）", level=xbmc.LOGINFO)
            return True
    xbmc.log(f"Skin.String检查：排除当前{current_x_code}后，所有genre{code}mo均为0/空", level=xbmc.LOGINFO)
    return False

# ======================== GE后缀 数据库操作函数 ========================
def add_ge_suffix_to_target_genre(db_path, target_genre_name):
    """给数据库中c14列包含目标类型的idFile添加ge后缀（不重复添加）"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT idFile FROM movie 
            WHERE idFile IS NOT NULL AND c14 LIKE ?
        """, (f'%{target_genre_name}%',))
        target_records = [str(row[0]) for row in cursor.fetchall()]
        
        update_count = 0
        for id_file in target_records:
            if "ge" not in id_file.lower():
                new_id = f"{id_file}ge"
                cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, id_file))
                update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：给[{target_genre_name}]类型添加ge后缀，共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"添加ge后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def delete_ge_suffix_from_target_genre(db_path, target_genre_name):
    """删除数据库中c14列包含目标类型的idFile的ge后缀"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT idFile FROM movie 
            WHERE idFile IS NOT NULL AND c14 LIKE ? AND (idFile LIKE '%ge%' OR idFile LIKE '%GE%')
        """, (f'%{target_genre_name}%',))
        target_records = [str(row[0]) for row in cursor.fetchall()]
        
        update_count = 0
        for id_file in target_records:
            new_id = id_file.replace("ge", "").replace("GE", "")
            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, id_file))
            update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：删除[{target_genre_name}]类型的ge后缀，共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"删除ge后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def delete_all_ge_suffix(db_path):
    """全局删除movie表中所有idFile的ge/GE后缀"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE movie 
            SET idFile = REPLACE(REPLACE(IFNULL(idFile, ''), 'ge', ''), 'GE', '')
            WHERE idFile LIKE '%ge%' OR idFile LIKE '%GE%'
        """)
        update_count = cursor.rowcount
        conn.commit()
        xbmc.log(f"数据库操作：全局删除ge后缀，共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"全局删除ge后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def add_ge_suffix_to_non_target_genre(db_path, target_genre_name):
    """给数据库中c14列不包含目标类型的idFile添加ge后缀（不重复添加）"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT idFile FROM movie 
            WHERE idFile IS NOT NULL AND (c14 NOT LIKE ? OR c14 IS NULL)
        """, (f'%{target_genre_name}%',))
        target_records = [str(row[0]) for row in cursor.fetchall()]
        
        update_count = 0
        for id_file in target_records:
            if "ge" not in id_file.lower():
                new_id = f"{id_file}ge"
                cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, id_file))
                update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：给非[{target_genre_name}]类型添加ge后缀，共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"给非目标类型添加ge后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

# ======================== 新增：处理all参数的核心函数 ========================
def handle_all_parameter():
    """
    处理all参数的逻辑：
    1. 所有genre{code}mo的Skin.String设为0
    2. 全局删除movie表idFile的所有ge后缀
    3. 刷新当前容器
    """
    xbmc.log("===== 开始处理all参数 =====", level=xbmc.LOGINFO)
    
    # 步骤1：遍历所有类型，设置Skin.String(genre{code}mo) = 0
    for code in ALL_GENRE_CODES:
        skin_key = f"genre{code}mo"
        set_skin_string(skin_key, 0)
    
    # 步骤2：获取数据库路径并全局删除ge后缀
    db_path = get_myvideos_db_path()
    delete_all_ge_suffix(db_path)
    
    # 步骤3：刷新容器
    refresh_container()
    xbmc.log("===== all参数处理完成 =====", level=xbmc.LOGINFO)

# ======================== 处理x参数的核心函数（保留） ========================
def handle_genre_x_parameter(x_code):
    """处理类型参数x的核心逻辑"""
    if x_code not in GENRE_MAPPING:
        raise ValueError(f"无效的类型参数：{x_code}，支持的参数：{','.join(ALL_GENRE_CODES)}")
    
    target_genre_name = GENRE_MAPPING[x_code]
    current_skin_key = f"genre{x_code}mo"
    db_path = get_myvideos_db_path()
    
    current_skin_val = get_skin_string(current_skin_key)
    other_genre_has_1 = check_other_genre_skin_string_1(x_code)
    
    xbmc.log(f"===== 开始处理参数x={x_code}（对应类型：{target_genre_name}） =====", level=xbmc.LOGINFO)
    xbmc.log(f"当前Skin.String({current_skin_key}) = {current_skin_val}", level=xbmc.LOGINFO)
    xbmc.log(f"其他类型Skin.String是否有1：{other_genre_has_1}", level=xbmc.LOGINFO)
    
    if current_skin_val == "1":
        if other_genre_has_1:
            add_ge_suffix_to_target_genre(db_path, target_genre_name)
        else:
            delete_all_ge_suffix(db_path)
        set_skin_string(current_skin_key, 0)
    else:
        if other_genre_has_1:
            delete_ge_suffix_from_target_genre(db_path, target_genre_name)
        else:
            add_ge_suffix_to_non_target_genre(db_path, target_genre_name)
        set_skin_string(current_skin_key, 1)
    
    refresh_container()
    xbmc.log(f"===== 参数x={x_code}处理完成 =====", level=xbmc.LOGINFO)

# ======================== 主执行入口（新增all参数判断） ========================
if __name__ == "__main__":
    # Python 2编码兼容
    if sys.version_info < (3,):
        reload(sys)
        sys.setdefaultencoding('utf-8')
    
    try:
        # 检查命令行参数
        if len(sys.argv) > 1:
            input_param = sys.argv[1].strip().lower()  # 统一转小写，兼容ALL/All等输入
            
            # 分支1：处理all参数
            if input_param == "all":
                handle_all_parameter()
            
            # 分支2：处理类型参数x
            elif input_param in ALL_GENRE_CODES:
                handle_genre_x_parameter(input_param)
            
            # 分支3：无效参数
            else:
                raise ValueError(f"无效参数：{input_param}，支持的参数：all / {','.join(ALL_GENRE_CODES)}")
        
        # 无参数时执行原有示例逻辑
        else:
            db_path = get_myvideos_db_path()
            print(f"数据库路径：{db_path}")
            
            # 示例：查询评分6-8的ID
            target_ids = query_movie_rating_range(db_path, min_rating=6.0, max_rating=8.0)
            print(f"评分6.0-8.0的id数量：{len(target_ids)}")
        
    except Exception as e:
        error_msg = f"执行失败：{str(e)}"
        print(error_msg)
        xbmc.log(error_msg, level=xbmc.LOGERROR)