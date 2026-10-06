# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import os
import time
import sys
from datetime import datetime

# ===================== 详细日志配置 - 全版本兼容 无乱码 =====================
LOG_TAG = "【FUSELIST】"
def log_info(content):
    xbmc.log(f"{LOG_TAG} [INFO] {content}", level=xbmc.LOGINFO)

def log_debug(content):
    xbmc.log(f"{LOG_TAG} [DEBUG] {content}", level=xbmc.LOGDEBUG)

def log_error(content):
    xbmc.log(f"{LOG_TAG} [ERROR] {content}", level=xbmc.LOGERROR)

# ===================== 全局公共常量定义 =====================
LIST_MAX_NUM = 6
PLAYLIST_DIR = xbmcvfs.translatePath("special://userdata/playlists/video/")
CHECK_TIMEOUT = 600  # 监测超时时间 10分钟(秒)，足够用户编辑
CHECK_INTERVAL = 1   # 文件监测间隔 1秒

# ===================== 电影专属常量 (原有，无任何修改) =====================
MOVIE_NAME_PREFIX = "mvname"
MOVIE_PATH_PREFIX = "mvpath"
MOVIE_FILE_PREFIX = "mvlist"
MOVIE_PLAYLIST_FLAG = "<smartplaylist type=\"movies\">"
# 电影空播放列表模板
MOVIE_EMPTY_CONTENT = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<smartplaylist type="movies">
    <name></name>
    <match>all</match>
</smartplaylist>'''

# ===================== 剧集专属常量 (新增，严格按需求配置) =====================
TV_NAME_PREFIX = "tvname"
TV_PATH_PREFIX = "tvpath"
TV_FILE_PREFIX = "tvlist"
TV_PLAYLIST_FLAG = "<smartplaylist type=\"tvshows\">"
# 剧集空播放列表模板
TV_EMPTY_CONTENT = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<smartplaylist type="tvshows">
    <name></name>
    <match>all</match>
</smartplaylist>'''

# ===================== 公共工具函数 (原有，无任何修改) =====================
def get_skin_string(var_name):
    """获取Skin.String变量值，去空处理"""
    skin_val = xbmc.getInfoLabel(f'Skin.String({var_name})').strip()
    log_debug(f"读取皮肤变量 Skin.String({var_name}) = [{skin_val}]")
    return skin_val

def set_skin_string(var_name, var_value):
    """设置Skin.String变量值"""
    log_debug(f"设置皮肤变量 Skin.SetString({var_name}, {var_value})")
    xbmc.executebuiltin(f'Skin.SetString({var_name}, {var_value})')

def reload_kodi_skin():
    """重载KODI皮肤"""
    log_info("执行皮肤重载操作 -> ReloadSkin()")
    xbmc.executebuiltin('ReloadSkin()')

def get_playlist_file_path(file_prefix, index):
    """生成指定前缀+序号的播放列表文件路径"""
    file_name = f"{file_prefix}{index}.xsp"
    file_path = os.path.join(PLAYLIST_DIR, file_name)
    return file_path, file_name

def get_kodi_playlist_path(file_prefix, index):
    """生成Kodi识别的特殊路径 special:// 格式"""
    return f"special://userdata/playlists/video/{file_prefix}{index}.xsp"

def get_playlist_name_from_file(file_path):
    """读取xsp文件中的<name>标签内容 - 加固版 防崩溃"""
    if not xbmcvfs.exists(file_path):
        log_error(f"文件不存在，无法解析列表名: {file_path}")
        return ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            start_tag = "<name>"
            end_tag = "</name>"
            if start_tag in content and end_tag in content:
                start_idx = content.find(start_tag) + len(start_tag)
                end_idx = content.find(end_tag, start_idx)
                playlist_name = content[start_idx:end_idx].strip()
                log_info(f"解析成功，列表名称为: [{playlist_name}]")
                return playlist_name
            else:
                log_error(f"文件中未找到<name>标签，无法获取列表名")
                return ""
    except Exception as e:
        log_error(f"解析文件列表名失败: {str(e)}")
        return ""

def create_empty_playlist(file_path, file_content):
    """创建空的播放列表文件 - 异常捕获加固"""
    log_info(f"开始创建空列表文件: {file_path}")
    if not xbmcvfs.exists(PLAYLIST_DIR):
        log_debug(f"播放列表目录不存在，创建目录: {PLAYLIST_DIR}")
        xbmcvfs.mkdirs(PLAYLIST_DIR)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        log_info(f"空列表文件创建成功: {file_path}")
        return True
    except Exception as e:
        log_error(f"创建空列表文件失败: {str(e)}")
        return False

def wait_playlist_edited(file_path):
    """核心文件监测函数 - 防崩溃全加固版，根治FileNotFoundError"""
    log_info(f"开始监测文件修改状态 -> 目标文件: {file_path}")
    if not xbmcvfs.exists(file_path):
        log_error(f"监测文件不存在，直接返回未修改: {file_path}")
        return False
    origin_mtime = 0
    try:
        origin_mtime = os.path.getmtime(file_path)
    except Exception as e:
        log_error(f"获取文件初始修改时间失败: {str(e)}")
        return False
    
    timeout_count = 0
    while timeout_count < CHECK_TIMEOUT:
        if not xbmcvfs.exists(file_path):
            log_info(f"⚠️ 监测中发现文件已被删除，终止监测，返回主选择窗口")
            return False
        try:
            current_mtime = os.path.getmtime(file_path)
            if current_mtime != origin_mtime:
                log_info(f"✅ 监测到文件已修改保存，执行后续逻辑")
                return True
        except Exception as e:
            log_error(f"读取文件修改时间失败: {str(e)}")
            return False

        timeout_count += CHECK_INTERVAL
        time.sleep(CHECK_INTERVAL)
        log_debug(f"文件未修改，持续监测中... 已等待: {timeout_count}秒 / 超时: {CHECK_TIMEOUT}秒")
    
    log_info(f"⚠️ 文件监测超时，用户未保存/取消编辑操作")
    return False

def get_target_xsp_files(playlist_flag):
    """获取目录下所有包含指定标识的xsp文件列表"""
    log_info(f"检索[{PLAYLIST_DIR}]下所有包含[{playlist_flag}]的xsp文件")
    target_xsp = []
    if not xbmcvfs.exists(PLAYLIST_DIR):
        log_error(f"播放列表目录不存在: {PLAYLIST_DIR}")
        return target_xsp
    all_files = xbmcvfs.listdir(PLAYLIST_DIR)[1]
    for file in all_files:
        if file.endswith('.xsp'):
            file_path = os.path.join(PLAYLIST_DIR, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if playlist_flag in content:
                        modify_time = os.path.getmtime(file_path)
                        target_xsp.append((file_path, modify_time, file))
                        log_debug(f"匹配到目标xsp文件: {file}")
            except Exception as e:
                log_error(f"读取文件失败跳过: {file} | {str(e)}")
                continue
    log_info(f"共检索到 {len(target_xsp)} 个目标xsp文件")
    return target_xsp

# ===================== 公共处理函数 - 新建/替换通用 =====================
def handle_playlist_common(index, name_prefix, path_prefix, file_prefix, empty_content, is_replace):
    """公共新建/替换处理逻辑，适配电影/剧集"""
    file_path, file_name = get_playlist_file_path(file_prefix, index)
    kodi_path = get_kodi_playlist_path(file_prefix, index)
    # 判断文件是否存在，不存在则新建
    if not xbmcvfs.exists(file_path):
        log_info(f"文件[{file_name}]不存在，开始创建空模板")
        create_empty_playlist(file_path, empty_content)
        if not xbmcvfs.exists(file_path):
            log_error(f"文件创建失败，无法继续操作: {file_path}")
            xbmcgui.Dialog().ok("操作失败", "文件创建失败，请重试！")
            return False
    # 打开播放列表编辑器
    log_info(f"打开编辑器: ActivateWindow(SmartPlaylistEditor,{file_path})")
    xbmc.executebuiltin(f'ActivateWindow(SmartPlaylistEditor,{file_path})')
    time.sleep(0.5)
    # 监测文件是否修改 - 超时后静默返回，无弹窗
    is_modified = wait_playlist_edited(file_path)
    if not is_modified:
        log_info(f"文件未修改/被删除/超时，用户取消编辑，静默退出")
        return False
    # 读取文件中的<name>标签内容
    playlist_name = get_playlist_name_from_file(file_path)
    if not playlist_name:
        playlist_name = f"{file_prefix[:2]}列表{index}"
        log_info(f"列表名解析为空，使用默认名称: {playlist_name}")
    # 设置皮肤变量
    set_skin_string(f"{name_prefix}{index}", playlist_name)
    set_skin_string(f"{path_prefix}{index}", kodi_path)
    # 弹出对应提示窗
    dialog = xbmcgui.Dialog()
    if is_replace:
        msg = f"已替换{index}位置展示列表！"
    else:
        msg = "已完成新建展示列表！"
    dialog.ok("操作成功", msg)
    # 重载皮肤
    reload_kodi_skin()
    log_info(f"{msg} 流程执行完毕")
    return True

# -----------------------------------------------------------------------------
# ===================== 原有 MOVIE 电影功能 (全部保留，一字未改) =====================
# -----------------------------------------------------------------------------
def do_create_playlist():
    log_info("="*20 + "开始执行【新建电影首页展示列表】逻辑" + "="*20)
    empty_index = -1
    for i in range(1, LIST_MAX_NUM + 1):
        skin_val = get_skin_string(f"{MOVIE_NAME_PREFIX}{i}")
        if not skin_val:
            empty_index = i
            log_info(f"找到第一个空值列表序号: {empty_index}")
            break
    if empty_index != -1:
        handle_playlist_common(empty_index, MOVIE_NAME_PREFIX, MOVIE_PATH_PREFIX, MOVIE_FILE_PREFIX, MOVIE_EMPTY_CONTENT, False)
    else:
        log_info("所有mvname1~6均为非空，列表已满，弹出替换选择窗口")
        replace_choices = []
        replace_index_map = {}
        for i in range(1, LIST_MAX_NUM + 1):
            skin_val = get_skin_string(f"{MOVIE_NAME_PREFIX}{i}")
            if skin_val:
                replace_choices.append(f"列表{i}：{skin_val}")
                replace_index_map[len(replace_choices)-1] = i
        dialog = xbmcgui.Dialog()
        select_idx = dialog.select("列表已满，请选择替换列表位置", replace_choices)
        if select_idx == -1:
            log_info("用户取消替换选择，静默退出")
            return
        target_index = replace_index_map[select_idx]
        log_info(f"用户选择替换列表序号: {target_index}")
        handle_playlist_common(target_index, MOVIE_NAME_PREFIX, MOVIE_PATH_PREFIX, MOVIE_FILE_PREFIX, MOVIE_EMPTY_CONTENT, True)

def do_edit_playlist():
    log_info("="*20 + "开始执行【编辑已有列表文件】逻辑" + "="*20)
    edit_choices = []
    edit_index_map = {}
    current_idx = 0
    for i in range(1, LIST_MAX_NUM + 1):
        skin_val = get_skin_string(f"{MOVIE_NAME_PREFIX}{i}")
        if skin_val:
            edit_choices.append(f"列表{i}：{skin_val}")
            edit_index_map[current_idx] = i
            current_idx += 1
    if not edit_choices:
        log_info("所有mvname1~6均为空值，无可用列表可编辑")
        xbmcgui.Dialog().ok("提示", "暂无可用的列表文件可编辑！")
        return
    dialog = xbmcgui.Dialog()
    select_idx = dialog.select("选择需要编辑的列表", edit_choices)
    if select_idx == -1:
        log_info("用户取消编辑选择，静默退出")
        return
    log_info(f"用户选择编辑选项序号: {select_idx} -> {edit_choices[select_idx]}")
    target_index = edit_index_map[select_idx]
    file_path, file_name = get_playlist_file_path(MOVIE_FILE_PREFIX, target_index)
    if not xbmcvfs.exists(file_path):
        log_error(f"待编辑文件不存在: {file_path}")
        xbmcgui.Dialog().ok("操作失败", f"{target_index}位置对应的列表文件不存在！")
        return
    log_info(f"打开编辑器: ActivateWindow(SmartPlaylistEditor,{file_path})")
    xbmc.executebuiltin(f'ActivateWindow(SmartPlaylistEditor,{file_path})')
    time.sleep(0.5)
    is_modified = wait_playlist_edited(file_path)
    if not is_modified:
        log_info(f"文件未修改/用户取消编辑/超时，静默退出")
        return
    playlist_name = get_playlist_name_from_file(file_path)
    if not playlist_name:
        playlist_name = f"电影列表{target_index}"
        log_info(f"列表名解析为空，使用默认名称: {playlist_name}")
    set_skin_string(f"{MOVIE_NAME_PREFIX}{target_index}", playlist_name)
    log_info(f"更新皮肤变量 mvname{target_index} = [{playlist_name}]")
    dialog = xbmcgui.Dialog()
    dialog.ok("操作成功", f"{target_index}位置列表文件完成编辑！")
    reload_kodi_skin()
    log_info(f"{target_index}位置列表编辑完成，流程执行完毕")

def do_delete_playlist():
    log_info("="*20 + "开始执行【删除电影首页展示列表】逻辑" + "="*20)
    del_choices = ["删除所有列表"]
    del_index_map = {}
    current_idx = 1
    for i in range(1, LIST_MAX_NUM + 1):
        skin_val = get_skin_string(f"{MOVIE_NAME_PREFIX}{i}")
        if skin_val:
            del_choices.append(f"列表{i}：{skin_val}")
            del_index_map[current_idx] = i
            current_idx += 1
    dialog = xbmcgui.Dialog()
    select_idx = dialog.select("删除电影展示列表", del_choices)
    if select_idx == -1:
        log_info("用户取消删除选择，静默退出")
        return
    log_info(f"用户选择删除选项序号: {select_idx} -> {del_choices[select_idx]}")
    if select_idx == 0:
        log_info("执行【删除所有列表】逻辑")
        movie_xsp_list = get_target_xsp_files(MOVIE_PLAYLIST_FLAG)
        for file_path, _, file_name in movie_xsp_list:
            if xbmcvfs.exists(file_path) and xbmcvfs.delete(file_path):
                log_info(f"成功删除电影xsp文件: {file_name}")
            else:
                log_error(f"删除文件失败/文件不存在: {file_name}")
        time.sleep(0.3)
        for i in range(1, LIST_MAX_NUM + 1):
            set_skin_string(f"{MOVIE_NAME_PREFIX}{i}", "")
            set_skin_string(f"{MOVIE_PATH_PREFIX}{i}", "")
        dialog.ok("操作成功", "已删除所有展示列表！")
        reload_kodi_skin()
    else:
        if select_idx in del_index_map:
            target_index = del_index_map[select_idx]
            log_info(f"执行删除列表序号: {target_index} 逻辑")
            file_path, _ = get_playlist_file_path(MOVIE_FILE_PREFIX, target_index)
            if xbmcvfs.exists(file_path) and xbmcvfs.delete(file_path):
                log_info(f"成功删除文件: {file_path}")
            else:
                log_info(f"文件不存在，跳过删除: {file_path}")
            time.sleep(0.3)
            set_skin_string(f"{MOVIE_NAME_PREFIX}{target_index}", "")
            set_skin_string(f"{MOVIE_PATH_PREFIX}{target_index}", "")
            dialog.ok("操作成功", f"已删除{target_index}位置展示列表!")
            reload_kodi_skin()

def do_reset_playlist():
    log_info("="*20 + "开始执行【重置电影首页展示列表】逻辑" + "="*20)
    dialog = xbmcgui.Dialog()
    confirm = dialog.yesno("重置确认", "此操作将重新排序并清除多余的列表，请确认继续进行！")
    if not confirm:
        log_info("用户取消重置操作，静默退出")
        return
    log_info("开始循环读取 mvlist1~6.xsp 文件，赋值皮肤变量 mvname1~6 和 mvpath1~6")
    for i in range(1, LIST_MAX_NUM + 1):
        file_path, _ = get_playlist_file_path(MOVIE_FILE_PREFIX, i)
        playlist_name = get_playlist_name_from_file(file_path)
        kodi_path = get_kodi_playlist_path(MOVIE_FILE_PREFIX, i)
        set_skin_string(f"{MOVIE_NAME_PREFIX}{i}", playlist_name)
        set_skin_string(f"{MOVIE_PATH_PREFIX}{i}", kodi_path)
        log_info(f"重置赋值完成 → mvname{i} = [{playlist_name}] | mvpath{i} = [{kodi_path}]")
    dialog.ok("操作成功", "已重置所有电影展示列表！")
    reload_kodi_skin()
    log_info("重置电影首页展示列表逻辑执行完毕")

# -----------------------------------------------------------------------------
# ===================== 新增 TVSHOW 剧集功能 (严格按需求开发，完整匹配) =====================
# -----------------------------------------------------------------------------
def do_create_tv_playlist():
    log_info("="*20 + "开始执行【新建剧集首页展示列表】逻辑" + "="*20)
    empty_index = -1
    # 1.1 依次查找第一个为空的tvname序号
    for i in range(1, LIST_MAX_NUM + 1):
        skin_val = get_skin_string(f"{TV_NAME_PREFIX}{i}")
        if not skin_val:
            empty_index = i
            log_info(f"找到第一个空值列表序号: {empty_index}")
            break
    if empty_index != -1:
        handle_playlist_common(empty_index, TV_NAME_PREFIX, TV_PATH_PREFIX, TV_FILE_PREFIX, TV_EMPTY_CONTENT, False)
    # 1.2 所有tvname都不为空，弹出替换选择窗
    else:
        log_info("所有tvname1~6均为非空，列表已满，弹出替换选择窗口")
        replace_choices = []
        replace_index_map = {}
        for i in range(1, LIST_MAX_NUM + 1):
            skin_val = get_skin_string(f"{TV_NAME_PREFIX}{i}")
            if skin_val:
                replace_choices.append(f"列表{i}：{skin_val}")
                replace_index_map[len(replace_choices)-1] = i
        dialog = xbmcgui.Dialog()
        select_idx = dialog.select("列表已满，请选择替换列表位置", replace_choices)
        if select_idx == -1:
            log_info("用户取消替换选择，静默退出")
            return
        target_index = replace_index_map[select_idx]
        log_info(f"用户选择替换列表序号: {target_index}")
        handle_playlist_common(target_index, TV_NAME_PREFIX, TV_PATH_PREFIX, TV_FILE_PREFIX, TV_EMPTY_CONTENT, True)

def do_edit_tv_playlist():
    log_info("="*20 + "开始执行【编辑已有剧集列表文件】逻辑" + "="*20)
    edit_choices = []
    edit_index_map = {}
    current_idx = 0
    # 仅展示tvname序号非空的列表，空值不显示
    for i in range(1, LIST_MAX_NUM + 1):
        skin_val = get_skin_string(f"{TV_NAME_PREFIX}{i}")
        if skin_val:
            edit_choices.append(f"列表{i}：{skin_val}")
            edit_index_map[current_idx] = i
            current_idx += 1
            log_debug(f"添加编辑选项：列表{i}：{skin_val}")
    # 判断是否有可编辑的列表
    if not edit_choices:
        log_info("所有tvname1~6均为空值，无可用列表可编辑")
        xbmcgui.Dialog().ok("提示", "暂无可用的列表文件可编辑！")
        return
    # 弹出编辑选择窗口
    dialog = xbmcgui.Dialog()
    select_idx = dialog.select("选择需要编辑的列表", edit_choices)
    if select_idx == -1:
        log_info("用户取消编辑选择，静默退出")
        return
    log_info(f"用户选择编辑选项序号: {select_idx} -> {edit_choices[select_idx]}")
    # 获取用户选择的列表序号
    target_index = edit_index_map[select_idx]
    file_path, file_name = get_playlist_file_path(TV_FILE_PREFIX, target_index)
    log_info(f"准备编辑列表序号: {target_index} 对应文件: {file_name}")
    # 校验文件是否存在
    if not xbmcvfs.exists(file_path):
        log_error(f"待编辑文件不存在: {file_path}")
        xbmcgui.Dialog().ok("操作失败", f"{target_index}位置对应的列表文件不存在！")
        return
    # 打开播放列表编辑器
    log_info(f"打开编辑器: ActivateWindow(SmartPlaylistEditor,{file_path})")
    xbmc.executebuiltin(f'ActivateWindow(SmartPlaylistEditor,{file_path})')
    time.sleep(0.5)
    # 监测文件是否修改
    is_modified = wait_playlist_edited(file_path)
    if not is_modified:
        log_info(f"文件未修改/用户取消编辑/超时，静默退出")
        return
    # 读取列表名并更新tvname变量（仅更新名称，路径不变）
    playlist_name = get_playlist_name_from_file(file_path)
    if not playlist_name:
        playlist_name = f"剧集列表{target_index}"
        log_info(f"列表名解析为空，使用默认名称: {playlist_name}")
    set_skin_string(f"{TV_NAME_PREFIX}{target_index}", playlist_name)
    log_info(f"更新皮肤变量 tvname{target_index} = [{playlist_name}]")
    # 弹出指定文案确认窗
    dialog.ok("操作成功", f"{target_index}位置列表文件完成编辑！")
    # 重载皮肤
    reload_kodi_skin()
    log_info(f"{target_index}位置列表编辑完成，流程执行完毕")

def do_delete_tv_playlist():
    log_info("="*20 + "开始执行【删除剧集首页展示列表】逻辑" + "="*20)
    del_choices = ["删除所有列表"]
    del_index_map = {}
    current_idx = 1
    # 构建删除选项：仅展示tvname非空的列表
    for i in range(1, LIST_MAX_NUM + 1):
        skin_val = get_skin_string(f"{TV_NAME_PREFIX}{i}")
        if skin_val:
            del_choices.append(f"列表{i}：{skin_val}")
            del_index_map[current_idx] = i
            current_idx += 1
    # 弹出删除选择窗
    dialog = xbmcgui.Dialog()
    select_idx = dialog.select("删除剧集展示列表", del_choices)
    if select_idx == -1:
        log_info("用户取消删除选择，静默退出")
        return
    log_info(f"用户选择删除选项序号: {select_idx} -> {del_choices[select_idx]}")
    # 选项1：删除所有列表 - 删除含tvshows的xsp文件
    if select_idx == 0:
        log_info("执行【删除所有列表】逻辑")
        tv_xsp_list = get_target_xsp_files(TV_PLAYLIST_FLAG)
        for file_path, _, file_name in tv_xsp_list:
            if xbmcvfs.exists(file_path) and xbmcvfs.delete(file_path):
                log_info(f"成功删除剧集xsp文件: {file_name}")
            else:
                log_error(f"删除文件失败/文件不存在: {file_name}")
        time.sleep(0.3)
        # 清空所有tvname和tvpath变量
        for i in range(1, LIST_MAX_NUM + 1):
            set_skin_string(f"{TV_NAME_PREFIX}{i}", "")
            set_skin_string(f"{TV_PATH_PREFIX}{i}", "")
        dialog.ok("操作成功", "已删除所有展示列表！")
        reload_kodi_skin()
    # 选项2：删除单个列表
    else:
        if select_idx in del_index_map:
            target_index = del_index_map[select_idx]
            log_info(f"执行删除列表序号: {target_index} 逻辑")
            file_path, _ = get_playlist_file_path(TV_FILE_PREFIX, target_index)
            # 删除对应tvlist文件
            if xbmcvfs.exists(file_path) and xbmcvfs.delete(file_path):
                log_info(f"成功删除文件: {file_path}")
            else:
                log_info(f"文件不存在，跳过删除: {file_path}")
            time.sleep(0.3)
            # 清空对应皮肤变量
            set_skin_string(f"{TV_NAME_PREFIX}{target_index}", "")
            set_skin_string(f"{TV_PATH_PREFIX}{target_index}", "")
            dialog.ok("操作成功", f"已删除{target_index}位置展示列表!")
            reload_kodi_skin()

def do_reset_tv_playlist():
    log_info("="*20 + "开始执行【重置剧集首页展示列表】逻辑" + "="*20)
    dialog = xbmcgui.Dialog()
    # 弹出确认窗口，文案精准匹配
    confirm = dialog.yesno("重置确认", "此操作将重新排序并清除多余的列表，请确认继续进行！")
    if not confirm:
        log_info("用户取消重置操作，静默退出")
        return
    # 核心逻辑：循环1-6，读取tvlist文件name，赋值tvname1~6，tvpath1~6固定赋值
    log_info("开始循环读取 tvlist1~6.xsp 文件，赋值皮肤变量 tvname1~6 和 tvpath1~6")
    for i in range(1, LIST_MAX_NUM + 1):
        file_path, _ = get_playlist_file_path(TV_FILE_PREFIX, i)
        playlist_name = get_playlist_name_from_file(file_path)
        kodi_path = get_kodi_playlist_path(TV_FILE_PREFIX, i)
        set_skin_string(f"{TV_NAME_PREFIX}{i}", playlist_name)
        set_skin_string(f"{TV_PATH_PREFIX}{i}", kodi_path)
        log_info(f"重置赋值完成 → tvname{i} = [{playlist_name}] | tvpath{i} = [{kodi_path}]")
    # 弹出确认窗并重载皮肤
    dialog.ok("操作成功", "已重置所有剧集展示列表！")
    reload_kodi_skin()
    log_info("重置剧集首页展示列表逻辑执行完毕")

# ===================== 程序入口 (核心修改处：移除while True死循环) =====================
def main():
    log_info("="*50)
    log_info("【列表管理脚本 fuselist.py 启动运行 - 双参数版(movie/tvshow)+全功能+全加固】")
    log_info("="*50)
    cmd_args = ""
    if len(sys.argv) > 1:
        cmd_args = sys.argv[1].strip()
    log_debug(f"脚本获取运行参数: [{cmd_args}]")
    
    # 仅处理 movie / tvshow 两个参数
    if cmd_args not in ["movie", "tvshow"]:
        log_info("脚本参数非[movie/tvshow]，终止执行")
        return

    main_dialog = xbmcgui.Dialog()
    # ===================== 电影参数逻辑 - 移除while True循环 =====================
    if cmd_args == "movie":
        main_choices = [
            "新建电影首页展示列表",
            "编辑已有列表文件",
            "删除电影首页展示列表",
            "重置电影首页展示列表"
        ]
        log_info(f"弹出电影主选择窗口，选项: {main_choices}")
        main_choose = main_dialog.select("电影列表管理", main_choices)
        if main_choose == -1:
            log_info("用户关闭主选择窗口，脚本执行完毕")
        if main_choose == 0:
            do_create_playlist()
        elif main_choose == 1:
            do_edit_playlist()
        elif main_choose == 2:
            do_delete_playlist()
        elif main_choose == 3:
            do_reset_playlist()
    # ===================== 剧集参数逻辑 - 移除while True循环 =====================
    elif cmd_args == "tvshow":
        main_choices = [
            "新建剧集首页展示列表",
            "编辑已有剧集列表文件",
            "删除剧集首页展示列表",
            "重置剧集首页展示列表"
        ]
        log_info(f"弹出剧集主选择窗口，选项: {main_choices}")
        main_choose = main_dialog.select("剧集列表管理", main_choices)
        if main_choose == -1:
            log_info("用户关闭主选择窗口，脚本执行完毕")
        if main_choose == 0:
            do_create_tv_playlist()
        elif main_choose == 1:
            do_edit_tv_playlist()
        elif main_choose == 2:
            do_delete_tv_playlist()
        elif main_choose == 3:
            do_reset_tv_playlist()

    log_info("="*50)
    log_info("【列表管理脚本 fuselist.py 执行完毕】")
    log_info("="*50)

if __name__ == '__main__':
    main()