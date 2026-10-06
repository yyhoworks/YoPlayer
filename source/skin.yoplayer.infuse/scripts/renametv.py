import xbmc
import xbmcgui
import xbmcvfs
import os
import re
import sys
import time
import threading

# 定义支持的视频文件扩展名
VIDEO_EXTENSIONS = {
    '.mkv', '.mp4', '.avi', '.wmv', '.ts', '.mov', '.mpg', '.mpeg', 
    '.m2ts', '.m2t', '.iso', '.img', '.ifo', '.vob', '.divx', '.flv'
}

def log(msg):
    """输出详细日志到Kodi日志文件"""
    xbmc.log(f"[RenameTV] {msg}", level=xbmc.LOGINFO)

def normalize_path(path):
    """规范化路径：去除末尾多余的斜杠，用于一致性比较"""
    if not path:
        return ""
    return path.rstrip('/\\')

def is_path_exists_robust(path):
    """
    鲁棒的路径存在性检测
    1. 优先使用 xbmcvfs.exists (最准确)
    2. 如果 exists 返回 False，尝试 listdir 作为二次验证
       - 关键修复：必须检查 listdir 是否真的返回了内容或至少成功执行且路径有效
       - 对于不存在的文件夹，listdir 通常会返回 ([], []) 或者在某些实现中抛出异常
    """
    try:
        # 第一道防线：标准存在性检查
        if xbmcvfs.exists(path):
            return True
            
        # 第二道防线：针对某些网络挂载的特殊处理
        # 确保路径以 / 结尾以便 listdir 识别为目录
        normalized = normalize_path(path) + '/'
        
        try:
            dirs, files = xbmcvfs.listdir(normalized)
            # 【核心修复】：只有当 listdir 成功且返回了非空结果，或者虽然为空但我们能确定它是目录时才返回 True
            # 但在 Kodi Python API 中，如果路径不存在，listdir 通常返回 ([], [])
            # 因此，如果 exists 为 False，且 listdir 返回空列表，我们应谨慎对待。
            
            # 更安全的策略：如果 exists 为 False，我们倾向于认为它不存在，除非我们有确凿证据。
            # 这里我们做一个简单的启发式判断：如果 listdir 没报错，但返回空，我们依然认为它可能不存在（尤其是对于新建的重命名目标）。
            # 但是，为了兼容某些特殊文件系统，如果 listdir 返回了任何内容，那肯定存在。
            
            if dirs or files:
                return True
            
            # 如果 dirs 和 files 都为空，且上面 exists 已经返回 False，那么大概率是不存在的。
            # 返回 False 允许重命名进行。
            return False
            
        except Exception as e:
            # 如果 listdir 报错（例如权限不足或路径无效），则视为不存在或无法访问
            log(f"listdir 验证失败: {e}")
            return False
            
    except Exception as e:
        log(f"路径检测整体异常: {e}")
        return False

def ensure_trailing_slash(path):
    """确保路径以 / 结尾"""
    if path and not path.endswith('/'):
        return path + '/'
    return path

def refresh_container():
    """刷新当前容器以显示更改"""
    log("正在刷新容器以更新视图...")
    xbmc.executebuiltin("Container.Refresh")
    time.sleep(0.5)

def is_video_file(filename):
    """检查文件是否为视频文件"""
    _, ext = os.path.splitext(filename)
    return ext.lower() in VIDEO_EXTENSIONS

def is_single_episode(name):
    """检查是否包含单集特征：SaEb, x集, Ex, 纯数字"""
    clean_name, _ = os.path.splitext(name)
    
    if re.search(r'(?i)s\d+e\d+', clean_name): return True
    if re.search(r'\d+集', clean_name): return True
    if re.search(r'(?i)e\d+', clean_name): return True
    if re.match(r'^\d+$', clean_name): return True
    return False

def is_season_folder(name):
    """检查是否包含季文件夹特征：season a, x季, Sx"""
    if re.search(r'(?i)season\s*\d+', name): return True
    if re.search(r'\d+季', name): return True
    if re.match(r'(?i)^s\d+$', name): return True
    return False

class VideoCounter(threading.Thread):
    """后台线程：统计视频文件数量"""
    def __init__(self, folder_path, only_season_folders=False):
        super().__init__()
        self.folder_path = folder_path
        self.count = 0
        self.only_season_folders = only_season_folders

    def run(self):
        self.count = self._count(self.folder_path, is_root=True)

    def _count(self, path, is_root=False):
        count = 0
        try:
            path = ensure_trailing_slash(path)
            dirs, files = xbmcvfs.listdir(path)
            if not self.only_season_folders or not is_root:
                for f in files:
                    if is_video_file(f):
                        count += 1
            
            for d in dirs:
                if d.upper() == 'STEAM':
                    continue
                if self.only_season_folders and is_root and not is_season_folder(d):
                    continue
                
                count += self._count(os.path.join(path, d), is_root=False)
        except Exception as e:
            log(f"统计视频数量异常: {e}")
        return count

def rename_single_file(folder, filename, season_num=None):
    """重命名单集视频文件，返回是否成功重命名"""
    if not is_video_file(filename):
        return False

    name, ext = os.path.splitext(filename)
    new_name = None
    
    m = re.search(r'(?i)s(\d+)e(\d+)', name)
    if m:
        s, e = m.group(1), m.group(2)
        if season_num is not None: s = season_num
        new_name = f"S{int(s):02d}E{int(e):02d}"
    else:
        m = re.search(r'(\d+)集', name)
        if m:
            e = m.group(1)
            new_name = f"S{season_num}E{int(e):02d}" if season_num is not None else f"E{int(e):02d}"
        else:
            m = re.search(r'(?i)e(\d+)', name)
            if m:
                e = m.group(1)
                new_name = f"S{season_num}E{int(e):02d}" if season_num is not None else f"E{int(e):02d}"
            else:
                m = re.match(r'^(\d+)$', name)
                if m and season_num is not None:
                    e = m.group(1)
                    new_name = f"S{int(season_num):02d}E{int(e):02d}"
    
    if new_name:
        old_path = os.path.join(folder, filename)
        new_path = os.path.join(folder, new_name + ext)
        if old_path != new_path:
            log(f"重命名视频文件: '{filename}' -> '{new_name}{ext}'")
            if xbmcvfs.rename(old_path, new_path):
                return True
            else:
                log(f"重命名失败: '{old_path}'")
    return False

def get_season_info(dirname):
    """从文件夹名提取季号和建议的新名称。返回 (建议名称, 季号) 或 (None, None)"""
    new_name = None
    season_num = None
    
    m = re.search(r'(?i)season\s*(\d+)', dirname)
    if m:
        season_num = m.group(1)
        new_name = f"season {season_num}"
    else:
        m = re.search(r'(\d+)季', dirname)
        if m:
            season_num = m.group(1)
            new_name = f"season {season_num}"
        else:
            m = re.match(r'(?i)^s(\d+)$', dirname)
            if m:
                season_num = m.group(1)
                new_name = f"season {season_num}"
    
    return new_name, season_num

def safe_listdir(path):
    """安全地列出目录，确保路径格式正确"""
    path = ensure_trailing_slash(path)
    try:
        return xbmcvfs.listdir(path)
    except Exception as e:
        log(f"列出目录失败 {path}: {e}")
        return [], []

def main():
    log("--- 脚本开始运行 ---")
    
    time.sleep(0.5)
    
    label = xbmc.getInfoLabel('ListItem.Label')
    is_folder = xbmc.getCondVisibility('ListItem.IsFolder')
    item_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
    
    if not item_path:
        item_path = xbmc.getInfoLabel('ListItem.Path')
        
    log(f"ListItem.Label: {label}")
    log(f"ListItem.IsFolder: {is_folder}")
    log(f"ListItem.FileNameAndPath: {item_path}")
    
    if not item_path:
        log("错误：无法获取当前项路径。")
        xbmcgui.Dialog().notification("错误", "无法获取当前项路径", xbmcgui.NOTIFICATION_ERROR)
        return

    clean_item_path = normalize_path(item_path)
    item_name = os.path.basename(clean_item_path)
    parent_dir = os.path.dirname(clean_item_path)
    
    if not is_folder and not is_video_file(item_name):
        log(f"拦截：'{item_name}' 不是视频文件，退出脚本。")
        xbmcgui.Dialog().ok("提示", "此脚本仅用于重命名视频文件或包含视频的文件夹。")
        return

    log(f"处理Label: '{label}'")
    # 【核心逻辑】清理非法字符，保留中文、英文、数字和空格
    cleaned = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', ' ', label)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    log(f"清理后的字符串: '{cleaned}'")
    
    season_match = re.search(r'(?i)season\s*\d+', cleaned)
    if season_match:
        auto_name = season_match.group()
    else:
        year_match = re.search(r'((?:19|20)\d{2})', cleaned)
        if year_match:
            auto_name = cleaned[:year_match.end()].strip()
        else:
            auto_name = cleaned
    log(f"自动提取名称: '{auto_name}'")
    
    # 【优化】插入第二选项：手动键盘输入文件名
    options = [f"自动提取：{auto_name}", "手动键盘输入文件名"]
    parts = [p for p in cleaned.split(' ') if p]
    options.extend(parts)
    
    selected = xbmcgui.Dialog().multiselect("选择重命名部分", options)
    if not selected:
        log("用户取消选择，退出脚本。")
        return
        
    selected_parts = []
    for i in selected:
        if i == 0:
            selected_parts.append(auto_name)
        elif i == 1:
            # 【优化】弹出键盘输入框，并预填清理后的字符串 cleaned
            kb_input = xbmcgui.Dialog().input(
                heading="请输入自定义文件名", 
                defaultt=cleaned,  # 预填默认值
                type=xbmcgui.INPUT_ALPHANUM
            )
            if kb_input:
                # 再次移除文件系统不允许的非法字符，防止用户手动输入了非法字符
                clean_kb_input = re.sub(r'[\\/:*?"<>|]', '', kb_input).strip()
                if clean_kb_input:
                    selected_parts.append(clean_kb_input)
        else:
            selected_parts.append(options[i])
            
    new_base_name = " ".join(selected_parts).strip()
    log(f"用户选择构建的新基础名称: '{new_base_name}'")
    
    if not new_base_name:
        log("错误：新名称为空。")
        return

    if is_folder:
        old_path = clean_item_path
        new_path = os.path.join(parent_dir, new_base_name)
        display_name = new_base_name
    else:
        _, ext = os.path.splitext(clean_item_path)
        old_path = clean_item_path
        new_path = os.path.join(parent_dir, new_base_name + ext)
        display_name = new_base_name + ext
        
    log(f"准备重命名: '{old_path}' -> '{new_path}'")
    
    if old_path != new_path:
        log(f"检测目标路径是否存在: {new_path}")
        if is_path_exists_robust(new_path):
            log(f"重命名阻止：目标路径已存在 '{new_path}'")
            xbmcgui.Dialog().ok("重命名失败", 
                f"无法重命名为“{display_name}”\n\n原因：同级目录下已存在同名文件或文件夹。\n请检查并删除冲突项，或选择其他名称。")
            return

        if not xbmcvfs.rename(old_path, new_path):
            log("重命名当前项失败！")
            # 重试一次检测，以防是缓存问题
            if is_path_exists_robust(new_path):
                 xbmcgui.Dialog().ok("重命名失败", "目标已存在，重命名被系统拒绝。")
            else:
                 xbmcgui.Dialog().notification("错误", "重命名失败，请检查权限或文件是否被占用", xbmcgui.NOTIFICATION_ERROR)
            return
        log("当前项重命名成功。")
        current_folder_path = new_path if is_folder else parent_dir
    else:
        log("新旧路径相同，跳过重命名。")
        current_folder_path = clean_item_path if is_folder else parent_dir

    if not is_folder:
        log("情况1：当前项是视频文件。")
        refresh_container()
        xbmcgui.Dialog().ok("成功", f"已重命名为“{display_name}”！")
        return

    log("当前项是文件夹，开始扫描子内容...")
    log(f"扫描路径: '{current_folder_path}'")
    
    dirs, files = safe_listdir(current_folder_path)
    
    has_single = any(is_single_episode(f) for f in files if is_video_file(f))
    has_season = any(is_season_folder(d) for d in dirs)
    
    log(f"检测到单集视频文件: {has_single}, 检测到季文件夹: {has_season}")

    if not has_single and not has_season:
        log("情况1：文件夹下无单集视频和季文件夹。")
        refresh_container()
        xbmcgui.Dialog().ok("成功", f"已重命名为“{display_name}”！")
        return

    if has_season:
        log("情况3：检测到季文件夹。")
        choice = xbmcgui.Dialog().yesno("确认", 
            f"已将文件夹重命名为“{display_name}”！但检测到文件夹下有季文件夹和视频单集，是否将其规范命名？点击“是”立即自动重命名，点击“否”保持现状。",
            nolabel="否", yeslabel="是")
            
        if not choice:
            refresh_container()
            return
            
        folder_rename_count = 0
        file_count = 0
        
        progress = xbmcgui.DialogProgress()
        progress.create("重命名进度", "正在统计视频文件数量，\n请稍候...")
        
        counter = VideoCounter(current_folder_path, only_season_folders=True)
        counter.start()
        counter.join()
        total_count = counter.count
        
        if total_count == 0:
            progress.close()
            refresh_container()
            xbmcgui.Dialog().ok("提示", "未检测到符合条件的视频文件。")
            return
            
        dirs, files = safe_listdir(current_folder_path)
        
        for d in dirs:
            if progress.iscanceled():
                break
            
            if is_season_folder(d):
                suggested_name, season_num = get_season_info(d)
                
                if suggested_name and suggested_name != d:
                    old_folder_path = os.path.join(current_folder_path, d)
                    new_folder_path = os.path.join(current_folder_path, suggested_name)
                    
                    if is_path_exists_robust(new_folder_path):
                         log(f"跳过重命名季文件夹: 目标 '{suggested_name}' 已存在")
                         if not season_num:
                             continue
                    else:
                        log(f"重命名季文件夹: '{d}' -> '{suggested_name}'")
                        if xbmcvfs.rename(old_folder_path, new_folder_path):
                            folder_rename_count += 1
                            d = suggested_name
                        else:
                            log(f"重命名季文件夹失败: '{d}'")
                            if not season_num:
                                continue 

                if not season_num and suggested_name:
                     _, season_num = get_season_info(d)

                if not season_num:
                    log(f"无法从文件夹 '{d}' 中提取季号，跳过文件处理。")
                    continue

                log(f"等待文件系统同步季文件夹: {d}...")
                time.sleep(1.0) 
                xbmc.executebuiltin("Container.Refresh")
                time.sleep(0.5)

                season_folder_path = os.path.join(current_folder_path, d)
                season_folder_path = ensure_trailing_slash(season_folder_path)
                
                log(f"准备处理季文件夹: '{season_folder_path}' (Season {season_num})")
                
                exists = xbmcvfs.exists(season_folder_path)
                if not exists:
                    log(f"首次检查路径不存在，等待并重试...")
                    time.sleep(1.0)
                    exists = xbmcvfs.exists(season_folder_path)
                    
                if exists:
                    s_dirs, s_files = safe_listdir(season_folder_path)
                    log(f"季文件夹 '{d}' 中找到 {len(s_files)} 个文件")
                    for f in s_files:
                        if progress.iscanceled():
                            break
                        if is_video_file(f) and is_single_episode(f):
                            if rename_single_file(season_folder_path, f, season_num):
                                file_count += 1
                                percent = int((file_count * 100) / total_count)
                                msg = f"正在处理季文件夹 {d}...\n[{file_count}/{total_count}]"
                                progress.update(percent, msg)
                else:
                    log(f"警告: 季文件夹路径最终仍不存在: {season_folder_path}")
                                
        progress.close()
        log(f"情况3处理完成，共重命名 {folder_rename_count} 个季文件夹，{file_count} 个单集视频文件。")
        refresh_container()
        xbmcgui.Dialog().ok("成功", f"已重命名季文件夹“{folder_rename_count}”，单集视频文件“{file_count}”个！")
        return

    if has_single and not has_season:
        log("情况2：检测到单集视频文件，无季文件夹。")
        choice = xbmcgui.Dialog().yesno("确认", 
            f"已将文件夹重命名为“{display_name}”！但检测到文件夹下有单集视频文件，是否将其规范命名为“SxxExx”格式？点击“是”立即自动重命名，点击“否”保持现状。",
            nolabel="否", yeslabel="是")
        
        if not choice:
            refresh_container()
            return
            
        progress = xbmcgui.DialogProgress()
        progress.create("重命名进度", "正在统计视频文件数量，\n请稍候...")
        
        counter = VideoCounter(current_folder_path, only_season_folders=False)
        counter.start()
        counter.join()
        total_count = counter.count
        
        if total_count == 0:
            progress.close()
            refresh_container()
            xbmcgui.Dialog().ok("提示", "未检测到符合条件的视频文件。")
            return

        file_count = 0
        for f in files:
            if progress.iscanceled():
                break
            if is_video_file(f) and is_single_episode(f):
                if rename_single_file(current_folder_path, f, None):
                    file_count += 1
                    percent = int((file_count * 100) / total_count)
                    msg = f"正在重命名处理文件，\n[{file_count}/{total_count}]"
                    progress.update(percent, msg)
                    
        progress.close()
        log(f"情况2处理完成，共重命名 {file_count} 个单集视频文件。")
        refresh_container()
        xbmcgui.Dialog().ok("成功", f"已重命名单集视频文件“{file_count}”个！")
        return

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        log(f"脚本发生异常: {e}")
        log(traceback.format_exc())
        xbmcgui.Dialog().notification("错误", f"脚本异常: {str(e)}", xbmcgui.NOTIFICATION_ERROR)