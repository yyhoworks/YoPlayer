# -*- coding: utf-8 -*-
"""
KODI脚本：ratingtv.py（最终版_v18）
核心修改：参数0/4/5-9的2.2场景中，负数idShow分尾数处理（1/4/6/9不变，其他减1）
调用方式：
- RunScript(special://skin/scripts/ratingtv.py, all) # 全量重置+处理
- RunScript(special://skin/scripts/ratingtv.py, 0)   # rating0mo
- RunScript(special://skin/scripts/ratingtv.py, 4)   # rating4mo
- RunScript(special://skin/scripts/ratingtv.py, 5-9) # ratingxmo（x=5-9）
兼容：KODI 18 (Leia) / 19+ (Matrix)
日志关键词：[ratingtv-DETAIL]（步骤）、[ratingtv-ERROR]（错误）、[ratingtv-INFO]（结果）
"""
import xbmc
import xbmcvfs
import sqlite3
import sys
import os

# ===================== 基础工具函数 =====================
def log_detail(msg):
    """详细日志（追踪执行步骤）"""
    xbmc.log(f"[ratingtv-DETAIL] {msg}", level=xbmc.LOGINFO)

def log_info(msg):
    """信息日志（关键结果）"""
    xbmc.log(f"[ratingtv-INFO] {msg}", level=xbmc.LOGINFO)

def log_error(msg):
    """错误日志"""
    xbmc.log(f"[ratingtv-ERROR] {msg}", level=xbmc.LOGERROR)

def get_db_path():
    """获取MyVideos131.db路径（兼容KODI版本）"""
    log_detail("开始获取数据库路径")
    try:
        userdata_path = xbmcvfs.translatePath('special://userdata/')  # KODI 19+
    except AttributeError:
        userdata_path = xbmc.translatePath('special://userdata/')    # KODI 18-
    
    db_path = os.path.join(userdata_path, 'Database', 'MyVideos131.db')
    final_db_path = xbmcvfs.validatePath(db_path)
    log_detail(f"最终数据库路径：{final_db_path}")
    return final_db_path

def get_skin_string(skin_key):
    """获取Skin.String值，空值/非数字返回0"""
    log_detail(f"获取Skin.String({skin_key})的值")
    raw_val = xbmc.getInfoLabel(f'Skin.String({skin_key})').strip()
    try:
        val = int(raw_val) if raw_val else 0
    except ValueError:
        val = 0
        log_error(f"Skin.String({skin_key})值[{raw_val}]非数字，强制返回0")
    log_detail(f"Skin.String({skin_key})最终值：{val}")
    return val

def set_skin_string(skin_key, val):
    """设置Skin.String值并验证"""
    log_detail(f"设置Skin.String({skin_key}) = {val}")
    xbmc.executebuiltin(f'Skin.SetString({skin_key}, {val})')
    after_val = get_skin_string(skin_key)
    log_detail(f"设置后验证：Skin.String({skin_key}) = {after_val}")
    return after_val

def refresh_container():
    """刷新当前容器"""
    log_detail("执行容器刷新：Container.Refresh")
    xbmc.executebuiltin("Container.Refresh")

def validate_x_param(x_str):
    """验证参数x是否为5-9的数字，返回整数或None"""
    try:
        x = int(x_str)
        if 5 <= x <= 9:
            log_info(f"参数x验证通过：{x}（5-9有效范围）")
            return x
        else:
            log_error(f"参数x[{x_str}]超出5-9范围，无效")
            return None
    except ValueError:
        log_error(f"参数x[{x_str}]非数字，无效")
        return None

# ===================== 参数0专用函数 =====================
def get_target_idshows_c23_null(db_path):
    """参数0：tvshow表c23为空的idShow"""
    log_detail("【参数0】查询tvshow表c23为空的idShow")
    target_idshows = []
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute("SELECT idShow FROM tvshow WHERE c23 IS NULL")
        raw_idshows = cursor.fetchall()
        target_idshows = list(set([row[0] for row in raw_idshows])) if raw_idshows else []
        log_info(f"【参数0】c23为空的idShow数量：{len(target_idshows)}")
    except Exception as e:
        log_error(f"【参数0】获取idShow失败：{str(e)}")
    finally:
        if conn:
            conn.close()
    return target_idshows

def check_rating4_5_6_7_8_9mo():
    """参数0：检查rating4/5/6/7/8/9mo是否至少一个为1"""
    log_detail("【参数0】检查rating4/5/6/7/8/9mo")
    check_result = False
    for num in [4,5,6,7,8,9]:
        if get_skin_string(f'rating{num}mo') == 1:
            check_result = True
            break
    log_info(f"【参数0】rating4/5/6/7/8/9mo至少一个为1？{check_result}")
    return check_result

def check_rating0_5_6_7_8_9mo_all_zero():
    """参数0：检查rating0/5/6/7/8/9mo是否全部为0"""
    log_detail("【参数0】检查rating0/5/6/7/8/9mo是否全部为0")
    all_zero = True
    for num in [0,5,6,7,8,9]:
        if get_skin_string(f'rating{num}mo') != 0:
            all_zero = False
            break
    log_info(f"【参数0】rating0/5/6/7/8/9mo全部为0？{all_zero}")
    return all_zero

# ===================== 参数4专用函数 =====================
def get_target_idshows_c23_lt5(db_path):
    """参数4：tvshow表c23<5.0的idShow"""
    log_detail("【参数4】查询tvshow表c23<5.0的idShow")
    target_idshows = []
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute("SELECT idShow FROM tvshow WHERE c23 < 5.0")
        raw_idshows = cursor.fetchall()
        target_idshows = list(set([row[0] for row in raw_idshows])) if raw_idshows else []
        log_info(f"【参数4】c23<5.0的idShow数量：{len(target_idshows)}")
    except Exception as e:
        log_error(f"【参数4】获取idShow失败：{str(e)}")
    finally:
        if conn:
            conn.close()
    return target_idshows

def check_rating0_5_6_7_8_9mo():
    """参数4：检查rating0/5/6/7/8/9mo是否至少一个为1"""
    log_detail("【参数4】检查rating0/5/6/7/8/9mo")
    check_result = False
    for num in [0,5,6,7,8,9]:
        if get_skin_string(f'rating{num}mo') == 1:
            check_result = True
            break
    log_info(f"【参数4】rating0/5/6/7/8/9mo至少一个为1？{check_result}")
    return check_result

# ===================== 参数5-9通用函数 =====================
def get_target_idshows_c23_range(x, db_path):
    """参数x(5-9)：tvshow表c23≥x且≤x+1的idShow"""
    log_detail(f"【参数{x}】查询tvshow表c23≥{x}且≤{x+1}的idShow")
    target_idshows = []
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT idShow FROM tvshow 
            WHERE c23 >= ? AND c23 <= ?
        """, (x, x+1))
        raw_idshows = cursor.fetchall()
        target_idshows = list(set([row[0] for row in raw_idshows])) if raw_idshows else []
        log_info(f"【参数{x}】c23≥{x}且≤{x+1}的idShow数量：{len(target_idshows)}")
    except Exception as e:
        log_error(f"【参数{x}】获取idShow失败：{str(e)}")
    finally:
        if conn:
            conn.close()
    return target_idshows

def check_rating_others_mo(x):
    """参数x(5-9)：检查除ratingxmo外的0/4/5/6/7/8/9mo是否至少一个为1"""
    log_detail(f"【参数{x}】检查除rating{x}mo外的0/4/5/6/7/8/9mo")
    check_result = False
    check_list = [0,4,5,6,7,8,9]
    check_list.remove(x)  # 严格排除当前x
    log_detail(f"【参数{x}】检查列表：{check_list}")
    for num in check_list:
        if get_skin_string(f'rating{num}mo') == 1:
            check_result = True
            break
    log_info(f"【参数{x}】除rating{x}mo外的0/4/5-9mo至少一个为1？{check_result}")
    return check_result

# ===================== 通用数据处理函数 =====================
def process_idshow_value(old_val, scenario):
    """
    处理idShow数值（核心修改：场景4负数分尾数处理）
    scenario: 
    1=1.1场景 2=1.2场景/all场景 3=2.1场景 4=2.2场景（负数分尾数处理）
    """
    log_detail(f"处理idShow值：{old_val}，场景：{scenario}")
    if old_val == 0:
        return old_val
    
    last_digit = abs(old_val) % 10
    new_val = old_val

    # 场景1：1.1（目标idShow处理）
    if scenario == 1:
        if old_val > 0:
            calc_val = old_val * 10000 + 1
            new_val = -calc_val
        elif old_val < 0 and last_digit in (1,4,6,9):
            new_val = old_val + 1
    # 场景2：1.2/all场景（所有结尾1/4/6/9的负数）
    elif scenario == 2:
        if old_val < 0 and last_digit in (1,4,6,9):
            new_val = old_val + 1
    # 场景3：2.1（目标idShow中符合条件的负数）
    elif scenario == 3:
        if old_val < 0 and last_digit in (1,4,6,9):
            new_val = old_val + 1
    # 场景4：2.2场景（核心修改：负数分尾数处理）
    elif scenario == 4:
        if old_val > 0:
            calc_val = old_val * 10000 + 1
            new_val = -calc_val
        elif old_val < 0:
            # 负数处理：尾数1/4/6/9 → 不变；其他 → 减1
            if last_digit in (1,4,6,9):
                log_detail(f"负数{old_val}尾数{last_digit}(1/4/6/9)，保持不变")
                new_val = old_val  # 尾数是1/4/6/9，不变
            else:
                log_detail(f"负数{old_val}尾数{last_digit}(非1/4/6/9)，减1")
                new_val = old_val - 1  # 尾数不是1/4/6/9，减1

    # 最后一位0且≤-10000 → 除以10000转正数
    new_last_digit = abs(new_val) % 10
    if new_last_digit == 0 and new_val <= -10000:
        log_detail(f"处理后值{new_val}最后一位0且≤-10000，转正数：{abs(new_val)//10000}")
        new_val = abs(new_val) // 10000

    log_detail(f"idShow {old_val}处理后：{new_val}")
    return new_val

def update_tvshow_idshows(db_path, target_idshows=None, scenario=1, process_all=False):
    """更新tvshow表idShow字段（严格匹配数值处理规则）"""
    target_idshows = target_idshows if target_idshows is not None else []
    log_detail(f"更新tvshow表，场景：{scenario}，process_all：{process_all}")
    
    conn = None
    update_count = 0
    try:
        conn = sqlite3.connect(db_path, timeout=15)
        cursor = conn.cursor()
        cursor.execute("SELECT idShow FROM tvshow")
        all_idshows = [row[0] for row in cursor.fetchall()]

        if process_all:
            # 1.2/all场景：处理所有idShow
            for old_id in all_idshows:
                new_id = process_idshow_value(old_id, scenario)
                if new_id != old_id:
                    cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (new_id, old_id))
                    update_count += 1
        else:
            if scenario == 4:
                # 2.2场景：处理非目标idShow（无目标则处理所有）
                for old_id in all_idshows:
                    if len(target_idshows) == 0 or old_id not in target_idshows:
                        new_id = process_idshow_value(old_id, scenario)
                        if new_id != old_id:
                            cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (new_id, old_id))
                            update_count += 1
            else:
                # 1.1/2.1场景：处理目标idShow
                for target_id in target_idshows:
                    if target_id in all_idshows:
                        new_id = process_idshow_value(target_id, scenario)
                        if new_id != target_id:
                            cursor.execute("UPDATE tvshow SET idShow = ? WHERE idShow = ?", (new_id, target_id))
                            update_count += 1

        conn.commit()
        log_info(f"tvshow表更新完成，共更新{update_count}条记录")
    except Exception as e:
        if conn:
            conn.rollback()
        log_error(f"更新tvshow表失败：{str(e)}，已回滚")
    finally:
        if conn:
            conn.close()
    return update_count

# ===================== 参数all专用逻辑 =====================
def reset_all_rating_mo():
    """重置rating0/4/5/6/7/8/9mo为0"""
    log_info("开始重置所有rating0/4/5/6/7/8/9mo为0")
    rating_keys = ["rating0mo", "rating4mo", "rating5mo", "rating6mo", "rating7mo", "rating8mo", "rating9mo"]
    for key in rating_keys:
        set_skin_string(key, 0)
    log_info("所有rating0/4/5/6/7/8/9mo已重置为0")

# ===================== 主执行函数 =====================
def main():
    log_detail("="*60 + "脚本开始执行" + "="*60)
    
    # 1. 检查脚本参数
    args = sys.argv[1:]
    log_detail(f"传入参数：{args}")
    if not args or len(args) < 1:
        log_error("错误：未传入参数，支持all/0/4/5/6/7/8/9")
        log_detail("="*60 + "脚本终止" + "="*60)
        return
    current_param = args[0].lower()  # 兼容大小写（如All/ALL）
    log_info(f"当前执行参数：{current_param}")

    # 2. 检查数据库
    db_path = get_db_path()
    if not xbmcvfs.exists(db_path):
        log_error(f"错误：数据库文件不存在 {db_path}")
        log_detail("="*60 + "脚本终止" + "="*60)
        return

    # 3. 分支执行：参数all
    if current_param == "all":
        log_info("===== 执行参数all逻辑 =====")
        # 步骤1：重置所有rating0/4/5/6/7/8/9mo为0
        reset_all_rating_mo()
        # 步骤2：处理所有结尾是1/4/6/9的负数idShow
        log_info("开始处理所有结尾为1/4/6/9的负数idShow")
        update_tvshow_idshows(db_path, scenario=2, process_all=True)
        # 步骤3：刷新容器
        refresh_container()
        log_info("参数all逻辑执行完成")
    
    # 4. 分支执行：参数0
    elif current_param == "0":
        log_info("===== 执行参数0（rating0mo）逻辑 =====")
        rating0mo_val = get_skin_string("rating0mo")
        if rating0mo_val == 1:
            # 分支1：rating0mo=1
            log_info("参数0分支1：rating0mo=1")
            check_result = check_rating4_5_6_7_8_9mo()
            if check_result:
                # 1.1：rating4/5/6/7/8/9mo至少一个为1 → 处理c23为空的idShow
                log_info("参数0子分支1.1：rating4/5/6/7/8/9mo至少一个为1")
                target_idshows = get_target_idshows_c23_null(db_path)
                update_tvshow_idshows(db_path, target_idshows, scenario=1)
                set_skin_string("rating0mo", 0)
                refresh_container()
            else:
                # 1.2：rating4/5/6/7/8/9mo全部为0 → 处理所有结尾1/4/6/9的负数idShow
                log_info("参数0子分支1.2：rating4/5/6/7/8/9mo全部为0")
                update_tvshow_idshows(db_path, scenario=2, process_all=True)
                set_skin_string("rating0mo", 0)
                refresh_container()
        else:
            # 分支2：rating0mo≠1
            log_info("参数0分支2：rating0mo≠1")
            # 记录c23为空的idShow
            target_idshows = get_target_idshows_c23_null(db_path)
            # 第一步：检查rating4/5/6/7/8/9mo是否至少一个为1
            check_4_9_result = check_rating4_5_6_7_8_9mo()
            if check_4_9_result:
                # 2.1：rating4/5/6/7/8/9mo至少一个为1 → 处理目标idShow中符合条件的负数
                log_info("参数0子分支2.1：rating4/5/6/7/8/9mo至少一个为1")
                update_tvshow_idshows(db_path, target_idshows, scenario=3)
                set_skin_string("rating0mo", 1)
                refresh_container()
            else:
                # 第二步：检查rating0/5/6/7/8/9mo是否全部为0
                check_0_5_9_all_zero = check_rating0_5_6_7_8_9mo_all_zero()
                if check_0_5_9_all_zero:
                    # 2.2：rating0/5/6/7/8/9mo全部为0 → 处理非目标idShow（负数分尾数处理）
                    log_info("参数0子分支2.2：rating0/5/6/7/8/9mo全部为0")
                    update_tvshow_idshows(db_path, target_idshows, scenario=4)
                    set_skin_string("rating0mo", 1)
                    refresh_container()

    # 5. 分支执行：参数4
    elif current_param == "4":
        log_info("===== 执行参数4（rating4mo）逻辑 =====")
        rating4mo_val = get_skin_string("rating4mo")
        if rating4mo_val == 1:
            # 分支1：rating4mo=1
            check_result = check_rating0_5_6_7_8_9mo()
            if check_result:
                # 1.1：处理c23<5.0的idShow
                log_info("参数4子分支1.1：rating0/5/6/7/8/9mo至少一个为1")
                target_idshows = get_target_idshows_c23_lt5(db_path)
                update_tvshow_idshows(db_path, target_idshows, scenario=1)
                set_skin_string("rating4mo", 0)
                refresh_container()
            else:
                # 1.2：处理所有结尾1/4/6/9的负数idShow
                log_info("参数4子分支1.2：rating0/5/6/7/8/9mo全部为0")
                update_tvshow_idshows(db_path, scenario=2, process_all=True)
                set_skin_string("rating4mo", 0)
                refresh_container()
        else:
            # 分支2：rating4mo≠1
            log_info("参数4分支2：rating4mo≠1")
            # 记录c23<5.0的idShow
            target_idshows = get_target_idshows_c23_lt5(db_path)
            # 检查rating0/5/6/7/8/9mo是否至少一个为1
            check_result = check_rating0_5_6_7_8_9mo()
            if check_result:
                # 2.1：rating0/5/6/7/8/9mo至少一个为1
                log_info("参数4子分支2.1：rating0/5/6/7/8/9mo至少一个为1")
                update_tvshow_idshows(db_path, target_idshows, scenario=3)
                set_skin_string("rating4mo", 1)
                refresh_container()
            else:
                # 2.2：rating0/5/6/7/8/9mo全部为0（负数分尾数处理）
                log_info("参数4子分支2.2：rating0/5/6/7/8/9mo全部为0")
                update_tvshow_idshows(db_path, target_idshows, scenario=4)
                set_skin_string("rating4mo", 1)
                refresh_container()

    # 6. 分支执行：参数5-9
    elif current_param in ["5","6","7","8","9"]:
        x = validate_x_param(current_param)
        if x is None:
            log_error("参数x无效，脚本终止")
            log_detail("="*60 + "脚本终止" + "="*60)
            return
        log_info(f"===== 执行参数{x}（rating{x}mo）逻辑 =====")
        
        # 获取当前ratingxmo值
        ratingxmo_key = f"rating{x}mo"
        ratingxmo_val = get_skin_string(ratingxmo_key)
        
        if ratingxmo_val == 1:
            # 分支1：ratingxmo=1
            log_info(f"参数{x}分支1：rating{x}mo=1")
            # 检查除ratingxmo外的0/4/5/6/7/8/9mo是否至少一个为1
            check_result = check_rating_others_mo(x)
            if check_result:
                # 1.1：其他ratingmo至少一个为1 → 处理c23≥x且≤x+1的idShow
                log_info(f"参数{x}子分支1.1：除rating{x}mo外的0/4/5-9mo至少一个为1")
                target_idshows = get_target_idshows_c23_range(x, db_path)
                update_tvshow_idshows(db_path, target_idshows, scenario=1)
                set_skin_string(ratingxmo_key, 0)
                refresh_container()
            else:
                # 1.2：其他ratingmo全部为0 → 处理所有结尾1/4/6/9的负数idShow
                log_info(f"参数{x}子分支1.2：除rating{x}mo外的0/4/5-9mo全部为0")
                update_tvshow_idshows(db_path, scenario=2, process_all=True)
                set_skin_string(ratingxmo_key, 0)
                refresh_container()
        else:
            # 分支2：ratingxmo≠1
            log_info(f"参数{x}分支2：rating{x}mo≠1")
            # 记录c23≥x且≤x+1的idShow
            target_idshows = get_target_idshows_c23_range(x, db_path)
            # 检查除ratingxmo外的0/4/5/6/7/8/9mo是否至少一个为1
            check_result = check_rating_others_mo(x)
            if check_result:
                # 2.1：其他ratingmo至少一个为1 → 处理目标idShow中符合条件的负数
                log_info(f"参数{x}子分支2.1：除rating{x}mo外的0/4/5-9mo至少一个为1")
                update_tvshow_idshows(db_path, target_idshows, scenario=3)
                set_skin_string(ratingxmo_key, 1)
                refresh_container()
            else:
                # 2.2：其他ratingmo全部为0（负数分尾数处理）
                log_info(f"参数{x}子分支2.2：除rating{x}mo外的0/4/5-9mo全部为0")
                update_tvshow_idshows(db_path, target_idshows, scenario=4)
                set_skin_string(ratingxmo_key, 1)
                refresh_container()

    # 7. 无效参数
    else:
        log_error(f"错误：参数{current_param}无效，支持all/0/4/5/6/7/8/9")
        log_detail("="*60 + "脚本终止" + "="*60)
        return

    log_info("脚本所有逻辑执行完成（无中断）")
    log_detail("="*60 + "脚本执行结束" + "="*60)

if __name__ == "__main__":
    main()