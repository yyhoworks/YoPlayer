#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：rating.py
功能：
  1. 参数"1960"：按year1960mo及其他year mo状态处理movie表idFile的ye后缀
  2. 参数"all"：批量重置所有year mo为0 + 删除所有idFile的ye后缀
  3. 参数"x"（1970/1980/1990/2000/2010/2020）：按yearxmo及其他year mo状态处理指定年份范围的ye后缀
"""
import sys
import os
import re
import sqlite3
import xbmc
import xbmcvfs
import xbmcgui

# ===================== 基础工具函数 =====================
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

def get_myvideos_db_path():
    """获取KODI MyVideos数据库路径（强制使用MyVideos131.db）"""
    userdata_path = translate_path('special://userdata')
    db_dir = os.path.join(userdata_path, 'Database')
    db_path = os.path.join(db_dir, 'MyVideos131.db')
    
    if xbmcvfs.exists(db_path):
        return db_path
    raise FileNotFoundError("未找到指定的数据库文件：MyVideos131.db")

# ===================== 通用数据库操作函数 =====================
def delete_all_ye_from_movie(db_path):
    """删除movie表中所有idFile的ye/YE后缀"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 全局删除所有ye/YE后缀
        cursor.execute("""
            UPDATE movie 
            SET idFile = REPLACE(REPLACE(IFNULL(idFile, ''), 'ye', ''), 'YE', '')
            WHERE idFile LIKE '%ye%' OR idFile LIKE '%YE%'
        """)
        delete_count = cursor.rowcount
        conn.commit()
        xbmc.log(f"通用逻辑：已删除movie表中{delete_count}条记录的ye/YE后缀", level=xbmc.LOGINFO)
        return delete_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"删除所有ye后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def update_movie_idfile_ye_batch(db_path, target_id_files, add_ye=True):
    """
    批量更新movie表idFile的ye后缀
    :param target_id_files: 目标idFile列表（None表示所有idFile）
    :param add_ye: True=添加ye后缀（不重复）；False=删除ye后缀
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 获取待处理的idFile列表
        if target_id_files is None:
            cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
            process_ids = [str(row[0]) for row in cursor.fetchall()]
        else:
            process_ids = target_id_files
        
        update_count = 0
        for id_file_str in process_ids:
            if add_ye:
                # 避免重复添加ye后缀（忽略大小写）
                if "ye" not in id_file_str.lower():
                    new_id = f"{id_file_str}ye"
                    cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, id_file_str))
                    update_count += 1
            else:
                # 删除所有大小写的ye后缀（YE/Ye/ye）
                if "ye" in id_file_str.lower():
                    new_id = id_file_str.replace("ye", "").replace("YE", "")
                    cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, id_file_str))
                    update_count += 1
        
        conn.commit()
        xbmc.log(f"通用逻辑：{'添加' if add_ye else '删除'}ye后缀，共更新{update_count}条记录", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"批量更新ye后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

# ===================== 年份提取与筛选通用函数 =====================
def extract_premiered_year(premiered_str):
    """
    增强版年份提取：支持两种格式
    1. 4位纯数字 → 直接返回整数年份
    2. year-mm-dd → 提取年份部分
    3. 其他情况（空/非上述格式）→ 返回None（提取失败）
    """
    if not premiered_str or not isinstance(premiered_str, (str, unicode) if sys.version_info < (3,) else str):
        return None
    
    premiered_str = premiered_str.strip()
    try:
        # 情况1：4位纯数字
        if re.match(r'^\d{4}$', premiered_str):
            return int(premiered_str)
        # 情况2：year-mm-dd格式
        elif re.match(r'^\d{4}-\d{2}-\d{2}$', premiered_str):
            return int(premiered_str.split('-')[0])
        # 情况3：其他格式（提取失败）
        else:
            return None
    except (ValueError, IndexError):
        # 数字转换失败/格式异常 → 提取失败
        return None

def get_premiered_filtered_idfiles(db_path, filter_type="range", x=None):
    """
    按不同规则筛选idFile列表
    :param filter_type: 
        - lt1970=年份<1970或提取失败（1960参数用）
        - ge1970=年份≥1970（1960参数用）
        - range=年份≥x且<x+10（x参数用）
        - not_range=年份<x或≥x+10或提取失败（x参数2.2用）
    :param x: 基准年份（仅filter_type=range/not_range时需要）
    :return: 符合条件的idFile字符串列表
    """
    if filter_type in ["range", "not_range"] and x is None:
        raise ValueError("筛选类型为range/not_range时必须指定x值")
    
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 查询所有非空idFile及对应的premiered
        cursor.execute("SELECT idFile, premiered FROM movie WHERE idFile IS NOT NULL")
        rows = cursor.fetchall()
        
        target_id_files = []
        for id_file, premiered in rows:
            id_file_str = str(id_file)
            premiered_year = extract_premiered_year(premiered)
            
            if filter_type == "lt1970":
                # 1960参数用：年份<1970 或 提取失败
                if premiered_year is None or premiered_year < 1970:
                    target_id_files.append(id_file_str)
            elif filter_type == "ge1970":
                # 1960参数用：年份≥1970（提取成功）
                if premiered_year is not None and premiered_year >= 1970:
                    target_id_files.append(id_file_str)
            elif filter_type == "range":
                # x参数用：年份≥x且<x+10（提取成功）
                if premiered_year is not None and (x <= premiered_year < x + 10):
                    target_id_files.append(id_file_str)
            elif filter_type == "not_range":
                # x参数2.2用：年份<x或≥x+10 或 提取失败
                if premiered_year is None or premiered_year < x or premiered_year >= x + 10:
                    target_id_files.append(id_file_str)
        
        # 去重避免重复处理
        target_id_files = list(set(target_id_files))
        xbmc.log(f"筛选逻辑：{filter_type}类型，筛选出{len(target_id_files)}条idFile", level=xbmc.LOGINFO)
        return target_id_files
    except sqlite3.Error as e:
        raise Exception(f"筛选premiered失败：{str(e)}")
    finally:
        if conn:
            conn.close()

# ===================== 1960参数专用函数 =====================
def check_any_year_1970_2020mo_1():
    """检查year1970/1980/1990/2000/2010/2020mo是否至少一个值为1"""
    check_years = [1970, 1980, 1990, 2000, 2010, 2020]
    has_any_1 = False
    for year in check_years:
        skin_key = f"year{year}mo"
        value = xbmc.getInfoLabel(f"Skin.String({skin_key})").strip()
        xbmc.log(f"1960参数逻辑：检查{skin_key}值为：{value}", level=xbmc.LOGINFO)
        if value == "1":
            has_any_1 = True
            break
    return has_any_1

def handle_1960_param(db_path):
    """处理1960参数的核心逻辑"""
    # 1. 获取year1960mo的当前值
    year1960mo_key = "year1960mo"
    year1960mo_value = xbmc.getInfoLabel(f"Skin.String({year1960mo_key})").strip()
    xbmc.log(f"1960参数逻辑：当前{year1960mo_key}值为：{year1960mo_value}", level=xbmc.LOGINFO)
    
    # 2. 检查1970-2020系列mo是否有至少一个为1
    any_1970_2020mo_1 = check_any_year_1970_2020mo_1()
    
    try:
        # ========== 分支1：year1960mo = 1 ==========
        if year1960mo_value == "1":
            xbmc.log("1960参数逻辑：进入分支1（year1960mo=1）", level=xbmc.LOGINFO)
            
            # 1.1 其他year mo至少一个=1 → 给年份<1970/提取失败的idFile加ye后缀
            if any_1970_2020mo_1:
                xbmc.log("1960参数逻辑：进入子分支1.1（其他year mo至少一个=1）", level=xbmc.LOGINFO)
                target_ids = get_premiered_filtered_idfiles(db_path, filter_type="lt1970")
                update_movie_idfile_ye_batch(db_path, target_ids, add_ye=True)
                # 设置year1960mo=0
                xbmc.executebuiltin(f'Skin.SetString({year1960mo_key},0)')
                xbmc.log(f"1960参数逻辑：子分支1.1执行完成，设置{year1960mo_key}=0", level=xbmc.LOGINFO)
            
            # 1.2 其他year mo全0/空 → 删除所有idFile的ye后缀
            else:
                xbmc.log("1960参数逻辑：进入子分支1.2（其他year mo全0/空）", level=xbmc.LOGINFO)
                delete_all_ye_from_movie(db_path)
                # 设置year1960mo=0
                xbmc.executebuiltin(f'Skin.SetString({year1960mo_key},0)')
                xbmc.log(f"1960参数逻辑：子分支1.2执行完成，设置{year1960mo_key}=0", level=xbmc.LOGINFO)
        
        # ========== 分支2：year1960mo ≠ 1（包括空） ==========
        else:
            xbmc.log("1960参数逻辑：进入分支2（year1960mo≠1）", level=xbmc.LOGINFO)
            
            # 2.1 其他year mo至少一个=1 → 删除年份<1970/提取失败的idFile的ye后缀
            if any_1970_2020mo_1:
                xbmc.log("1960参数逻辑：进入子分支2.1（其他year mo至少一个=1）", level=xbmc.LOGINFO)
                target_ids = get_premiered_filtered_idfiles(db_path, filter_type="lt1970")
                update_movie_idfile_ye_batch(db_path, target_ids, add_ye=False)
                # 设置year1960mo=1
                xbmc.executebuiltin(f'Skin.SetString({year1960mo_key},1)')
                xbmc.log(f"1960参数逻辑：子分支2.1执行完成，设置{year1960mo_key}=1", level=xbmc.LOGINFO)
            
            # 2.2 其他year mo全0/空 → 给年份≥1970的idFile加ye后缀
            else:
                xbmc.log("1960参数逻辑：进入子分支2.2（其他year mo全0/空）", level=xbmc.LOGINFO)
                target_ids = get_premiered_filtered_idfiles(db_path, filter_type="ge1970")
                update_movie_idfile_ye_batch(db_path, target_ids, add_ye=True)
                # 设置year1960mo=1
                xbmc.executebuiltin(f'Skin.SetString({year1960mo_key},1)')
                xbmc.log(f"1960参数逻辑：子分支2.2执行完成，设置{year1960mo_key}=1", level=xbmc.LOGINFO)
        
        # 刷新容器使修改生效
        xbmc.executebuiltin("Container.Refresh")
        xbmc.log("1960参数逻辑：所有操作完成，已刷新容器", level=xbmc.LOGINFO)
    
    except Exception as e:
        raise Exception(f"1960参数逻辑执行失败：{str(e)}")

# ===================== ALL参数专用函数 =====================
def handle_all_param(db_path):
    """处理all参数的核心逻辑：批量重置year mo + 删除所有ye后缀"""
    try:
        # 1. 批量设置所有year mo为0（1960/1970/1980/1990/2000/2010/2020）
        reset_years = [1960, 1970, 1980, 1990, 2000, 2010, 2020]
        for year in reset_years:
            skin_key = f"year{year}mo"
            xbmc.executebuiltin(f'Skin.SetString({skin_key},0)')
            xbmc.log(f"ALL参数逻辑：已设置{skin_key}=0", level=xbmc.LOGINFO)
        
        # 2. 删除所有idFile的ye/YE后缀
        delete_all_ye_from_movie(db_path)
        
        # 3. 刷新容器
        xbmc.executebuiltin("Container.Refresh")
        xbmc.log("ALL参数逻辑：所有操作执行完成，已刷新容器", level=xbmc.LOGINFO)
    
    except Exception as e:
        raise Exception(f"ALL参数逻辑执行失败：{str(e)}")

# ===================== X参数（1970/1980等）专用函数 =====================
def check_any_year_mo_1_except_x(x):
    """
    检查除yearxmo外，其他year1960/1970/1980/1990/2000/2010/2020mo是否至少一个值为1
    :param x: 排除的年份（1970/1980/1990/2000/2010/2020）
    :return: True=至少一个为1，False=全0/空
    """
    check_years = [1960, 1970, 1980, 1990, 2000, 2010, 2020]
    # 移除当前x，只检查其他年份
    check_years.remove(x)
    
    has_any_1 = False
    for year in check_years:
        skin_key = f"year{year}mo"
        value = xbmc.getInfoLabel(f"Skin.String({skin_key})").strip()
        xbmc.log(f"X参数逻辑：检查{skin_key}（排除{x}mo）值为：{value}", level=xbmc.LOGINFO)
        if value == "1":
            has_any_1 = True
            break
    return has_any_1

def handle_x_param(db_path, x):
    """
    处理x参数的核心逻辑（x=1970/1980/1990/2000/2010/2020）
    """
    # 1. 验证x的有效性
    valid_x = [1970, 1980, 1990, 2000, 2010, 2020]
    if x not in valid_x:
        raise ValueError(f"x参数值无效，仅支持{valid_x}")
    
    # 2. 获取yearxmo的当前值
    yearxmo_key = f"year{x}mo"
    yearxmo_value = xbmc.getInfoLabel(f"Skin.String({yearxmo_key})").strip()
    xbmc.log(f"X参数逻辑：当前{yearxmo_key}值为：{yearxmo_value}", level=xbmc.LOGINFO)
    
    # 3. 检查除x外的其他year mo是否有至少一个为1
    any_other_year_mo_1 = check_any_year_mo_1_except_x(x)
    
    try:
        # ========== 分支1：yearxmo = 1 ==========
        if yearxmo_value == "1":
            xbmc.log(f"X参数逻辑：进入分支1（{yearxmo_key}=1）", level=xbmc.LOGINFO)
            
            # 1.1 其他year mo至少一个=1 → 给年份≥x且<x+10的idFile加ye后缀
            if any_other_year_mo_1:
                xbmc.log(f"X参数逻辑：进入子分支1.1（其他year mo至少一个=1）", level=xbmc.LOGINFO)
                target_ids = get_premiered_filtered_idfiles(db_path, filter_type="range", x=x)
                update_movie_idfile_ye_batch(db_path, target_ids, add_ye=True)
                # 设置yearxmo=0
                xbmc.executebuiltin(f'Skin.SetString({yearxmo_key},0)')
                xbmc.log(f"X参数逻辑：子分支1.1执行完成，设置{yearxmo_key}=0", level=xbmc.LOGINFO)
            
            # 1.2 其他year mo全0/空 → 删除所有idFile的ye后缀
            else:
                xbmc.log(f"X参数逻辑：进入子分支1.2（其他year mo全0/空）", level=xbmc.LOGINFO)
                delete_all_ye_from_movie(db_path)
                # 设置yearxmo=0
                xbmc.executebuiltin(f'Skin.SetString({yearxmo_key},0)')
                xbmc.log(f"X参数逻辑：子分支1.2执行完成，设置{yearxmo_key}=0", level=xbmc.LOGINFO)
        
        # ========== 分支2：yearxmo ≠ 1（包括空） ==========
        else:
            xbmc.log(f"X参数逻辑：进入分支2（{yearxmo_key}≠1）", level=xbmc.LOGINFO)
            
            # 2.1 其他year mo至少一个=1 → 删除年份≥x且<x+10的idFile的ye后缀
            if any_other_year_mo_1:
                xbmc.log(f"X参数逻辑：进入子分支2.1（其他year mo至少一个=1）", level=xbmc.LOGINFO)
                target_ids = get_premiered_filtered_idfiles(db_path, filter_type="range", x=x)
                update_movie_idfile_ye_batch(db_path, target_ids, add_ye=False)
                # 设置yearxmo=1
                xbmc.executebuiltin(f'Skin.SetString({yearxmo_key},1)')
                xbmc.log(f"X参数逻辑：子分支2.1执行完成，设置{yearxmo_key}=1", level=xbmc.LOGINFO)
            
            # 2.2 其他year mo全0/空 → 给非x范围的idFile加ye后缀
            else:
                xbmc.log(f"X参数逻辑：进入子分支2.2（其他year mo全0/空）", level=xbmc.LOGINFO)
                target_ids = get_premiered_filtered_idfiles(db_path, filter_type="not_range", x=x)
                update_movie_idfile_ye_batch(db_path, target_ids, add_ye=True)
                # 设置yearxmo=1
                xbmc.executebuiltin(f'Skin.SetString({yearxmo_key},1)')
                xbmc.log(f"X参数逻辑：子分支2.2执行完成，设置{yearxmo_key}=1", level=xbmc.LOGINFO)
        
        # 刷新容器使修改生效
        xbmc.executebuiltin("Container.Refresh")
        xbmc.log(f"X参数逻辑：所有操作完成，已刷新容器", level=xbmc.LOGINFO)
    
    except Exception as e:
        raise Exception(f"{x}参数逻辑执行失败：{str(e)}")

# ===================== 主函数 =====================
def main():
    # Python 2编码兼容处理
    if sys.version_info < (3,):
        reload(sys)
        sys.setdefaultencoding('utf-8')
    
    # 1. 校验参数是否有效
    if len(sys.argv) < 2:
        xbmc.log("Rating脚本：未传入参数，支持\"1960\"/\"all\"/\"1970\"/\"1980\"/\"1990\"/\"2000\"/\"2010\"/\"2020\"，脚本退出", level=xbmc.LOGWARNING)
        return
    
    param = sys.argv[1]
    # 定义有效参数列表
    valid_params = ["1960", "all", "1970", "1980", "1990", "2000", "2010", "2020"]
    if param not in valid_params:
        xbmc.log(f"Rating脚本：参数无效（仅支持{valid_params}），脚本退出", level=xbmc.LOGWARNING)
        return

    try:
        # 2. 获取指定的数据库文件路径
        db_path = get_myvideos_db_path()
        xbmc.log(f"Rating脚本：使用数据库文件：{db_path}", level=xbmc.LOGINFO)

        # 3. 分支处理不同参数
        if param == "all":
            handle_all_param(db_path)
        elif param == "1960":
            handle_1960_param(db_path)
        else:
            # 处理x参数（1970/1980/1990/2000/2010/2020）
            x = int(param)
            handle_x_param(db_path, x)

    except FileNotFoundError as e:
        xbmc.log(f"Rating脚本错误：{str(e)}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().ok("脚本错误", f"数据库文件不存在：\n{str(e)}")
    except sqlite3.Error as e:
        xbmc.log(f"Rating脚本数据库错误：{str(e)}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().ok("数据库错误", f"操作数据库失败：\n{str(e)}")
    except Exception as e:
        xbmc.log(f"Rating脚本执行失败：{str(e)}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().ok("脚本执行失败", f"错误信息：\n{str(e)}")

if __name__ == "__main__":
    main()