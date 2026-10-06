#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：rating.py
功能：
  1. 参数"4"：按rating4mo状态+rating5-9mo状态分支操作idFile的ra后缀
  2. 参数"all"：批量重置rating4-9mo为0 + 删除所有idFile的ra后缀
  3. 参数"x"（5-9）：按ratingxmo状态+排除xmo的4-9mo状态分支操作idFile的ra后缀（rating范围≥x且≤x+1）
兼容：KODI 18-21（Leia/Matrix/Nexus/Omega），Python 2/3
修改点：
  - 无有效目标idFile时，不再跳过数据库操作，而是按逻辑处理全部idFile
  - 2.2分支在无目标数据时，会给所有idFile添加ra后缀（不重复添加）
"""
import sys
import os
import re
import sqlite3
import xbmc
import xbmcvfs
import xbmcgui

def get_kodi_version():
    """获取KODI主版本号（如18、19、20）"""
    version_str = xbmc.getInfoLabel('System.BuildVersion')
    try:
        return int(version_str.split('.')[0])
    except (ValueError, IndexError):
        return 18  # 降级兼容旧版本

def translate_path(virtual_path):
    """兼容新旧版本的路径转换，确保返回字符串类型"""
    kodi_ver = get_kodi_version()
    if kodi_ver >= 19:
        path = xbmcvfs.translatePath(virtual_path)
    else:
        path = xbmc.translatePath(virtual_path)
    
    # 统一转换为字符串（兼容Python 2/3）
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    return str(path)

def extract_numbers(input_str):
    """从字符串中提取所有数字字符，返回纯数字字符串"""
    if not input_str or not isinstance(input_str, (str, unicode) if sys.version_info < (3,) else str):
        return ""
    # 正则匹配所有数字字符
    numbers = re.findall(r'\d+', input_str)
    return ''.join(numbers)

def check_any_rating_5_9mo_1():
    """检查rating5mo到rating9mo是否至少有一个值为1（供参数4使用）"""
    has_any_1 = False
    for num in range(5, 10):
        skin_key = f"rating{num}mo"
        value = xbmc.getInfoLabel(f"Skin.String({skin_key})").strip()
        xbmc.log(f"Rating脚本：检查{skin_key}值为：{value}", level=xbmc.LOGINFO)
        if value == "1":
            has_any_1 = True
            break
    return has_any_1

def check_any_rating_4_9mo_except_x_1(x):
    """检查rating4-9mo中排除ratingxmo后是否至少有一个值为1（供参数x使用）"""
    has_any_1 = False
    for num in range(4, 10):
        if num == x:  # 排除当前x对应的mo
            continue
        skin_key = f"rating{num}mo"
        value = xbmc.getInfoLabel(f"Skin.String({skin_key})").strip()
        xbmc.log(f"Rating脚本：检查{skin_key}（排除{x}mo）值为：{value}", level=xbmc.LOGINFO)
        if value == "1":
            has_any_1 = True
            break
    return has_any_1

def delete_all_ra_from_movie(db_path):
    """删除movie表idFile列所有ra后缀（复用函数）"""
    conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
    cursor = conn.cursor()
    # 全局删除ra（大小写）
    cursor.execute("""
        UPDATE movie 
        SET idFile = REPLACE(REPLACE(IFNULL(idFile, ''), 'ra', ''), 'RA', '')
        WHERE idFile LIKE '%ra%' OR idFile LIKE '%RA%'
    """)
    delete_count = cursor.rowcount
    conn.commit()
    conn.close()
    xbmc.log(f"Rating脚本：已删除movie表中{delete_count}条记录的ra后缀（大小写）", level=xbmc.LOGINFO)

def handle_all_param(db_path):
    """处理"all"参数的核心逻辑：重置rating4-9mo为0 + 删除所有ra后缀"""
    try:
        # 1. 批量设置rating4mo到rating9mo为0
        for num in range(4, 10):
            skin_key = f"rating{num}mo"
            xbmc.executebuiltin(f'Skin.SetString({skin_key},0)')
            xbmc.log(f"Rating脚本：已设置Skin字符串 {skin_key}=0", level=xbmc.LOGINFO)
        
        # 2. 删除所有ra后缀
        delete_all_ra_from_movie(db_path)
        
        # 3. 刷新容器
        xbmc.executebuiltin("Container.Refresh")
        xbmc.log("Rating脚本：all参数逻辑执行完成，已刷新容器", level=xbmc.LOGINFO)
        
    except sqlite3.Error as e:
        raise Exception(f"all参数数据库操作失败：{str(e)}")

def handle_4_param(db_path, rating4mo_value):
    """处理"4"参数的核心逻辑"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()

        # 通用步骤：查询movie_view中rating<5.0或空的idFile，仅保留数字
        cursor.execute("""
            SELECT idFile FROM movie_view 
            WHERE (rating < 5.0 OR rating IS NULL) AND idFile IS NOT NULL
        """)
        raw_id_files = [str(row[0]) for row in cursor.fetchall() if row[0] is not None]
        # 提取纯数字并去重
        target_id_numbers = list(set([extract_numbers(idf) for idf in raw_id_files]))
        target_id_numbers = [num for num in target_id_numbers if num]
        xbmc.log(f"Rating脚本：找到{len(target_id_numbers)}条有效数字idFile（rating<5.0或空）", level=xbmc.LOGINFO)

        # 修改点1：无有效目标时不跳过，仅日志提示并重置Skin字符串，继续执行后续逻辑
        if not target_id_numbers:
            xbmc.log("Rating脚本：无有效目标idFile记录，将按逻辑处理全部idFile", level=xbmc.LOGINFO)
            # 无数据时重置Skin字符串（保留）
            if rating4mo_value == "1":
                xbmc.executebuiltin('Skin.SetString(rating4mo,0)')
                xbmc.log("Rating脚本：无目标数据，先重置rating4mo=0", level=xbmc.LOGINFO)
            else:
                xbmc.executebuiltin('Skin.SetString(rating4mo,1)')
                xbmc.log("Rating脚本：无目标数据，先重置rating4mo=1", level=xbmc.LOGINFO)
        # 移除原有的return语句，确保后续逻辑执行

        # 分支1：rating4mo=1的情况
        if rating4mo_value == "1":
            xbmc.log("Rating脚本：进入分支1（rating4mo=1）", level=xbmc.LOGINFO)
            # 检查rating5-9mo是否至少有一个为1
            any_5_9mo_is_1 = check_any_rating_5_9mo_1()
            
            # 1.1 子分支：rating5-9mo至少一个=1 → 给目标idFile加ra后缀
            if any_5_9mo_is_1:
                xbmc.log("Rating脚本：分支1.1（rating5-9mo至少一个=1）：为目标idFile加ra后缀", level=xbmc.LOGINFO)
                update_count = 0
                cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
                all_movie_ids = cursor.fetchall()
                
                for (movie_id,) in all_movie_ids:
                    movie_id_str = str(movie_id)
                    movie_id_num = extract_numbers(movie_id_str)
                    # 匹配目标数字+未包含ra → 加后缀（无目标时此条件恒为False，update_count=0）
                    if movie_id_num in target_id_numbers and "ra" not in movie_id_str.lower():
                        new_id = f"{movie_id_str}ra"
                        cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                        update_count += 1
                conn.commit()
                xbmc.log(f"Rating脚本：分支1.1执行完成，共为{update_count}条记录添加ra后缀", level=xbmc.LOGINFO)
                
                # 设置rating4mo=0
                xbmc.executebuiltin('Skin.SetString(rating4mo,0)')
                xbmc.log("Rating脚本：分支1.1执行完成，重置rating4mo=0", level=xbmc.LOGINFO)
            
            # 1.2 子分支：rating5-9mo全为0/空 → 删除所有ra后缀
            else:
                xbmc.log("Rating脚本：分支1.2（rating5-9mo全为0/空）：删除所有ra后缀", level=xbmc.LOGINFO)
                # 关闭当前连接，调用复用函数删除所有ra
                conn.close()
                delete_all_ra_from_movie(db_path)
                # 重新连接（保证连接完整性）
                conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
                
                # 设置rating4mo=0
                xbmc.executebuiltin('Skin.SetString(rating4mo,0)')
                xbmc.log("Rating脚本：分支1.2执行完成，重置rating4mo=0", level=xbmc.LOGINFO)

        # 分支2：rating4mo≠1的情况
        else:
            xbmc.log("Rating脚本：进入分支2（rating4mo≠1）", level=xbmc.LOGINFO)
            # 检查是否存在ra
            cursor.execute("SELECT COUNT(*) FROM movie WHERE idFile LIKE '%ra%' AND idFile IS NOT NULL")
            has_ra = cursor.fetchone()[0] > 0
            
            # 2.1 子分支：存在ra → 删除目标idFile的ra
            if has_ra:
                xbmc.log("Rating脚本：分支2.1（存在ra）：删除目标idFile中的所有ra", level=xbmc.LOGINFO)
                update_count = 0
                cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
                all_movie_ids = cursor.fetchall()
                
                for (movie_id,) in all_movie_ids:
                    movie_id_str = str(movie_id)
                    movie_id_num = extract_numbers(movie_id_str)
                    if movie_id_num in target_id_numbers:
                        new_id = movie_id_str.replace("ra", "").replace("RA", "")
                        if new_id != movie_id_str:
                            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                            update_count += 1
                conn.commit()
                xbmc.log(f"Rating脚本：分支2.1执行完成，共删除{update_count}条记录的ra", level=xbmc.LOGINFO)
                
                # 设置rating4mo=1
                xbmc.executebuiltin('Skin.SetString(rating4mo,1)')
                xbmc.log("Rating脚本：分支2.1执行完成，重置rating4mo=1", level=xbmc.LOGINFO)
            
            # 2.2 子分支：无ra → 非目标idFile加ra（无目标时"非目标"=所有idFile）
            else:
                xbmc.log("Rating脚本：分支2.2（无ra）：给非目标idFile加ra后缀", level=xbmc.LOGINFO)
                update_count = 0
                cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
                all_movie_ids = cursor.fetchall()
                
                for (movie_id,) in all_movie_ids:
                    movie_id_str = str(movie_id)
                    movie_id_num = extract_numbers(movie_id_str)
                    # 非目标数字+未包含ra → 加后缀（无目标时movie_id_num not in []恒为True）
                    if movie_id_num not in target_id_numbers and "ra" not in movie_id_str.lower():
                        new_id = f"{movie_id_str}ra"
                        cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                        update_count += 1
                conn.commit()
                xbmc.log(f"Rating脚本：分支2.2执行完成，共为{update_count}条记录加ra后缀", level=xbmc.LOGINFO)
                
                # 设置rating4mo=1
                xbmc.executebuiltin('Skin.SetString(rating4mo,1)')
                xbmc.log("Rating脚本：分支2.2执行完成，重置rating4mo=1", level=xbmc.LOGINFO)

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"4参数数据库操作失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def handle_x_param(db_path, x):
    """处理参数x（5-9）的核心逻辑（修正rating范围为≥x且≤x+1）"""
    # 1. 获取ratingxmo的值
    rating_xmo_key = f"rating{x}mo"
    rating_xmo_value = xbmc.getInfoLabel(f"Skin.String({rating_xmo_key})").strip()
    xbmc.log(f"Rating脚本：当前{rating_xmo_key}值为：{rating_xmo_value}", level=xbmc.LOGINFO)

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()

        # 2. 通用步骤：查询movie_view中rating ≥x 且 ≤x+1的idFile，仅保留数字（核心修正）
        cursor.execute(f"""
            SELECT idFile FROM movie_view 
            WHERE rating >= {x} AND rating <= {x+1} AND idFile IS NOT NULL
        """)
        raw_id_files = [str(row[0]) for row in cursor.fetchall() if row[0] is not None]
        # 提取纯数字并去重
        target_id_numbers = list(set([extract_numbers(idf) for idf in raw_id_files]))
        target_id_numbers = [num for num in target_id_numbers if num]
        xbmc.log(f"Rating脚本：找到{len(target_id_numbers)}条有效数字idFile（rating≥{x}且≤{x+1}）", level=xbmc.LOGINFO)

        # 修改点2：无有效目标时不跳过，仅日志提示并重置Skin字符串，继续执行后续逻辑
        if not target_id_numbers:
            xbmc.log(f"Rating脚本：无有效目标idFile记录（rating≥{x}且≤{x+1}），将按逻辑处理全部idFile", level=xbmc.LOGINFO)
            # 无数据时先重置Skin字符串（保留）
            if rating_xmo_value == "1":
                xbmc.executebuiltin(f'Skin.SetString({rating_xmo_key},0)')
                xbmc.log(f"Rating脚本：无目标数据，先重置{rating_xmo_key}=0", level=xbmc.LOGINFO)
            else:
                xbmc.executebuiltin(f'Skin.SetString({rating_xmo_key},1)')
                xbmc.log(f"Rating脚本：无目标数据，先重置{rating_xmo_key}=1", level=xbmc.LOGINFO)
        # 移除原有的return和提前的Container.Refresh，确保后续逻辑执行

        # 3. 分支1：ratingxmo=1的情况
        if rating_xmo_value == "1":
            xbmc.log(f"Rating脚本：进入分支1（{rating_xmo_key}=1）", level=xbmc.LOGINFO)
            # 检查排除xmo的4-9mo是否至少有一个为1
            any_4_9mo_except_x_is_1 = check_any_rating_4_9mo_except_x_1(x)
            
            # 1.1 子分支：排除xmo后至少一个=1 → 给目标idFile加ra后缀
            if any_4_9mo_except_x_is_1:
                xbmc.log(f"Rating脚本：分支1.1（排除{rating_xmo_key}的4-9mo至少一个=1）：为目标idFile加ra后缀", level=xbmc.LOGINFO)
                update_count = 0
                cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
                all_movie_ids = cursor.fetchall()
                
                for (movie_id,) in all_movie_ids:
                    movie_id_str = str(movie_id)
                    movie_id_num = extract_numbers(movie_id_str)
                    # 匹配目标数字+未包含ra → 加后缀（无目标时此条件恒为False，update_count=0）
                    if movie_id_num in target_id_numbers and "ra" not in movie_id_str.lower():
                        new_id = f"{movie_id_str}ra"
                        cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                        update_count += 1
                conn.commit()
                xbmc.log(f"Rating脚本：分支1.1执行完成，共为{update_count}条记录添加ra后缀", level=xbmc.LOGINFO)
                
                # 设置ratingxmo=0
                xbmc.executebuiltin(f'Skin.SetString({rating_xmo_key},0)')
                xbmc.log(f"Rating脚本：分支1.1执行完成，重置{rating_xmo_key}=0", level=xbmc.LOGINFO)
            
            # 1.2 子分支：排除xmo后全为0/空 → 删除所有ra后缀
            else:
                xbmc.log(f"Rating脚本：分支1.2（排除{rating_xmo_key}的4-9mo全为0/空）：删除所有ra后缀", level=xbmc.LOGINFO)
                # 关闭当前连接，调用复用函数删除所有ra
                conn.close()
                delete_all_ra_from_movie(db_path)
                # 重新连接（保证连接完整性）
                conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
                
                # 设置ratingxmo=0
                xbmc.executebuiltin(f'Skin.SetString({rating_xmo_key},0)')
                xbmc.log(f"Rating脚本：分支1.2执行完成，重置{rating_xmo_key}=0", level=xbmc.LOGINFO)

        # 4. 分支2：ratingxmo≠1的情况
        else:
            xbmc.log(f"Rating脚本：进入分支2（{rating_xmo_key}≠1）", level=xbmc.LOGINFO)
            # 检查是否存在ra
            cursor.execute("SELECT COUNT(*) FROM movie WHERE idFile LIKE '%ra%' AND idFile IS NOT NULL")
            has_ra = cursor.fetchone()[0] > 0
            
            # 2.1 子分支：存在ra → 删除目标idFile的ra
            if has_ra:
                xbmc.log(f"Rating脚本：分支2.1（存在ra）：删除目标idFile中的所有ra", level=xbmc.LOGINFO)
                update_count = 0
                cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
                all_movie_ids = cursor.fetchall()
                
                for (movie_id,) in all_movie_ids:
                    movie_id_str = str(movie_id)
                    movie_id_num = extract_numbers(movie_id_str)
                    if movie_id_num in target_id_numbers:
                        new_id = movie_id_str.replace("ra", "").replace("RA", "")
                        if new_id != movie_id_str:
                            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                            update_count += 1
                conn.commit()
                xbmc.log(f"Rating脚本：分支2.1执行完成，共删除{update_count}条记录的ra", level=xbmc.LOGINFO)
                
                # 设置ratingxmo=1
                xbmc.executebuiltin(f'Skin.SetString({rating_xmo_key},1)')
                xbmc.log(f"Rating脚本：分支2.1执行完成，重置{rating_xmo_key}=1", level=xbmc.LOGINFO)
            
            # 2.2 子分支：无ra → 非目标idFile加ra（无目标时"非目标"=所有idFile）
            else:
                xbmc.log(f"Rating脚本：分支2.2（无ra）：给非目标idFile加ra后缀", level=xbmc.LOGINFO)
                update_count = 0
                cursor.execute("SELECT idFile FROM movie WHERE idFile IS NOT NULL")
                all_movie_ids = cursor.fetchall()
                
                for (movie_id,) in all_movie_ids:
                    movie_id_str = str(movie_id)
                    movie_id_num = extract_numbers(movie_id_str)
                    # 非目标数字+未包含ra → 加后缀（无目标时movie_id_num not in []恒为True）
                    if movie_id_num not in target_id_numbers and "ra" not in movie_id_str.lower():
                        new_id = f"{movie_id_str}ra"
                        cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, movie_id_str))
                        update_count += 1
                conn.commit()
                xbmc.log(f"Rating脚本：分支2.2执行完成，共为{update_count}条记录加ra后缀", level=xbmc.LOGINFO)
                
                # 设置ratingxmo=1
                xbmc.executebuiltin(f'Skin.SetString({rating_xmo_key},1)')
                xbmc.log(f"Rating脚本：分支2.2执行完成，重置{rating_xmo_key}=1", level=xbmc.LOGINFO)

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"{x}参数数据库操作失败：{str(e)}")
    finally:
        if conn:
            conn.close()
    
    # 刷新容器
    xbmc.executebuiltin("Container.Refresh")
    xbmc.log(f"Rating脚本：{x}参数逻辑执行完成，已刷新容器", level=xbmc.LOGINFO)

def main():
    # 1. 检查参数是否有效
    if len(sys.argv) < 2:
        xbmc.log("Rating脚本：未传入参数，脚本退出", level=xbmc.LOGWARNING)
        return
    
    param = sys.argv[1]
    valid_params = ["4", "all"] + [str(x) for x in range(5, 10)]
    if param not in valid_params:
        xbmc.log(f"Rating脚本：参数无效（仅支持{valid_params}），脚本退出", level=xbmc.LOGWARNING)
        return

    try:
        # 2. 获取数据库路径并验证存在性
        userdata_path = translate_path('special://userdata')
        db_path = os.path.join(userdata_path, 'Database', 'MyVideos131.db')
        
        if not xbmcvfs.exists(db_path):
            raise FileNotFoundError(f"数据库文件不存在：{db_path}")
        xbmc.log(f"Rating脚本：找到数据库文件：{db_path}", level=xbmc.LOGINFO)

        # 3. 分支处理不同参数
        if param == "all":
            # 处理all参数
            handle_all_param(db_path)
        elif param == "4":
            # 处理4参数
            rating4mo_value = xbmc.getInfoLabel("Skin.String(rating4mo)").strip()
            xbmc.log(f"Rating脚本：当前rating4mo值为：{rating4mo_value}", level=xbmc.LOGINFO)
            handle_4_param(db_path, rating4mo_value)
            # 刷新容器
            xbmc.executebuiltin("Container.Refresh")
            xbmc.log("Rating脚本：4参数逻辑执行完成，已刷新容器", level=xbmc.LOGINFO)
        else:
            # 处理5-9参数x
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
    # Python 2编码兼容
    if sys.version_info < (3,):
        reload(sys)
        sys.setdefaultencoding('utf-8')
    main()