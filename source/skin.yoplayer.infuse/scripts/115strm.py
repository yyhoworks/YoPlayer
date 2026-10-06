# -*- coding: utf-8 -*-
"""
KODI 115老接口STRM同步脚本 (优化版 - 支持多级嵌套 & 仅silent模式单实例运行)
路径: special://skin/scripts/115strm.py
调用: 
  - 手动模式: RunScript(special://skin/scripts/115strm.py,manual) - 不受单实例限制
  - 静默模式: RunScript(special://skin/scripts/115strm.py,silent) - 单实例运行
功能: 双向同步115open→115（替换URL关键词），支持交互/静默模式，仅静默模式单实例运行
"""

import os
import sys
import shutil
import re
import xbmc
import xbmcgui
import time
import threading

# ==================== 配置 ====================
BASE_PATH = "/storage/videos/strm"
TARGET_DIR_NAME = "115"
SOURCE_PATTERN = "115open"
REPLACE_TARGET = "115"
LOCK_FILE_PATH = os.path.join(BASE_PATH, ".115strm_sync_lock")

# 全局锁对象，用于线程间同步
process_lock = threading.Lock()
is_running = False

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[115STRM_SYNC] {msg}", level)

def acquire_lock(is_silent_mode):
    """获取全局锁，仅在静默模式下限制单实例运行"""
    global is_running
    if not is_silent_mode:
        # 手动模式不限制并发
        return True
    
    if process_lock.acquire(blocking=False):  # 非阻塞获取锁
        if not is_running:
            is_running = True
            process_lock.release()
            return True
        else:
            process_lock.release()
            return False
    else:
        return False

def release_lock(is_silent_mode):
    """释放全局锁，仅在静默模式下才释放"""
    global is_running
    if not is_silent_mode:
        # 手动模式不需要释放锁
        return

    if process_lock.acquire(blocking=True):  # 阻塞获取锁以确保安全
        is_running = False
        process_lock.release()

def create_lock_file(is_silent_mode):
    """创建锁文件，仅在静默模式下创建"""
    if not is_silent_mode:
        return True  # 手动模式不需要锁文件，视为成功
    
    try:
        pid = os.getpid()
        start_time = time.time()
        lock_info = f"{pid}\n{start_time}"
        with open(LOCK_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(lock_info)
        log(f"创建锁文件: {LOCK_FILE_PATH}, PID: {pid}, Start Time: {start_time}")
        return True
    except Exception as e:
        log(f"创建锁文件失败: {str(e)}", xbmc.LOGERROR)
        return False

def remove_lock_file(is_silent_mode):
    """删除锁文件，仅在静默模式下删除"""
    if not is_silent_mode:
        return  # 手动模式不需要删除锁文件

    try:
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
            log(f"删除锁文件: {LOCK_FILE_PATH}")
    except Exception as e:
        log(f"删除锁文件失败: {str(e)}", xbmc.LOGERROR)

def check_and_clean_stale_lock(is_silent_mode):
    """检查并清理过期的锁文件，仅在静默模式下检查"""
    if not is_silent_mode:
        return True  # 手动模式不需要检查锁文件，视为可以继续

    if not os.path.exists(LOCK_FILE_PATH):
        return True  # 锁文件不存在，可以继续
    
    try:
        with open(LOCK_FILE_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) >= 2:
                stored_pid = int(lines[0].strip())
                start_time = float(lines[1].strip())
                current_time = time.time()
                
                # 检查进程是否仍然存在（仅在Unix-like系统有效）
                try:
                    # 尝试向进程发送信号0来检查是否存在（不会实际发送信号）
                    os.kill(stored_pid, 0)
                    # 如果进程存在，检查运行时间是否过长（假设最大运行时间为1小时）
                    if current_time - start_time > 3600:
                        log(f"检测到过期锁文件，进程{stored_pid}运行超时，清理锁文件")
                        os.remove(LOCK_FILE_PATH)
                        return True
                except OSError:
                    # 进程不存在，清理锁文件
                    log(f"检测到失效锁文件，进程{stored_pid}不存在，清理锁文件")
                    os.remove(LOCK_FILE_PATH)
                    return True
            else:
                # 锁文件格式不正确，删除它
                log("锁文件格式不正确，清理锁文件")
                os.remove(LOCK_FILE_PATH)
                return True
    except Exception as e:
        log(f"检查锁文件时出错: {str(e)}", xbmc.LOGERROR)
        # 如果读取锁文件出错，尝试删除它
        try:
            os.remove(LOCK_FILE_PATH)
        except:
            pass
        return True
    
    # 锁文件有效且进程正在运行
    return False

def safe_replace_first(content, old_str, new_str):
    """不区分大小写替换内容中首次出现的字符串"""
    pattern = re.compile(re.escape(old_str), re.IGNORECASE)
    return pattern.sub(new_str, content, count=1)

def find_case_insensitive_match(directory, target_name):
    """在目录中查找不区分大小写的匹配项"""
    if not os.path.isdir(directory):
        return None, None
    target_lower = target_name.lower()
    for item in os.listdir(directory):
        if item.lower() == target_lower:
            return os.path.join(directory, item), item
    return None, None

# ==================== 增量同步: 115open → 115 ====================
def sync_incremental(source_dir, target_dir, stats):
    os.makedirs(target_dir, exist_ok=True)
    
    try:
        for item in os.listdir(source_dir):
            src_path = os.path.join(source_dir, item)
            if not os.path.exists(src_path):
                continue
                
            if os.path.isfile(src_path) and item.lower().endswith('.strm'):
                _, existing_name = find_case_insensitive_match(target_dir, item)
                if existing_name is None:
                    dst_path = os.path.join(target_dir, item)
                    try:
                        shutil.copy2(src_path, dst_path)
                        with open(dst_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        new_content = safe_replace_first(content, SOURCE_PATTERN, REPLACE_TARGET)
                        with open(dst_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        stats['added'] += 1
                        log(f"新增: {os.path.relpath(dst_path, BASE_PATH)}")
                    except Exception as e:
                        log(f"处理文件失败 {src_path}: {str(e)}", xbmc.LOGERROR)
                        if os.path.exists(dst_path):
                            try: os.remove(dst_path)
                            except: pass
                continue
            
            if os.path.isdir(src_path):
                _, target_sub_name = find_case_insensitive_match(target_dir, item)
                tgt_sub_path = os.path.join(target_dir, target_sub_name if target_sub_name else item)
                sync_incremental(src_path, tgt_sub_path, stats)
    except Exception as e:
        log(f"遍历目录失败 {source_dir}: {str(e)}", xbmc.LOGERROR)

# ==================== 减量清理: 清理115中多余内容 ====================
def clean_decremental(target_dir, source_dir, stats):
    if not os.path.exists(source_dir):
        if os.path.exists(target_dir):
            cnt = sum(1 for _ in os.walk(target_dir) 
                      for f in _[2] if f.lower().endswith('.strm'))
            try:
                shutil.rmtree(target_dir)
                stats['deleted'] += cnt
                log(f"删除整个目录(源不存在): {target_dir} | {cnt}个文件")
            except Exception as e:
                log(f"删除目录失败 {target_dir}: {str(e)}", xbmc.LOGERROR)
        return
    
    if not os.path.isdir(target_dir):
        return
        
    try:
        for item in os.listdir(target_dir):
            tgt_path = os.path.join(target_dir, item)
            if not os.path.exists(tgt_path):
                continue
                
            src_match_path, _ = find_case_insensitive_match(source_dir, item)
            
            if src_match_path is None:
                if os.path.isfile(tgt_path) and item.lower().endswith('.strm'):
                    try:
                        os.remove(tgt_path)
                        stats['deleted'] += 1
                        log(f"删除多余文件: {os.path.relpath(tgt_path, BASE_PATH)}")
                    except Exception as e:
                        log(f"删除文件失败 {tgt_path}: {str(e)}", xbmc.LOGERROR)
                elif os.path.isdir(tgt_path):
                    cnt = sum(1 for _ in os.walk(tgt_path) 
                              for f in _[2] if f.lower().endswith('.strm'))
                    try:
                        shutil.rmtree(tgt_path)
                        stats['deleted'] += cnt
                        log(f"删除多余目录: {os.path.relpath(tgt_path, BASE_PATH)} | {cnt}个文件")
                    except Exception as e:
                        log(f"删除目录失败 {tgt_path}: {str(e)}", xbmc.LOGERROR)
            else:
                if os.path.isdir(tgt_path) and os.path.isdir(src_match_path):
                    clean_decremental(tgt_path, src_match_path, stats)
    except Exception as e:
        log(f"清理目录失败 {target_dir}: {str(e)}", xbmc.LOGERROR)

# ==================== 主流程 ====================
def main():
    # ============ 参数验证 ============
    if len(sys.argv) < 2 or sys.argv[1] not in ["manual", "silent"]:
        log("无效参数：需指定 manual 或 silent", xbmc.LOGWARNING)
        return

    is_silent = (sys.argv[1] == "silent")
    mode_str = "静默模式" if is_silent else "手动模式"
    log(f"启动同步 ({mode_str})")
    
    # 根据模式决定是否检查单实例限制
    if not check_and_clean_stale_lock(is_silent):
        log("检测到静默模式下已有实例正在运行，本次执行取消", xbmc.LOGINFO)
        if not is_silent:
            xbmcgui.Dialog().ok("提示", "检测到后台已有同步任务正在运行，请稍后再试。")
        return

    # 尝试获取全局锁
    if not acquire_lock(is_silent):
        log("获取全局锁失败，可能存在并发冲突", xbmc.LOGINFO)
        if not is_silent:
            xbmcgui.Dialog().ok("提示", "获取同步锁失败，可能存在并发冲突。")
        return

    try:
        # 创建锁文件（仅在静默模式下创建）
        if not create_lock_file(is_silent):
            log("创建锁文件失败，取消运行", xbmc.LOGERROR)
            return

        # ============ 基础路径检查 ============
        if not os.path.isdir(BASE_PATH):
            err_msg = f"基础路径不存在: {BASE_PATH}"
            log(err_msg, xbmc.LOGERROR)
            if not is_silent:
                xbmcgui.Dialog().ok("错误", err_msg)
            return

        # ============ 查找115open源目录 (递归搜索所有子目录) ============
        source_dir = None
        for root, dirs, files in os.walk(BASE_PATH):
            # 检查当前层级的目录名 (不区分大小写)
            for dir_name in dirs:
                if dir_name.lower() == SOURCE_PATTERN.lower():
                    source_dir = os.path.join(root, dir_name)
                    log(f"发现源目录: {source_dir}")
                    break
            if source_dir:
                break # 找到后立即停止搜索

        if not source_dir:
            err_msg = "在strm文件夹及其子文件夹中未找到115open文件夹，无法生成115老接口文件夹！"
            log(err_msg, xbmc.LOGERROR)
            if not is_silent:
                xbmcgui.Dialog().ok("提示", err_msg)
            return

        # ============ 处理115目标目录 ============
        parent_dir = os.path.dirname(source_dir)
        target_dir, _ = find_case_insensitive_match(parent_dir, TARGET_DIR_NAME)

        if not target_dir:
            target_dir = os.path.join(parent_dir, TARGET_DIR_NAME)
            try:
                os.makedirs(target_dir, exist_ok=True)
                log(f"创建目标目录: {target_dir}")
            except Exception as e:
                err_msg = f"创建115文件夹失败: {str(e)}"
                log(err_msg, xbmc.LOGERROR)
                if not is_silent:
                    xbmcgui.Dialog().ok("错误", err_msg)
                return
        else:
            log(f"复用目标目录: {target_dir}")

        # ============ 执行双向同步 ============
        stats = {'added': 0, 'deleted': 0}
        try:
            log("=== 增量同步开始 ===")
            sync_incremental(source_dir, target_dir, stats)
            log("=== 减量清理开始 ===")
            clean_decremental(target_dir, source_dir, stats)
        except Exception as e:
            err_msg = f"同步过程发生严重错误: {str(e)}"
            log(err_msg, xbmc.LOGERROR)
            if not is_silent:
                xbmcgui.Dialog().ok("同步错误", err_msg)
            return

        # ============ 结果处理 ============
        summary = (
            f"同步完成 | 新增:{stats['added']} | 删除:{stats['deleted']} | "
            f"路径:{os.path.basename(target_dir)} ({os.path.dirname(target_dir)})"
        )
        log(summary)

        if not is_silent:
            xbmcgui.Dialog().ok(
                "同步完成",
                f"115老接口strm文件夹已同步完成！\n\n"
                f"新增strm文件: {stats['added']} 个\n"
                f"删除strm文件: {stats['deleted']} 个\n\n"
                f"目标路径: {target_dir}"
            )
    finally:
        # 确保锁文件被清理（仅在静默模式下清理）
        remove_lock_file(is_silent)
        # 释放全局锁
        release_lock(is_silent)

if __name__ == "__main__":
    main()