#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI皮肤脚本：rating.py - 国家区域筛选+idFile ar后缀管理（含all/qt专属逻辑）
核心功能：
  1. 转换KODI虚拟路径为实际路径（兼容新旧版本）
  2. 提取字符串中的纯数字（处理idFile）
  3. 国家参数映射+Skin.String状态判断
  4. 基于区域状态的movie表idFile ar后缀增删（关联c21列国家信息）
  5. Skin.String状态更新+容器刷新
  6. all参数：重置所有区域状态+全局删除ar后缀
  7. qt参数：其他地区专属逻辑（含多选弹窗+自定义地区筛选）
"""
import sys
import os
import re
import sqlite3
import xbmc
import xbmcvfs
import xbmcgui

# ===================== 核心配置 =====================
# 国家参数映射表：key=参数x值，value=(中文名称，英文名称/英文名称列表)
COUNTRY_MAP = {
    "ch": ("中国", "China"),
    "hk": ("香港", ("Hong Kong", "中国香港")),
    "tw": ("台湾", ("Taiwan", "中国台湾")),
    "mg": ("美国", ("USA", "America", "United States of America")),
    "rb": ("日本", "Japan"),
    "hg": ("韩国", "Korea"),
    "tg": ("泰国", "Thailand"),
    "yd": ("印度", "India"),
    "yg": ("英国", ("UK", "United Kingdom")),
    "fg": ("法国", "France"),
    "dg": ("德国", "Germany"),
    "els": ("俄罗斯", "Russia"),
    "qt": ("其他", "Other")
}
# 数据库文件固定路径
DB_FILE_NAME = "MyVideos131.db"
# 所有区域参数列表（不含qt，用于qt逻辑的状态检查）
MAIN_AREA_PARAMS = [k for k in COUNTRY_MAP.keys() if k != "qt"]
# 所有区域参数全量列表（用于all参数）
ALL_AREA_PARAMS = list(COUNTRY_MAP.keys())

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
    
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    return str(path)

def get_myvideos_db_path():
    """获取MyVideos131.db数据库绝对路径"""
    userdata_path = translate_path('special://userdata')
    db_dir = os.path.join(userdata_path, 'Database')
    db_path = os.path.join(db_dir, DB_FILE_NAME)
    
    if not xbmcvfs.exists(db_path):
        raise FileNotFoundError(f"未找到数据库文件：{db_path}")
    return db_path

def get_skin_string(skin_key):
    """读取KODI Skin.String值，返回0/1（空值返回0）"""
    value = xbmc.getInfoLabel(f"Skin.String({skin_key})").strip()
    return "1" if value == "1" else "0"

def set_skin_string(skin_key, value):
    """设置KODI Skin.String值"""
    xbmc.executebuiltin(f'Skin.SetString({skin_key}, {value})')
    xbmc.log(f"设置Skin.String({skin_key}) = {value}", level=xbmc.LOGINFO)

def refresh_container():
    """刷新当前KODI容器"""
    xbmc.executebuiltin("Container.Refresh")
    xbmc.log("执行容器刷新操作", level=xbmc.LOGINFO)

def extract_numbers(input_str):
    """从字符串中提取所有数字字符，返回纯数字字符串"""
    if not input_str or not isinstance(input_str, str if sys.version_info >= (3,) else (str, unicode)):
        return ""
    numbers = re.findall(r'\d+', input_str)
    return ''.join(numbers)

# ===================== QT参数专属工具函数 =====================
def get_excluded_country_names():
    """获取需要排除的国家/地区名称列表（中+英）- 对应ch/hk/tw/mg/rb/hg/tg/yd/yg/fg/dg/els"""
    excluded = []
    for key in MAIN_AREA_PARAMS:
        cn, en = COUNTRY_MAP[key]
        excluded.append(cn)
        if isinstance(en, (tuple, list)):
            excluded.extend(en)
        else:
            excluded.append(en)
    # 去重并转小写（用于匹配）
    excluded_lower = [name.lower() for name in excluded if name]
    return excluded_lower

def get_other_countries_from_db(db_path):
    """读取country表，返回排除列表外的地区名列表"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        # 读取country表的name列
        cursor.execute("SELECT DISTINCT name FROM country WHERE name IS NOT NULL AND name != ''")
        all_countries = [str(row[0]).strip() for row in cursor.fetchall()]
        
        # 筛选出排除列表外的地区
        excluded_lower = get_excluded_country_names()
        other_countries = []
        for country in all_countries:
            if not country.lower() in excluded_lower:
                other_countries.append(country)
        
        # 去重并排序
        other_countries = sorted(list(set(other_countries)))
        xbmc.log(f"从country表读取到排除列表外的地区：{other_countries}", level=xbmc.LOGINFO)
        return other_countries
    except sqlite3.Error as e:
        raise Exception(f"读取country表失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def show_country_selection_dialog(country_list):
    """弹出多选对话框，返回用户选择的地区名列表"""
    if not country_list:
        xbmcgui.Dialog().notification("提示", "未找到排除列表外的地区", xbmcgui.NOTIFICATION_INFO, 3000)
        return []
    
    # 创建多选对话框
    dialog = xbmcgui.Dialog()
    selected_indices = dialog.multiselect(
        "选择需要筛选的其他地区",
        country_list,
        preselect=[],
        useDetails=False
    )
    
    # 处理选择结果
    if selected_indices is None:
        xbmc.log("用户取消了地区选择", level=xbmc.LOGINFO)
        return []
    
    selected_countries = [country_list[i] for i in selected_indices]
    xbmc.log(f"用户选择的地区：{selected_countries}", level=xbmc.LOGINFO)
    return selected_countries

def check_main_area_skin_strings():
    """检查MAIN_AREA_PARAMS（ch/hk等）的Skin.String是否至少一个为1"""
    status_list = []
    for area in MAIN_AREA_PARAMS:
        skin_key = f"area{area}mo"
        status = get_skin_string(skin_key)
        status_list.append(status)
        xbmc.log(f"检查Skin.String({skin_key}) = {status}", level=xbmc.LOGINFO)
    
    has_one_1 = any([s == "1" for s in status_list])
    return has_one_1

# ===================== QT参数专属数据库操作 =====================
def update_idfile_add_ar_for_non_excluded(db_path):
    """
    给movie表中c21列不包含排除列表（ch/hk等）的行添加ar后缀（不重复）
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 构建排除列表的匹配条件
        excluded_lower = get_excluded_country_names()
        exclude_conditions = []
        exclude_params = []
        for name in excluded_lower:
            exclude_conditions.append("LOWER(c21) NOT LIKE ?")
            exclude_params.append(f'%{name}%')
        
        # 查询符合条件的记录（c21不含排除列表 + idFile不含ar）
        query_sql = f"""
            SELECT idFile FROM movie 
            WHERE {' AND '.join(exclude_conditions)}
            AND idFile IS NOT NULL 
            AND LOWER(idFile) NOT LIKE '%ar%'
        """
        cursor.execute(query_sql, exclude_params)
        target_ids = [str(row[0]) for row in cursor.fetchall()]
        
        # 批量更新
        update_count = 0
        for old_id in target_ids:
            new_id = f"{old_id}ar"
            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, old_id))
            update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：给非排除列表的记录添加ar后缀，共更新{update_count}条", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"添加ar后缀（非排除列表）失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def update_idfile_remove_ar_for_selected(db_path, selected_countries):
    """
    删除movie表中c21列包含选中地区名的行的ar后缀
    """
    if not selected_countries:
        xbmc.log("未选择任何地区，跳过删除ar后缀操作", level=xbmc.LOGINFO)
        return 0
    
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 构建选中地区的匹配条件
        select_conditions = []
        select_params = []
        for country in selected_countries:
            select_conditions.append("LOWER(c21) LIKE ?")
            select_params.append(f'%{country.lower()}%')
        
        # 查询符合条件的记录（c21包含选中地区 + idFile含ar）
        query_sql = f"""
            SELECT idFile FROM movie 
            WHERE ({' OR '.join(select_conditions)})
            AND idFile IS NOT NULL 
            AND LOWER(idFile) LIKE '%ar%'
        """
        cursor.execute(query_sql, select_params)
        target_ids = [str(row[0]) for row in cursor.fetchall()]
        
        # 批量更新
        update_count = 0
        for old_id in target_ids:
            new_id = old_id.replace("ar", "").replace("AR", "")
            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, old_id))
            update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：删除选中地区({selected_countries})记录的ar后缀，共更新{update_count}条", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"删除ar后缀（选中地区）失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def update_idfile_add_ar_except_selected(db_path, selected_countries):
    """
    给movie表中c21列不包含选中地区名的行添加ar后缀（不重复）
    """
    if not selected_countries:
        xbmc.log("未选择任何地区，跳过添加ar后缀操作", level=xbmc.LOGINFO)
        return 0
    
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        # 构建选中地区的匹配条件（取反）
        select_conditions = []
        select_params = []
        for country in selected_countries:
            select_conditions.append("LOWER(c21) NOT LIKE ?")
            select_params.append(f'%{country.lower()}%')
        
        # 查询符合条件的记录（c21不含选中地区 + idFile不含ar）
        query_sql = f"""
            SELECT idFile FROM movie 
            WHERE {' AND '.join(select_conditions)}
            AND idFile IS NOT NULL 
            AND LOWER(idFile) NOT LIKE '%ar%'
        """
        cursor.execute(query_sql, select_params)
        target_ids = [str(row[0]) for row in cursor.fetchall()]
        
        # 批量更新
        update_count = 0
        for old_id in target_ids:
            new_id = f"{old_id}ar"
            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, old_id))
            update_count += 1
        
        conn.commit()
        xbmc.log(f"数据库操作：给非选中地区({selected_countries})的记录添加ar后缀，共更新{update_count}条", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"添加ar后缀（非选中地区）失败：{str(e)}")
    finally:
        if conn:
            conn.close()

# ===================== QT参数主处理函数 =====================
def handle_qt_param():
    """
    QT（其他）参数专属逻辑处理
    """
    xbmc.log("开始执行qt参数专属逻辑", level=xbmc.LOGINFO)
    db_path = get_myvideos_db_path()
    qt_skin_key = "areaqtmo"
    qt_skin_value = get_skin_string(qt_skin_key)
    
    try:
        if qt_skin_value == "1":
            # 情况1：Skin.String(areaqtmo) = 1
            main_area_has_one_1 = check_main_area_skin_strings()
            
            if main_area_has_one_1:
                # 1.1 主区域至少一个为1 → 给非排除列表的记录加ar
                update_idfile_add_ar_for_non_excluded(db_path)
            else:
                # 1.2 主区域全部为0 → 全局删除ar后缀
                update_idfile_remove_ar(db_path)
            
            # 设置qt状态为0
            set_skin_string(qt_skin_key, 0)
        
        else:
            # 情况2：Skin.String(areaqtmo) ≠ 1（空/0）
            # 步骤1：读取country表，获取排除列表外的地区
            other_countries = get_other_countries_from_db(db_path)
            if not other_countries:
                xbmcgui.Dialog().notification("提示", "无可用的其他地区可选", xbmcgui.NOTIFICATION_INFO, 3000)
                return
            
            # 步骤2：弹出多选对话框，获取用户选择
            selected_countries = show_country_selection_dialog(other_countries)
            if not selected_countries:
                return  # 用户取消选择
            
            # 步骤3：检查主区域Skin.String状态
            main_area_has_one_1 = check_main_area_skin_strings()
            
            if main_area_has_one_1:
                # 2.1 主区域至少一个为1 → 删除选中地区的ar后缀
                update_idfile_remove_ar_for_selected(db_path, selected_countries)
            else:
                # 2.2 主区域全部为0 → 给非选中地区的记录加ar后缀
                update_idfile_add_ar_except_selected(db_path, selected_countries)
            
            # 设置qt状态为1
            set_skin_string(qt_skin_key, 1)
        
        # 刷新容器
        refresh_container()
        xbmc.log("qt参数专属逻辑执行完成", level=xbmc.LOGINFO)
    
    except Exception as e:
        xbmc.log(f"qt参数逻辑执行失败：{str(e)}", level=xbmc.LOGERROR)
        raise

# ===================== 通用数据库操作函数 =====================
def build_country_conditions(country_cn, country_en):
    """构建国家匹配的SQL条件和参数（支持多英文关键词）"""
    en_list = [country_en] if isinstance(country_en, str) else list(country_en)
    conditions = [f"c21 LIKE ?"]
    params = [f'%{country_cn}%']
    for en in en_list:
        conditions.append(f"c21 LIKE ?")
        params.append(f'%{en}%')
    condition_str = " OR ".join(conditions)
    return condition_str, params

def update_idfile_add_ar(db_path, country_cn, country_en):
    """给指定国家的记录添加ar后缀（不重复）"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        country_condition, country_params = build_country_conditions(country_cn, country_en)
        query_sql = f"""
            SELECT idFile FROM movie 
            WHERE ({country_condition})
            AND idFile IS NOT NULL 
            AND LOWER(idFile) NOT LIKE '%ar%'
        """
        cursor.execute(query_sql, country_params)
        target_ids = [str(row[0]) for row in cursor.fetchall()]
        
        update_count = 0
        for old_id in target_ids:
            new_id = f"{old_id}ar"
            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, old_id))
            update_count += 1
        
        conn.commit()
        en_str = country_en if isinstance(country_en, str) else "/".join(country_en)
        # 修复：将{c21}改为字符串c21（变量未定义错误）
        xbmc.log(f"数据库操作：给c21列包含{country_cn}/{en_str}的记录添加ar后缀，共更新{update_count}条", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"添加ar后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def update_idfile_remove_ar(db_path, country_cn=None, country_en=None):
    """删除ar后缀（可选：仅删除指定国家的记录）"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        query_conditions = ["idFile IS NOT NULL", "LOWER(idFile) LIKE '%ar%'"]
        query_params = []
        if country_cn and country_en:
            country_condition, country_params = build_country_conditions(country_cn, country_en)
            query_conditions.append(f"({country_condition})")
            query_params.extend(country_params)
        
        query_sql = f"SELECT idFile FROM movie WHERE {' AND '.join(query_conditions)}"
        cursor.execute(query_sql, query_params)
        target_ids = [str(row[0]) for row in cursor.fetchall()]
        
        update_count = 0
        for old_id in target_ids:
            new_id = old_id.replace("ar", "").replace("AR", "")
            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, old_id))
            update_count += 1
        
        conn.commit()
        if country_cn:
            en_str = country_en if isinstance(country_en, str) else "/".join(country_en)
            log_msg = f"数据库操作：删除c21列包含{country_cn}/{en_str}的记录的ar后缀，共更新{update_count}条"
        else:
            log_msg = f"数据库操作：全局删除idFile的ar后缀，共更新{update_count}条"
        xbmc.log(log_msg, level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"删除ar后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

def update_idfile_add_ar_except_country(db_path, country_cn, country_en):
    """给非指定国家的记录添加ar后缀（不重复）"""
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
        cursor = conn.cursor()
        
        country_condition, country_params = build_country_conditions(country_cn, country_en)
        query_sql = f"""
            SELECT idFile FROM movie 
            WHERE NOT ({country_condition})
            AND idFile IS NOT NULL 
            AND LOWER(idFile) NOT LIKE '%ar%'
        """
        cursor.execute(query_sql, country_params)
        target_ids = [str(row[0]) for row in cursor.fetchall()]
        
        update_count = 0
        for old_id in target_ids:
            new_id = f"{old_id}ar"
            cursor.execute("UPDATE movie SET idFile = ? WHERE idFile = ?", (new_id, old_id))
            update_count += 1
        
        conn.commit()
        en_str = country_en if isinstance(country_en, str) else "/".join(country_en)
        xbmc.log(f"数据库操作：给c21列不包含{country_cn}/{en_str}的记录添加ar后缀，共更新{update_count}条", level=xbmc.LOGINFO)
        return update_count
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise Exception(f"排除国家添加ar后缀失败：{str(e)}")
    finally:
        if conn:
            conn.close()

# ===================== ALL参数处理函数 =====================
def handle_all_param():
    """ALL参数：重置所有区域状态+全局删除ar后缀"""
    xbmc.log("开始执行all参数逻辑：重置所有区域状态+全局删除ar后缀", level=xbmc.LOGINFO)
    
    # 批量设置所有区域Skin.String为0
    for area in ALL_AREA_PARAMS:
        skin_key = f"area{area}mo"
        set_skin_string(skin_key, 0)
    
    # 全局删除ar后缀
    db_path = get_myvideos_db_path()
    update_idfile_remove_ar(db_path)
    
    # 刷新容器
    refresh_container()
    xbmc.log("all参数逻辑执行完成", level=xbmc.LOGINFO)

# ===================== 单区域（非QT）主逻辑 =====================
def check_other_area_skin_strings(current_x):
    """检查除当前x外的主区域Skin.String是否至少一个为1"""
    other_areas = [k for k in MAIN_AREA_PARAMS if k != current_x]
    other_status = []
    
    for area in other_areas:
        skin_key = f"area{area}mo"
        status = get_skin_string(skin_key)
        other_status.append((area, status))
        xbmc.log(f"检查Skin.String({skin_key}) = {status}", level=xbmc.LOGINFO)
    
    has_one_1 = any([s == "1" for (a, s) in other_status])
    return has_one_1, other_status

def main_logic(x_param):
    """单区域（非QT）主业务逻辑"""
    if x_param == "qt":
        raise ValueError("qt参数请使用专属逻辑处理")
    
    if x_param not in MAIN_AREA_PARAMS:
        raise ValueError(f"无效的国家参数：{x_param}，支持的参数：{MAIN_AREA_PARAMS}")
    
    db_path = get_myvideos_db_path()
    current_skin_key = f"area{x_param}mo"
    current_country_cn, current_country_en = COUNTRY_MAP[x_param]
    current_skin_value = get_skin_string(current_skin_key)
    
    en_log = current_country_en if isinstance(current_country_en, str) else "/".join(current_country_en)
    xbmc.log(f"当前参数x={x_param}，对应{current_country_cn}/{en_log}，Skin.String({current_skin_key})={current_skin_value}", level=xbmc.LOGINFO)
    
    other_has_one_1, _ = check_other_area_skin_strings(x_param)
    
    try:
        if current_skin_value == "1":
            if other_has_one_1:
                update_idfile_add_ar(db_path, current_country_cn, current_country_en)
            else:
                update_idfile_remove_ar(db_path)
            set_skin_string(current_skin_key, 0)
        else:
            if other_has_one_1:
                update_idfile_remove_ar(db_path, current_country_cn, current_country_en)
            else:
                update_idfile_add_ar_except_country(db_path, current_country_cn, current_country_en)
            set_skin_string(current_skin_key, 1)
        
        refresh_container()
        xbmc.log(f"x={x_param} 业务逻辑执行完成", level=xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"x={x_param} 业务逻辑执行失败：{str(e)}", level=xbmc.LOGERROR)
        raise

# ===================== 入口函数 =====================
if __name__ == "__main__":
    # Python 2编码兼容
    if sys.version_info < (3,):
        reload(sys)
        sys.setdefaultencoding('utf-8')
    
    # 解析命令行参数
    if len(sys.argv) < 2:
        print("用法：")
        print("  1. 重置所有区域：script.py all")
        print("  2. 处理其他地区：script.py qt")
        print(f"  3. 处理单个主区域：script.py <国家参数>（支持：{','.join(MAIN_AREA_PARAMS)}）")
        sys.exit(1)
    
    input_param = sys.argv[1].strip().lower()
    
    try:
        # 分支执行
        if input_param == "all":
            handle_all_param()
            print("操作完成：所有区域状态已重置为0，全局ar后缀已删除")
        elif input_param == "qt":
            handle_qt_param()
            print("操作完成：qt参数逻辑执行完毕")
        else:
            main_logic(input_param)
            print(f"操作完成：参数x={input_param}")
    except Exception as e:
        error_msg = f"操作失败：{str(e)}"
        print(error_msg)
        xbmc.log(f"脚本执行失败：{error_msg}", level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification("脚本执行失败", str(e), xbmcgui.NOTIFICATION_ERROR, 5000)
        sys.exit(1)