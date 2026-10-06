#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：rating.py - 适配tvshow表idShow数字运算逻辑
核心功能：
  1. 类型参数x处理：根据Skin.String(genre{x}mo)状态修改tvshow表idShow的数字值
  2. all参数处理：重置所有genrexxmo为0 + 处理tvshow.idShow负数 + 刷新容器
  类型映射：dz=动作/xj=喜剧/aq=爱情/kh=科幻/fz=犯罪/mx=冒险/kb=恐怖/dh=动画/zz=战争/xy=悬疑/ls=历史/yy=音乐/jl=纪录/jt=家庭/jq=剧情/qh=奇幻/js=惊悚/dp=短片
"""
import sys
import os
import re
import sqlite3
import xbmc
import xbmcvfs

# ======================== 核心常量：类型映射（严格按要求定义） ========================
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
# 数字处理相关常量
NEGATIVE_END_DIGITS = {5, 6, 8, 9}  # 负数需要特殊处理的结尾数字
MULTIPLIER = 10000  # 正数运算乘数
ADD_VALUE = 5       # 基础加减值

# ======================== 基础工具函数（适配tvshow） ========================
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

# ======================== idShow数字处理核心函数 ========================
def process_idshow_number(num, process_type="case11"):
    """
    处理idShow数字的核心逻辑
    :param num: 原始idShow数字（整数）
    :param process_type: 处理场景：
        - case11: 1.1场景（目标类型行处理）
        - case12: 1.2场景/ALL场景（全局负数处理）
        - case21: 2.1场景（目标类型行处理）
        - case22: 2.2场景（非目标类型行处理）
    :return: 处理后的数字
    """
    if not isinstance(num, int):
        xbmc.log(f"idShow数字非整数，跳过处理：{num}", level=xbmc.LOGWARNING)
        return num
    
    new_num = num
    last_digit = abs(num) % 10  # 取最后一位数字
    
    # 场景1.2/ALL场景：全局负数结尾5/6/8/9→加5
    if process_type == "case12":
        if num < 0 and last_digit in NEGATIVE_END_DIGITS:
            new_num = num + ADD_VALUE
            xbmc.log(f"负数结尾{last_digit}处理：{num} → {new_num}", level=xbmc.LOGINFO)
    
    # 场景1.1：正数→乘10000+5→负数；负数结尾5/6/8/9→加5；其他负数不变
    elif process_type == "case11":
        if num > 0:
            new_num = -(num * MULTIPLIER + ADD_VALUE)
            xbmc.log(f"正数处理：{num} → {new_num}", level=xbmc.LOGINFO)
        elif num < 0:
            if last_digit in NEGATIVE_END_DIGITS:
                new_num = num + ADD_VALUE
                xbmc.log(f"负数结尾{last_digit}处理：{num} → {new_num}", level=xbmc.LOGINFO)
            # 结尾非5/6/8/9则不变
    
    # 场景2.1：负数结尾5/6/8/9→加5；其他负数不变
    elif process_type == "case21":
        if num < 0:
            if last_digit in NEGATIVE_END_DIGITS:
                new_num = num + ADD_VALUE
                xbmc.log(f"负数结尾{last_digit}处理：{num} → {new_num}", level=xbmc.LOGINFO)
            # 结尾非5/6/8/9则不变
    
    # 场景2.2：非目标类型行处理
    elif process_type == "case22":
        if num > 0:
            new_num = -(num * MULTIPLIER + ADD_VALUE)
            xbmc.log(f"正数处理：{num} → {new_num}", level=xbmc.LOGINFO)
        elif num < 0:
            if last_digit not in NEGATIVE_END_DIGITS:
                new_num = num - ADD_VALUE
                xbmc.log(f"负数结尾{last_digit}处理：{num} → {new_num}", level=xbmc.LOGINFO)
            # 结尾是5/6/8/9则不变
    
    # 最终检查：处理后最后一位是0 且 ≤-10000 → 除以10000变正数（所有场景通用）
    final_num = new_num
    final_last_digit = abs(final_num) % 10
    if final_last_digit == 0 and final_num <= -MULTIPLIER:
        final_num = abs(final_num) // MULTIPLIER
        xbmc.log(f"最终调整：{new_num} → {final_num}（结尾0且≤-{MULTIPLIER}）", level=xbmc.LOGINFO)
    
    return final_num

# ======================== 数据库操作函数（适配tvshow） ========================
def process_tvshow_target_genre(db_path, target_genre_name, process_type):
    """
    处理tvshow表中c08包含目标类型的行的idShow
    :param db_path: 数据库路径
    :param target_genre_name: 目标类型名称（如动作）
    :param process_type: 处理场景（case11/case21）
    :return: 处理的行数
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 查询c08包含目标类型的idShow
        cursor.execute("""
            SELECT idShow FROM tvshow 
            WHERE idShow IS NOT NULL AND c08 LIKE ?
        """, (f'%{target_genre_name}%',))
        target_records = [(row[0],) for row in cursor.fetchall()]
        if not target_records:
            xbmc.log(f"未找到c08包含[{target_genre_name}]的tvshow记录", level=xbmc.LOGINFO)
            return 0
        
        update_count = 0
        for (id_show,) in target_records:
            processed_num = process_idshow_number(id_show, process_type)
            if processed_num != id_show:
                cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (processed_num, id_show))
                update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：处理[{target_genre_name}]类型tvshow，共更新{update_count}条记录（{process_type}）", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"处理目标类型tvshow失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def process_tvshow_all_negative(db_path):
    """
    场景1.2/ALL参数：处理tvshow表中所有结尾为5/6/8/9的负数idShow
    :param db_path: 数据库路径
    :return: 处理的行数
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 查询所有负数idShow
        cursor.execute("""
            SELECT idShow FROM tvshow 
            WHERE idShow IS NOT NULL AND idShow < 0
        """)
        target_records = [(row[0],) for row in cursor.fetchall()]
        if not target_records:
            xbmc.log("未找到tvshow表中的负数idShow", level=xbmc.LOGINFO)
            return 0
        
        update_count = 0
        for (id_show,) in target_records:
            processed_num = process_idshow_number(id_show, "case12")
            if processed_num != id_show:
                cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (processed_num, id_show))
                update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：全局处理tvshow负数idShow，共更新{update_count}条记录（case12/ALL）", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"全局处理tvshow负数失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def process_tvshow_non_target_genre(db_path, target_genre_name):
    """
    场景2.2：处理tvshow表中c08不包含目标类型的行的idShow
    :param db_path: 数据库路径
    :param target_genre_name: 目标类型名称（如动作）
    :return: 处理的行数
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 查询c08不包含目标类型的idShow（无则处理所有）
        cursor.execute("""
            SELECT idShow FROM tvshow 
            WHERE idShow IS NOT NULL AND (c08 NOT LIKE ? OR c08 IS NULL)
        """, (f'%{target_genre_name}%',))
        target_records = [(row[0],) for row in cursor.fetchall()]
        
        # 如果没有非目标类型行，处理所有行
        if not target_records:
            cursor.execute("""
                SELECT idShow FROM tvshow 
                WHERE idShow IS NOT NULL
            """)
            target_records = [(row[0],) for row in cursor.fetchall()]
            xbmc.log(f"未找到非[{target_genre_name}]类型的tvshow，处理所有记录", level=xbmc.LOGINFO)
        
        update_count = 0
        for (id_show,) in target_records:
            processed_num = process_idshow_number(id_show, "case22")
            if processed_num != id_show:
                cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (processed_num, id_show))
                update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：处理非[{target_genre_name}]类型tvshow，共更新{update_count}条记录（case22）", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"处理非目标类型tvshow失败：{str(e)}")
    finally:
        if conn:
            conn.close()

# ======================== all参数处理函数（新增数据库处理逻辑） ========================
def handle_all_parameter():
    """
    处理all参数的逻辑（严格按要求）：
    1. 所有genre{code}mo的Skin.String设为0
    2. 处理tvshow表中所有结尾为5/6/8/9的负数idShow（加5，最终检查转正数）
    3. 刷新当前容器
    """
    xbmc.log("===== 开始处理all参数 =====", level=xbmc.LOGINFO)
    
    # 步骤1：遍历所有类型，设置Skin.String(genre{code}mo) = 0
    for code in ALL_GENRE_CODES:
        skin_key = f"genre{code}mo"
        set_skin_string(skin_key, 0)
    
    # 步骤2：获取数据库路径并处理tvshow表的负数idShow
    try:
        db_path = get_myvideos_db_path()
        process_tvshow_all_negative(db_path)
    except Exception as e:
        xbmc.log(f"ALL参数处理数据库失败：{str(e)}", level=xbmc.LOGERROR)
        raise
    
    # 步骤3：刷新容器
    refresh_container()
    xbmc.log("===== all参数处理完成 =====", level=xbmc.LOGINFO)

# ======================== 类型参数x处理核心函数（严格按新逻辑） ========================
def handle_genre_x_parameter(x_code):
    """处理类型参数x的核心逻辑（严格遵循用户定义的分支规则）"""
    if x_code not in GENRE_MAPPING:
        raise ValueError(f"无效的类型参数：{x_code}，支持的参数：{','.join(ALL_GENRE_CODES)}")
    
    target_genre_name = GENRE_MAPPING[x_code]
    current_skin_key = f"genre{x_code}mo"
    db_path = get_myvideos_db_path()
    
    # 获取当前状态和其他类型状态
    current_skin_val = get_skin_string(current_skin_key)
    other_genre_has_1 = check_other_genre_skin_string_1(x_code)
    
    xbmc.log(f"===== 开始处理参数x={x_code}（对应类型：{target_genre_name}） =====", level=xbmc.LOGINFO)
    xbmc.log(f"当前Skin.String({current_skin_key}) = {current_skin_val}", level=xbmc.LOGINFO)
    xbmc.log(f"其他类型Skin.String是否有1：{other_genre_has_1}", level=xbmc.LOGINFO)
    
    # 第一种情况：Skin.String值等于1
    if current_skin_val == "1":
        # 1.1 其他类型至少有一个是1
        if other_genre_has_1:
            process_tvshow_target_genre(db_path, target_genre_name, "case11")
        # 1.2 其他类型全部是0
        else:
            process_tvshow_all_negative(db_path)
        # 设置Skin.String为0并刷新
        set_skin_string(current_skin_key, 0)
        refresh_container()
    
    # 第二种情况：Skin.String值不等于1（包括空）
    else:
        # 2.1 其他类型至少有一个是1
        if other_genre_has_1:
            process_tvshow_target_genre(db_path, target_genre_name, "case21")
        # 2.2 其他类型全部是0
        else:
            process_tvshow_non_target_genre(db_path, target_genre_name)
        # 设置Skin.String为1并刷新
        set_skin_string(current_skin_key, 1)
        refresh_container()
    
    xbmc.log(f"===== 参数x={x_code}处理完成 =====", level=xbmc.LOGINFO)

# ======================== 主执行入口 ========================
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
        
        # 无参数时提示
        else:
            print("请传入有效参数：all 或 类型简称（如dz/xj/aq等）")
            xbmc.log(f"未传入参数，支持的参数：all / {','.join(ALL_GENRE_CODES)}", level=xbmc.LOGWARNING)
        
    except Exception as e:
        error_msg = f"执行失败：{str(e)}"
        print(error_msg)
        xbmc.log(error_msg, level=xbmc.LOGERROR)