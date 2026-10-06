#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：rating.py - 新增all参数逻辑 + 保留1960/1970等参数规则
all参数逻辑：
  1. 批量设置year1960/1970/1980/1990/2000/2010/2020mo为0
  2. 处理tvshow表所有结尾3/4/8/9的负数idShow（加3，满足条件则转正数）
  3. 刷新容器
"""
import sys
import os
import re
import sqlite3
import xbmc
import xbmcvfs

# ===================== 全局常量定义 =====================
# 新增"all"参数到支持列表
SUPPORTED_PARAMS = ["all", "1960", "1970", "1980", "1990", "2000", "2010", "2020"]
MYVIDEOS_DB_NAME = "MyVideos131.db"
# 所有年份键列表（用于all参数批量设置）
ALL_YEAR_KEYS = [f"year{y}mo" for y in [1960, 1970, 1980, 1990, 2000, 2010, 2020]]

# ===================== 原有核心函数（保留） =====================
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
    """批量更新movie表的idFile后缀"""
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
    """查询指定评分范围的movie_view.idFile"""
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

def get_myvideos_db_path(db_version=MYVIDEOS_DB_NAME):
    """获取KODI MyVideos数据库路径"""
    userdata_path = translate_path('special://userdata')
    db_dir = os.path.join(userdata_path, 'Database')
    db_path = os.path.join(db_dir, db_version)
    if xbmcvfs.exists(db_path):
        return db_path
    raise FileNotFoundError(f"未找到MyVideos数据库文件：{db_version}")

# ===================== 通用工具函数（保留） =====================
def get_skin_string(skin_key):
    """获取KODI Skin.String值，统一返回0/1"""
    value = xbmc.getInfoLabel(f'Skin.String({skin_key})').strip()
    return 1 if value == "1" else 0

def set_skin_string(skin_key, value):
    """设置KODI Skin.String值"""
    xbmc.executebuiltin(f'Skin.SetString({skin_key}, {value})')
    xbmc.log(f"设置Skin.String({skin_key}) = {value}", level=xbmc.LOGINFO)

def refresh_container():
    """刷新KODI当前容器"""
    xbmc.executebuiltin('Container.Refresh')
    xbmc.log("执行容器刷新操作", level=xbmc.LOGINFO)

def extract_year_from_c05(c05_value):
    """从tvshow表c05字段提取年份"""
    if not c05_value or not isinstance(c05_value, (str, int)):
        return None
    
    c05_str = str(c05_value).strip()
    if re.match(r'^\d{4}$', c05_str):
        try:
            return int(c05_str)
        except ValueError:
            return None
    
    date_match = re.match(r'^(\d{4})-\d{2}-\d{2}$', c05_str)
    if date_match:
        try:
            return int(date_match.group(1))
        except ValueError:
            return None
    
    return None

def process_idshow_number(original_num, neg_delta=3, process_positive=True, is_22_branch=False):
    """处理idShow数值的核心规则（保留2.2分支专属逻辑）"""
    if not isinstance(original_num, int):
        try:
            original_num = int(original_num)
        except (ValueError, TypeError):
            xbmc.log(f"idShow数值转换失败：{original_num}", level=xbmc.LOGWARNING)
            return original_num
    
    new_num = original_num
    
    # 规则1：正数处理（仅当process_positive=True时）
    if process_positive and original_num > 0:
        new_num = -(original_num * 10000 + 3)
        xbmc.log(f"正数处理：{original_num} → {new_num}", level=xbmc.LOGDEBUG)
    
    # 规则2：负数处理（区分2.2分支和其他分支）
    elif original_num < 0:
        last_digit = abs(original_num) % 10  # 提取负数尾数（忽略负号）
        
        if is_22_branch:
            # 2.2分支：尾数非3/4/8/9 → 减3；尾数是 → 不变
            if last_digit not in [3, 4, 8, 9]:
                new_num = original_num + neg_delta  # 2.2分支delta=-3 → 实际减3
                # 判断最后一位是否为0 且 ≤-10000
                new_last_digit = abs(new_num) % 10
                if new_last_digit == 0 and new_num <= -10000:
                    new_num = abs(new_num) // 10000  # 除以10000转正数
                xbmc.log(f"2.2分支负数处理：{original_num}（尾数{last_digit}）→ {new_num}（减3）", level=xbmc.LOGDEBUG)
            else:
                xbmc.log(f"2.2分支负数处理：{original_num}（尾数{last_digit}）→ 不变（尾数是3/4/8/9）", level=xbmc.LOGDEBUG)
        else:
            # 非2.2分支：仅尾数是3/4/8/9时处理
            if last_digit in [3, 4, 8, 9]:
                new_num = original_num + neg_delta
                new_last_digit = abs(new_num) % 10
                if new_last_digit == 0 and new_num <= -10000:
                    new_num = abs(new_num) // 10000
                xbmc.log(f"非2.2分支负数处理：{original_num} → {new_num}（最后一位{last_digit}，增量{neg_delta}）", level=xbmc.LOGDEBUG)
            else:
                xbmc.log(f"非2.2分支负数处理：{original_num}（尾数{last_digit}）→ 不变", level=xbmc.LOGDEBUG)
    
    return new_num

# ===================== 1960参数处理逻辑（保留） =====================
def handle_tvshow_idshow_1960(db_path, process_type):
    """处理1960参数对应的tvshow表idShow字段"""
    conn = None
    update_count = 0
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("SELECT idShow, c05 FROM tvshow")
        tvshow_records = cursor.fetchall()
        
        has_ge_1970 = False
        if process_type == "2.2":
            for _, c05_val in tvshow_records:
                year = extract_year_from_c05(c05_val)
                if year is not None and year >= 1970:
                    has_ge_1970 = True
                    break
        
        for id_show, c05_val in tvshow_records:
            need_process = False
            current_year = extract_year_from_c05(c05_val)
            process_positive = True
            neg_delta = 3
            is_22_branch = False  # 默认非2.2分支
            
            if process_type == "1.1":
                need_process = (current_year is None) or (current_year < 1970)
                process_positive = True
                neg_delta = 3
            
            elif process_type == "1.2":
                need_process = True
                process_positive = False
                neg_delta = 3
            
            elif process_type == "2.1":
                need_process = (current_year is None) or (current_year < 1970)
                process_positive = False
                neg_delta = 3
            
            elif process_type == "2.2":
                if has_ge_1970:
                    need_process = (current_year is not None) and (current_year >= 1970)
                else:
                    need_process = True
                process_positive = True
                neg_delta = -3  # 负数减3
                is_22_branch = True  # 触发2.2分支专属规则
            
            if need_process:
                new_id = process_idshow_number(id_show, neg_delta, process_positive, is_22_branch)
                if new_id != id_show:
                    cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (new_id, id_show))
                    update_count += 1
        
        conn.commit()
        xbmc.log(f"1960参数：tvshow表idShow处理完成（类型：{process_type}），共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"1960参数：处理tvshow表idShow失败（类型：{process_type}）：{str(e)}")
    finally:
        if conn:
            conn.close()

def handle_1960_parameter_logic():
    """处理1960参数触发的核心业务逻辑"""
    db_path = get_myvideos_db_path(MYVIDEOS_DB_NAME)
    year1960mo_val = get_skin_string("year1960mo")
    other_year_keys = [f"year{y}mo" for y in [1970, 1980, 1990, 2000, 2010, 2020]]
    other_year_has_1 = any([get_skin_string(key) == 1 for key in other_year_keys])
    
    xbmc.log(f"触发1960参数逻辑：year1960mo={year1960mo_val}，其他年份有1={other_year_has_1}", level=xbmc.LOGINFO)
    
    if year1960mo_val == 1:
        if other_year_has_1:
            handle_tvshow_idshow_1960(db_path, "1.1")
        else:
            handle_tvshow_idshow_1960(db_path, "1.2")
        set_skin_string("year1960mo", 0)
    else:
        if other_year_has_1:
            handle_tvshow_idshow_1960(db_path, "2.1")
        else:
            handle_tvshow_idshow_1960(db_path, "2.2")
        set_skin_string("year1960mo", 1)
    
    refresh_container()

# ===================== 1970/1980等参数处理逻辑（保留） =====================
def handle_tvshow_idshow_year_x(db_path, x_year, process_type):
    """处理1970/1980等参数对应的tvshow表idShow字段"""
    conn = None
    update_count = 0
    x_next = x_year + 10
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("SELECT idShow, c05 FROM tvshow")
        tvshow_records = cursor.fetchall()
        
        # 预判断2.2分支是否需要处理所有记录（无year<x或>x+10的记录）
        has_lt_x_or_gt_xnext = False
        if process_type == "2.2":
            for _, c05_val in tvshow_records:
                year = extract_year_from_c05(c05_val)
                if year is not None and (year < x_year or year > x_next):
                    has_lt_x_or_gt_xnext = True
                    break
        
        # 遍历处理每条记录
        for id_show, c05_val in tvshow_records:
            need_process = False
            current_year = extract_year_from_c05(c05_val)
            process_positive = True
            neg_delta = 3
            is_22_branch = False  # 默认非2.2分支
            
            # 按处理类型匹配规则
            if process_type == "1.1":
                if current_year is not None:
                    need_process = (current_year >= x_year) and (current_year < x_next)
                process_positive = True
                neg_delta = 3
            
            elif process_type == "1.2":
                need_process = True
                process_positive = False
                neg_delta = 3
            
            elif process_type == "2.1":
                if current_year is not None:
                    need_process = (current_year >= x_year) and (current_year < x_next)
                process_positive = False
                neg_delta = 3
            
            elif process_type == "2.2":
                if has_lt_x_or_gt_xnext:
                    if current_year is not None:
                        need_process = (current_year < x_year) or (current_year > x_next)
                else:
                    need_process = True  # 无符合条件年份，处理所有
                process_positive = True  # 处理正数
                neg_delta = -3  # 负数减3
                is_22_branch = True  # 触发2.2分支专属负数规则
            
            # 执行处理并更新
            if need_process:
                new_id = process_idshow_number(id_show, neg_delta, process_positive, is_22_branch)
                if new_id != id_show:
                    cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (new_id, id_show))
                    update_count += 1
        
        conn.commit()
        xbmc.log(f"{x_year}参数：tvshow表idShow处理完成（类型：{process_type}），共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"{x_year}参数：处理tvshow表idShow失败（类型：{process_type}）：{str(e)}")
    finally:
        if conn:
            conn.close()

def handle_year_x_parameter_logic(x_param):
    """处理1970/1980等参数触发的核心业务逻辑"""
    x_year = int(x_param)
    db_path = get_myvideos_db_path(MYVIDEOS_DB_NAME)
    skin_key = f"year{x_param}mo"
    current_skin_val = get_skin_string(skin_key)
    
    # 所有年份键列表（排除当前x）
    other_year_keys = [k for k in ALL_YEAR_KEYS if k != skin_key]
    other_year_has_1 = any([get_skin_string(key) == 1 for key in other_year_keys])
    
    xbmc.log(f"触发{x_param}参数逻辑：{skin_key}={current_skin_val}，其他年份有1={other_year_has_1}", level=xbmc.LOGINFO)
    
    if current_skin_val == 1:
        if other_year_has_1:
            handle_tvshow_idshow_year_x(db_path, x_year, "1.1")
        else:
            handle_tvshow_idshow_year_x(db_path, x_year, "1.2")
        set_skin_string(skin_key, 0)
    else:
        if other_year_has_1:
            handle_tvshow_idshow_year_x(db_path, x_year, "2.1")
        else:
            handle_tvshow_idshow_year_x(db_path, x_year, "2.2")
        set_skin_string(skin_key, 1)
    
    refresh_container()

# ===================== all参数处理逻辑（新增核心） =====================
def handle_all_parameter_logic():
    """处理all参数的核心逻辑"""
    # 1. 初始化数据库路径
    db_path = get_myvideos_db_path(MYVIDEOS_DB_NAME)
    
    # 2. 批量设置所有yearXmo为0
    xbmc.log("all参数：开始批量设置所有year1960/1970等Skin.String为0", level=xbmc.LOGINFO)
    for skin_key in ALL_YEAR_KEYS:
        set_skin_string(skin_key, 0)
    xbmc.log("all参数：已完成所有yearXmo的置0操作", level=xbmc.LOGINFO)
    
    # 3. 处理tvshow表idShow列：所有结尾是3/4/8/9的负数加3
    conn = None
    update_count = 0
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 查询所有idShow记录
        cursor.execute("SELECT idShow FROM tvshow")
        idshow_records = cursor.fetchall()
        
        # 遍历处理每条记录
        for (id_show,) in idshow_records:
            # 数值转换校验
            if not isinstance(id_show, int):
                try:
                    id_show = int(id_show)
                except (ValueError, TypeError):
                    xbmc.log(f"all参数：idShow {id_show} 非整型，跳过处理", level=xbmc.LOGWARNING)
                    continue
            
            # 仅处理负数且结尾是3/4/8/9的情况
            if id_show < 0:
                last_digit = abs(id_show) % 10
                if last_digit in [3, 4, 8, 9]:
                    # 第一步：加3
                    new_id = id_show + 3
                    # 第二步：判断最后一位是否为0且≤-10000
                    new_last_digit = abs(new_id) % 10
                    if new_last_digit == 0 and new_id <= -10000:
                        new_id = abs(new_id) // 10000  # 除以10000转正数
                    # 第三步：更新数据库
                    cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (new_id, id_show))
                    update_count += 1
                    xbmc.log(f"all参数：处理idShow {id_show} → {new_id}（尾数{last_digit}，加3）", level=xbmc.LOGDEBUG)
        
        # 提交事务
        conn.commit()
        xbmc.log(f"all参数：tvshow表处理完成，共更新{update_count}条idShow记录", level=xbmc.LOGINFO)
    
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"all参数：处理tvshow表失败：{str(e)}")
    finally:
        if conn:
            conn.close()
    
    # 4. 刷新容器
    refresh_container()
    xbmc.log("all参数：所有操作执行完毕", level=xbmc.LOGINFO)

# ===================== 主执行逻辑（新增all参数处理） =====================
if __name__ == "__main__":
    if sys.version_info < (3,):
        reload(sys)
        sys.setdefaultencoding('utf-8')
    
    try:
        if len(sys.argv) < 2:
            raise ValueError(f"未传入参数，支持的参数：{','.join(SUPPORTED_PARAMS)}")
        
        input_param = sys.argv[1]
        if input_param not in SUPPORTED_PARAMS:
            raise ValueError(f"不支持的参数：{input_param}，仅支持：{','.join(SUPPORTED_PARAMS)}")
        
        # 执行对应参数逻辑
        if input_param == "all":
            handle_all_parameter_logic()
        elif input_param == "1960":
            handle_1960_parameter_logic()
        else:
            # 1970/1980/1990/2000/2010/2020参数
            handle_year_x_parameter_logic(input_param)
    
    except Exception as e:
        error_msg = f"操作失败：{str(e)}"
        print(error_msg)
        xbmc.log(error_msg, level=xbmc.LOGERROR)
        # 非参数错误时执行示例逻辑
        if "未传入参数" not in str(e) and "不支持的参数" not in str(e):
            try:
                db_path = get_myvideos_db_path()
                print(f"数据库路径：{db_path}")
                target_ids = query_movie_rating_range(db_path, min_rating=6.0, max_rating=8.0)
                print(f"评分6.0-8.0的id数量：{len(target_ids)}")
            except Exception as e2:
                print(f"示例逻辑执行失败：{str(e2)}")