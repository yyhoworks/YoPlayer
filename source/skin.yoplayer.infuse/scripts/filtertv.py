#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KODI脚本：仅执行一次的tvshow_view视图重建（带执行标记）
运行方式：RunScript(special://skin/scripts/filtertv.py)
"""

import xbmc
import xbmcvfs
import sqlite3
import os
import hashlib

# 定义唯一标记（可自定义，用于标识当前视图版本）
VIEW_VERSION = "tvshow_view_v1.0"
# 标记表名（避免与KODI原有表冲突）
FLAG_TABLE = "filtertv_exec_flag"

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
        exec_flag INTEGER DEFAULT 1,    -- 执行标记：1=已执行，0=未执行
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
    """检查执行标记：存在且为1则返回True（跳过执行），否则返回False"""
    try:
        # 查询当前视图版本的标记
        cursor.execute(f"""
            SELECT exec_flag FROM {FLAG_TABLE} WHERE view_version = ?;
        """, (VIEW_VERSION,))
        result = cursor.fetchone()
        
        if result and result[0] == 1:
            # 标记存在且为1 → 已执行过，跳过
            xbmc.log(f"[FilterTV] 检测到已执行标记（版本{VIEW_VERSION}），脚本跳过执行", level=xbmc.LOGINFO)
            return True
        else:
            # 标记不存在/为0 → 需要执行
            xbmc.log(f"[FilterTV] 未检测到有效执行标记，将执行视图重建", level=xbmc.LOGINFO)
            return False
    except sqlite3.Error as e:
        # 表不存在/查询失败 → 视为需要执行
        xbmc.log(f"[FilterTV] 检查标记失败，将执行视图重建：{e}", level=xbmc.LOGWARNING)
        return False

def update_exec_flag(cursor):
    """更新执行标记：存在则更新，不存在则插入"""
    try:
        # 先尝试更新（UPSERT语法，SQLite 3.24+支持，KODI内置SQLite满足）
        cursor.execute(f"""
            INSERT INTO {FLAG_TABLE} (view_version, exec_flag, exec_time)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(view_version) DO UPDATE SET
                exec_flag = 1,
                exec_time = CURRENT_TIMESTAMP;
        """, (VIEW_VERSION,))
        xbmc.log(f"[FilterTV] 执行标记更新成功（版本{VIEW_VERSION}）", level=xbmc.LOGINFO)
        return True
    except sqlite3.Error as e:
        xbmc.log(f"[FilterTV] 更新执行标记失败：{e}", level=xbmc.LOGERROR)
        return False

def rebuild_tvshow_view(cursor):
    """重建tvshow_view视图"""
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
           path ON path.idPath = tvshowlinkpath_minview.idShow
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
    """核心逻辑：检查标记 → 执行操作 → 更新标记"""
    db_path = get_database_path()
    if not xbmcvfs.exists(db_path):
        xbmc.log(f"[FilterTV] 错误：数据库文件不存在 {db_path}", level=xbmc.LOGERROR)
        return False

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        # 步骤1：创建标记表（不存在则创建）
        if not create_flag_table(cursor):
            raise Exception("标记表创建失败")

        # 步骤2：检查执行标记，已执行则直接退出
        if check_exec_flag(cursor):
            conn.close()
            return True

        # 步骤3：执行核心操作（删除+重建视图）
        # 3.1 删除原有视图
        cursor.execute("DROP VIEW IF EXISTS tvshow_view;")
        xbmc.log("[FilterTV] 原有tvshow_view视图删除成功", level=xbmc.LOGINFO)
        
        # 3.2 重建视图
        if not rebuild_tvshow_view(cursor):
            conn.rollback()
            xbmc.log("[FilterTV] 视图重建失败，事务回滚", level=xbmc.LOGERROR)
            return False

        # 步骤4：更新执行标记（标记为已执行）
        if not update_exec_flag(cursor):
            conn.rollback()
            xbmc.log("[FilterTV] 标记更新失败，事务回滚", level=xbmc.LOGERROR)
            return False

        # 步骤5：提交所有事务
        conn.commit()
        xbmc.log("[FilterTV] 所有操作执行成功，事务已提交", level=xbmc.LOGINFO)
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