#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KODI脚本：仅执行一次的tvshow_view视图重建（带执行标记+皮肤字符串设置）
核心：填充tvshow表原有c23字段的空位（同步rating表tvshow类型数据）
运行方式：RunScript(special://skin/scripts/filtertv.py)
"""

import xbmc
import xbmcvfs
import sqlite3
import os

# 定义唯一标记（可自定义，用于标识当前视图版本）
VIEW_VERSION = "tvshow_view_v1.0"
# 标记表名（避免与KODI原有表冲突）
FLAG_TABLE = "filtertv_exec_flag"
# 皮肤字符串键名
SKIN_STRING_KEY = "tvshow_view"
# ========== 修改点1：皮肤字符串值从1改为2 ==========
SKIN_STRING_VALUE = "2"
# 目标字段（使用原有c23字段）
TARGET_COLUMN = "c23"

def get_database_path():
    """获取MyVideos131.db的完整路径"""
    userdata_path = xbmcvfs.translatePath("special://userdata/")
    db_path = os.path.join(userdata_path, "Database", "MyVideos131.db")
    return xbmcvfs.validatePath(db_path)

def create_flag_table(cursor):
    """创建执行标记表（不存在时创建）"""
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {FLAG_TABLE} (
        view_version TEXT PRIMARY KEY,  -- 视图版本（唯一标识）
        exec_flag INTEGER DEFAULT 1,    -- 执行标记：2=已执行，其他=未执行
        exec_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 最后执行时间
    );
    """
    try:
        cursor.execute(create_table_sql)
        xbmc.log(f"[FilterTV] 标记表{FLAG_TABLE}检查/创建成功", level=xbmc.LOGINFO)
        return True
    except sqlite3.Error as e:
        xbmc.log(f"[FilterTV] 创建标记表失败：{e}", level=xbmc.LOGERROR)
        return False

def check_exec_flag(cursor):
    """检查执行标记：存在且为2则返回True（跳过视图重建），否则返回False"""
    try:
        # 查询当前视图版本的标记
        cursor.execute(f"""
            SELECT exec_flag FROM {FLAG_TABLE} WHERE view_version = ?;
        """, (VIEW_VERSION,))
        result = cursor.fetchone()
        
        # ========== 修改点2：判断逻辑从==1改为==2 ==========
        if result and result[0] == 2:
            # 标记存在且为2 → 跳过视图重建，但仍执行c23字段空位填充
            xbmc.log(f"[FilterTV] 检测到已执行标记（版本{VIEW_VERSION}），跳过视图重建", level=xbmc.LOGINFO)
            return True
        else:
            # 标记不存在/不为2 → 需要执行视图重建
            xbmc.log(f"[FilterTV] 未检测到有效执行标记（标记≠2），将执行视图重建", level=xbmc.LOGINFO)
            return False
    except sqlite3.Error as e:
        # 表不存在/查询失败 → 视为需要执行视图重建
        xbmc.log(f"[FilterTV] 检查标记失败，将执行视图重建：{e}", level=xbmc.LOGWARNING)
        return False

def update_exec_flag(cursor):
    """更新执行标记：存在则更新，不存在则插入"""
    try:
        # 先尝试更新（UPSERT语法，SQLite 3.24+支持，KODI内置SQLite满足）
        # ========== 修改点3：exec_flag值从1改为2 ==========
        cursor.execute(f"""
            INSERT INTO {FLAG_TABLE} (view_version, exec_flag, exec_time)
            VALUES (?, 2, CURRENT_TIMESTAMP)
            ON CONFLICT(view_version) DO UPDATE SET
                exec_flag = 2,
                exec_time = CURRENT_TIMESTAMP;
        """, (VIEW_VERSION,))
        xbmc.log(f"[FilterTV] 执行标记更新成功（版本{VIEW_VERSION}，标记值=2）", level=xbmc.LOGINFO)
        return True
    except sqlite3.Error as e:
        xbmc.log(f"[FilterTV] 更新执行标记失败：{e}", level=xbmc.LOGERROR)
        return False

def set_skin_string():
    """执行KODI内置命令：Skin.SetString(tvshow_view,2)"""
    try:
        # 构建内置命令并执行（值已通过常量改为2）
        builtin_cmd = f"Skin.SetString({SKIN_STRING_KEY},{SKIN_STRING_VALUE})"
        xbmc.executebuiltin(builtin_cmd)
        xbmc.log(f"[FilterTV] 成功执行皮肤字符串设置：{builtin_cmd}", level=xbmc.LOGINFO)
        return True
    except Exception as e:
        # 捕获所有异常，避免皮肤字符串设置失败影响核心逻辑
        xbmc.log(f"[FilterTV] 皮肤字符串设置失败：{e}", level=xbmc.LOGWARNING)
        return False

def fill_tvshow_c23_empty(cursor):
    """
    填充tvshow表c23字段的空位（仅处理NULL/空字符串）
    同步rating表中media_type=tvshow且media_id匹配tvshow.idShow的rating值到c23空位
    """
    try:
        # 填充空位的SQL：仅更新c23为空的行，且匹配rating表的tvshow类型数据
        fill_sql = f"""
UPDATE tvshow 
SET {TARGET_COLUMN} = (
    SELECT rating 
    FROM rating 
    WHERE rating.media_id = tvshow.idShow 
      AND rating.media_type = 'tvshow'
) 
WHERE (tvshow.{TARGET_COLUMN} IS NULL OR tvshow.{TARGET_COLUMN} = '')
  AND tvshow.idShow IN (
    SELECT media_id 
    FROM rating 
    WHERE media_type = 'tvshow'
);
        """
        
        # 执行填充SQL
        cursor.execute(fill_sql)
        affected_rows = cursor.rowcount  # 获取受影响的行数
        xbmc.log(f"[FilterTV] 填充tvshow表{TARGET_COLUMN}字段空位完成，受影响行数：{affected_rows}", level=xbmc.LOGINFO)
        return True
    except sqlite3.Error as e:
        xbmc.log(f"[FilterTV] 填充{TARGET_COLUMN}字段空位失败：{e}", level=xbmc.LOGERROR)
        raise  # 抛出异常，触发主逻辑回滚

def rebuild_tvshow_view(cursor):
    """重建tvshow_view视图（原逻辑不变）"""
    create_view_sql = """
CREATE VIEW tvshow_view AS
    SELECT tvshow.*,
           path.idParentPath AS idParentPath,
           path.strPath AS strPath,
           tvshowcounts.dateAdded AS dateAdded,
           lastPlayed,
           totalCount,
           watchedcount,
           totalSeasons,
           rating.rating AS rating,
           rating.votes AS votes,
           rating.rating_type AS rating_type,
           uniqueid.value AS uniqueid_value,
           uniqueid.type AS uniqueid_type,
           tvshowcounts.inProgressCount AS inProgressCount
      FROM tvshow
           LEFT JOIN
           tvshowlinkpath_minview ON tvshowlinkpath_minview.idShow = tvshow.idShow
           LEFT JOIN
           path ON path.idPath = tvshowlinkpath_minview.idPath
           INNER JOIN
           tvshowcounts ON tvshow.idShow = tvshowcounts.idShow
           LEFT JOIN
           rating ON rating.rating_id = tvshow.c04
           LEFT JOIN
           uniqueid ON uniqueid.uniqueid_id = tvshow.c12
      WHERE tvshow.idShow >= 0;
    """
    try:
        cursor.execute(create_view_sql)
        xbmc.log("[FilterTV] tvshow_view视图重建成功", level=xbmc.LOGINFO)
        return True
    except sqlite3.Error as e:
        xbmc.log(f"[FilterTV] 重建视图失败：{e}", level=xbmc.LOGERROR)
        return False

def delete_and_rebuild_tvshow_view():
    """核心逻辑：
    1. 每次运行都执行：c23字段空位填充（同步rating表tvshow数据）
    2. 仅标记≠2时执行：视图重建+执行标记更新（标记为2）
    3. 每次运行都设置皮肤字符串（值为2）
    """
    db_path = get_database_path()
    if not xbmcvfs.exists(db_path):
        xbmc.log(f"[FilterTV] 错误：数据库文件不存在 {db_path}", level=xbmc.LOGERROR)
        return False

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 步骤1：创建标记表（不存在则创建）
        create_flag_table(cursor)  # 即使创建失败，仍继续执行c23填充逻辑

        # 步骤2：【每次运行都执行】填充tvshow表c23字段空位
        try:
            fill_tvshow_c23_empty(cursor)
        except Exception as e:
            xbmc.log(f"[FilterTV] {TARGET_COLUMN}字段空位填充失败，但继续执行后续逻辑：{e}", level=xbmc.LOGWARNING)

        # 步骤3：检查执行标记（仅控制视图重建）
        flag_exists = check_exec_flag(cursor)

        # 步骤4：仅标记≠2时执行视图重建+标记更新
        if not flag_exists:
            # 4.1 删除原有视图
            cursor.execute("DROP VIEW IF EXISTS tvshow_view;")
            xbmc.log("[FilterTV] 原有tvshow_view视图删除成功", level=xbmc.LOGINFO)
            
            # 4.2 重建视图
            if not rebuild_tvshow_view(cursor):
                conn.rollback()
                xbmc.log("[FilterTV] 视图重建失败，事务回滚", level=xbmc.LOGERROR)
                return False

            # 4.3 更新执行标记（标记为已执行，值=2）
            if not update_exec_flag(cursor):
                conn.rollback()
                xbmc.log("[FilterTV] 标记更新失败，事务回滚", level=xbmc.LOGERROR)
                return False

            # 4.4 提交视图重建/标记更新的事务
            conn.commit()
            xbmc.log("[FilterTV] 视图重建+标记更新事务已提交", level=xbmc.LOGINFO)
        else:
            # 有标记（值=2）时，仅提交c23填充操作的事务（如果有）
            try:
                conn.commit()
                xbmc.log(f"[FilterTV] {TARGET_COLUMN}字段空位填充事务已提交", level=xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"[FilterTV] {TARGET_COLUMN}字段空位填充事务提交失败：{e}", level=xbmc.LOGWARNING)

        # 步骤5：【每次运行都执行】设置皮肤字符串（值=2）
        set_skin_string()

        return True

    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            xbmc.log(f"[FilterTV] 数据库被锁定：{e}", level=xbmc.LOGERROR)
        else:
            xbmc.log(f"[FilterTV] 数据库操作错误：{e}", level=xbmc.LOGERROR)
        if conn:
            conn.rollback()
        return False

    except Exception as e:
        xbmc.log(f"[FilterTV] 脚本执行异常：{e}", level=xbmc.LOGERROR)
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()
            xbmc.log("[FilterTV] 数据库连接已关闭", level=xbmc.LOGINFO)

if __name__ == "__main__":
    xbmc.log("[FilterTV] 脚本开始执行", level=xbmc.LOGINFO)
    success = delete_and_rebuild_tvshow_view()
    if success:
        xbmc.log("[FilterTV] 脚本执行完成", level=xbmc.LOGINFO)
    else:
        xbmc.log("[FilterTV] 脚本执行失败", level=xbmc.LOGERROR)   