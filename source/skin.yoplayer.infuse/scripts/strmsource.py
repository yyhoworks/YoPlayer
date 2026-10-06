#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
import os
import traceback
import sys
import shutil
import re
from urllib.parse import unquote_plus, quote_plus
from pathlib import PureWindowsPath, PurePosixPath

# ===================== 极简日志函数（核心精简，删除所有debug） =====================
def log_info(msg):
    """仅保留核心流程日志，少量输出"""
    xbmc.log(f"[STRMSOURCE SCRIPT] {msg}", xbmc.LOGINFO)

def log_warning(msg):
    """仅保留关键警告日志"""
    xbmc.log(f"[STRMSOURCE SCRIPT WARN] {msg}", xbmc.LOGWARNING)

def log_error(msg):
    """完整保留错误日志+堆栈，排错必备，不精简"""
    xbmc.log(f"[STRMSOURCE SCRIPT ERROR] {msg}", xbmc.LOGERROR)

# ===================== 核心保留：目录名清理函数（适配STRM去特殊符号） =====================
def clean_dir_name(dir_name):
    """清理目录名称中的特殊符号、标点、空格等，用于包含匹配"""
    if not dir_name:
        return ""
    dir_name = dir_name.lower()
    clean_name = re.sub(r'[^\u4e00-\u9fff0-9a-zA-Z]', '', dir_name)
    clean_name = clean_name.strip()
    return clean_name

# ===================== 所有核心功能函数完整保留，仅精简日志输出 =====================
def get_xml_directory_content(xml_path):
    """读取XML文件并提取<directory>标签内容"""
    try:
        if not xbmcvfs.exists(xml_path):
            log_error(f"XML文件不存在：{xml_path}")
            return []
        
        with xbmcvfs.File(xml_path, 'r') as f:
            xml_content = f.read()
        
        root = ET.fromstring(xml_content.encode('utf-8'))
        dirs = []
        for elem in root.iter('directory'):
            text = elem.text.strip() if elem.text else ''
            if text:
                dirs.append(unquote_plus(text))
        return dirs
    except Exception as e:
        log_error(f"XML解析失败：{str(e)}\n{traceback.format_exc()}")
        xbmcgui.Dialog().ok('XML解析错误', f'错误详情：{str(e)}')
        return []

def delete_xml_directory_entry(xml_path, target_dir):
    """删除XML文件中指定的<directory>条目"""
    try:
        if not xbmcvfs.exists(xml_path):
            log_error(f"XML文件不存在：{xml_path}")
            return False
        
        with xbmcvfs.File(xml_path, 'r') as f:
            xml_content = f.read()
        root = ET.fromstring(xml_content.encode('utf-8'))
        removed = False
        
        for elem in root.iter('directory'):
            elem_text = elem.text.strip() if elem.text else ''
            if elem_text:
                decode_text = unquote_plus(elem_text)
                if decode_text == target_dir or elem_text == target_dir:
                    root.remove(elem)
                    removed = True
                    break
        
        if not removed:
            log_warning(f"XML中未找到目标目录记录：{target_dir}")
            return False
        
        xml_string = ET.tostring(root, encoding='utf-8', method='xml').decode('utf-8')
        with xbmcvfs.File(xml_path, 'w') as f:
            f.write(xml_string)
        return True
    except Exception as e:
        log_error(f"删除XML条目失败：{str(e)}\n{traceback.format_exc()}")
        return False

def split_path_to_parts(path):
    """拆分路径为从最后一级到根的文件夹列表"""
    try:
        path = path.rstrip('/\\')
        path_parts = []
        
        if '\\' in path:
            pure_path = PureWindowsPath(path)
        else:
            pure_path = PurePosixPath(path)
        
        for part in reversed(pure_path.parts):
            if part:
                if part.endswith('\\') and len(part) == 2:
                    part = part.rstrip('\\')
                path_parts.append(part)
        return path_parts
    except Exception as e:
        log_error(f"路径拆分失败：{str(e)}\n{traceback.format_exc()}")
        return []

# ===================== 核心保留：包含匹配逻辑（关键不改） =====================
def search_matching_paths(base_dir, target_parts, match_level):
    """核心：包含匹配 - STRM目录名包含目标目录名即判定匹配"""
    try:
        matches = []
        local_base = os.path.abspath(xbmcvfs.translatePath(base_dir))
        
        if not os.path.exists(local_base):
            log_error(f"基准目录不存在：{local_base}")
            return matches
        
        need_match_parts = target_parts[:match_level][::-1]
        need_match_name = clean_dir_name("".join(need_match_parts))
        
        for root, dirs, _ in os.walk(local_base, followlinks=True):
            current_dir_name = os.path.basename(root)
            current_clean_name = clean_dir_name(current_dir_name)
            if need_match_name and need_match_name in current_clean_name:
                matches.append(root)
        
        matches.sort(key=lambda x: len(x), reverse=True)
        return matches
    except Exception as e:
        log_error(f"路径搜索失败：{str(e)}\n{traceback.format_exc()}")
        return []

def remove_readonly(func, path, excinfo):
    """处理只读文件删除的回调函数"""
    try:
        os.chmod(path, 0o777)
        func(path)
    except Exception as e:
        log_error(f"修改权限并删除失败：{str(e)}")

def delete_directory_contents(dir_path):
    """删除目录下所有内容"""
    try:
        local_dir = os.path.abspath(xbmcvfs.translatePath(dir_path))
        if not os.path.exists(local_dir):
            return True
        
        if os.path.isdir(local_dir):
            shutil.rmtree(local_dir, onerror=remove_readonly)
        return True
    except Exception as e:
        log_error(f"删除目录内容失败：{str(e)}\n{traceback.format_exc()}")
        return False

def delete_directory(dir_path):
    """删除指定目录（包括内容）"""
    try:
        local_dir = os.path.abspath(xbmcvfs.translatePath(dir_path))
        if not os.path.exists(local_dir):
            return True
        
        if os.path.isdir(local_dir):
            shutil.rmtree(local_dir, onerror=remove_readonly)
        elif os.path.exists(local_dir):
            os.remove(local_dir)
        
        return not os.path.exists(local_dir)
    except Exception as e:
        log_error(f"删除目录失败：{str(e)}\n{traceback.format_exc()}")
        return False

def delete_file(file_path):
    """删除指定文件"""
    try:
        local_file = os.path.abspath(xbmcvfs.translatePath(file_path))
        if not os.path.exists(local_file):
            return True
        
        if os.path.isfile(local_file):
            os.chmod(local_file, 0o777)
            os.remove(local_file)
        
        return not os.path.exists(local_file)
    except Exception as e:
        log_error(f"删除文件失败：{str(e)}\n{traceback.format_exc()}")
        return False

def refresh_container(is_folder_deleted=False, folder_path=None):
    """智能刷新容器"""
    try:
        if is_folder_deleted and folder_path:
            parent_path = os.path.dirname(xbmcvfs.translatePath(folder_path))
            kodi_parent_path = xbmcvfs.makeLegalFilename(parent_path).replace(os.sep, '/')
            xbmc.executebuiltin(f'Container.Update("{kodi_parent_path}")')
        else:
            xbmc.executebuiltin('Container.Refresh')
        
        xbmc.sleep(100)
        xbmc.executebuiltin('XBMC.Container.Refresh')
    except Exception as e:
        log_error(f"容器刷新失败：{str(e)}")

# ===================== delete删除模式 - 完整保留逻辑 =====================
def handle_delete_mode(xml_local_path, xml_dir):
    """处理删除模式逻辑"""
    try:
        dir_list = get_xml_directory_content(xml_local_path)
        delete_options = ["删除所有源目录及strm文件"] + dir_list
        
        selected_idx = xbmcgui.Dialog().select('删除操作选择', delete_options)
        if selected_idx == -1:
            return
        
        if selected_idx == 0:
            confirm = xbmcgui.Dialog().yesno('危险操作确认', '是否确认删除STRM目录下所有内容？\n包括：源目录文件夹、STRM文件、源目录记录文件！\n此操作不可恢复！')
            if confirm:
                if delete_directory_contents(xml_dir):
                    xbmcgui.Dialog().ok('成功', 'STRM目录下所有内容已删除完成！')
                    refresh_container(is_folder_deleted=True, folder_path=xml_dir)
                else:
                    xbmcgui.Dialog().ok('失败', '删除过程中出现错误！')
            return
        
        target_dir = delete_options[selected_idx]
        path_parts = split_path_to_parts(target_dir)
        if not path_parts:
            xbmcgui.Dialog().ok('错误', '目标目录路径无效，无法拆分！')
            return
        
        found_path = None
        match_failed = False
        for match_level in range(1, len(path_parts)+1):
            matches = search_matching_paths(xml_dir, path_parts, match_level)
            
            if len(matches) >= 1:
                found_path = matches[0]
                break
            elif len(matches) == 0:
                need_match = path_parts[:match_level][::-1]
                match_str = path_parts[0] if match_level == 1 else os.sep.join(need_match)
                xbmcgui.Dialog().ok('未找到', f'未找到包含「{match_str}」的路径！')
                
                xml_deleted = delete_xml_directory_entry(xml_local_path, target_dir)
                if xml_deleted:
                    xbmcgui.Dialog().ok('清理完成', f'已自动删除XML中无效的目录记录：\n{target_dir}')
                    refresh_container()
                else:
                    xbmcgui.Dialog().ok('清理失败', f'未找到路径，但删除XML记录失败！')
                
                match_failed = True
                break
        
        if match_failed or not found_path:
            return
        
        confirm = xbmcgui.Dialog().yesno('确认删除', f'是否确认删除路径：\n{found_path}？\n并同步删除XML中的对应记录？')
        if not confirm:
            return
        
        delete_target = found_path
        strm_root = xml_dir
        
        while True:
            parent_dir = os.path.dirname(delete_target)
            if os.path.abspath(parent_dir) == os.path.abspath(strm_root):
                break
            
            try:
                all_items = os.listdir(parent_dir)
            except Exception as e:
                log_error(f"读取上级目录失败：{str(e)}")
                break
            
            current_target_name = os.path.basename(delete_target)
            remaining_items = [item for item in all_items if item != current_target_name]
            
            if len(remaining_items) > 0:
                break
            delete_target = parent_dir
        
        dir_deleted = delete_directory(delete_target)
        xml_updated = delete_xml_directory_entry(xml_local_path, target_dir)
        
        if dir_deleted and xml_updated:
            xbmcgui.Dialog().ok('成功', f'已成功删除：\n{delete_target}\n\n并同步删除XML中的目录记录！')
            refresh_container(is_folder_deleted=True, folder_path=delete_target)
        elif dir_deleted and not xml_updated:
            xbmcgui.Dialog().ok('部分成功', f'已删除目录：\n{delete_target}\n\n但删除XML记录失败！')
            refresh_container(is_folder_deleted=True, folder_path=delete_target)
        elif not dir_deleted:
            xbmcgui.Dialog().ok('失败', f'删除目录失败：\n{delete_target}')
    
    except Exception as e:
        log_error(f"删除模式执行异常：{str(e)}\n{traceback.format_exc()}")
        xbmcgui.Dialog().ok('删除错误', f'执行出错：{str(e)}')

# ===================== deletstrm删除模式 - 完整保留逻辑 =====================
def handle_deletstrm_mode():
    """处理deletstrm参数模式逻辑"""
    try:
        current_item_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
        if not current_item_path:
            xbmcgui.Dialog().ok('错误', '未获取到当前项目路径！')
            return
        
        local_item_path = os.path.abspath(xbmcvfs.translatePath(current_item_path))
        is_folder = os.path.isdir(local_item_path) if os.path.exists(local_item_path) else False
        
        if not is_folder:
            if delete_file(current_item_path):
                xbmcgui.Dialog().ok('成功', '文件已成功删除！')
                refresh_container()
            else:
                xbmcgui.Dialog().ok('失败', '删除文件失败！')
            return
        
        primary_xml_dir = xbmcvfs.translatePath('/storage/videos/strm/')
        fallback_xml_dir = xbmcvfs.translatePath('C:\\storage\\videos\\strm\\')
        xml_dir = primary_xml_dir if xbmcvfs.exists(primary_xml_dir) else fallback_xml_dir
        
        xml_local_path = None
        dir_list = []
        xml_files = []
        if xbmcvfs.exists(xml_dir):
            try:
                for filename in os.listdir(xbmcvfs.translatePath(xml_dir)):
                    file_path = os.path.join(xbmcvfs.translatePath(xml_dir), filename)
                    if os.path.isfile(file_path) and filename.lower().endswith('.xml'):
                        xml_files.append(file_path)
            except Exception as e:
                log_error(f"读取XML目录失败：{str(e)}")
            
            if xml_files:
                if len(xml_files) == 1:
                    xml_local_path = xml_files[0]
                else:
                    xml_file_names = [os.path.basename(f) for f in xml_files]
                    selected_idx = xbmcgui.Dialog().select('选择源目录记录文件', xml_file_names)
                    if selected_idx != -1:
                        xml_local_path = xml_files[selected_idx]
            
            if xml_local_path:
                dir_list = get_xml_directory_content(xml_local_path)
        
        current_parts = split_path_to_parts(local_item_path)
        matched_records = []
        
        if current_parts and dir_list:
            for record in dir_list:
                record_parts = split_path_to_parts(record)
                if not record_parts:
                    continue
                
                match_level = 0
                max_possible = min(len(current_parts), len(record_parts))
                for i in range(max_possible):
                    if clean_dir_name(current_parts[i]) in clean_dir_name(record_parts[i]):
                        match_level += 1
                    else:
                        break
                
                if match_level > 0:
                    matched_records.append((record, match_level))
        
        target_record = None
        if matched_records:
            matched_records.sort(key=lambda x: x[1], reverse=True)
            max_level = matched_records[0][1]
            max_matches = [r for r, l in matched_records if l == max_level]
            
            if len(max_matches) == 1:
                target_record = max_matches[0]
            else:
                selected_idx = xbmcgui.Dialog().select('找到多个匹配记录', max_matches)
                if selected_idx != -1:
                    target_record = max_matches[selected_idx]
        
        delete_record = False
        delete_folder = True
        
        if target_record:
            confirm = xbmcgui.Dialog().yesno('确认删除', f'找到匹配的源目录记录：\n{target_record}\n\n是否确认删除该记录及所选文件夹？')
            if confirm:
                delete_record = True
            else:
                delete_folder = xbmcgui.Dialog().yesno('确认删除', '是否仅删除所选文件夹？')
        else:
            confirm = xbmcgui.Dialog().yesno('确认删除', '未找到匹配的源目录记录，是否删除所选文件夹？')
            delete_folder = confirm
        
        success = True
        if delete_record and xml_local_path:
            xml_deleted = delete_xml_directory_entry(xml_local_path, target_record)
            if not xml_deleted:
                success = False
                xbmcgui.Dialog().ok('部分失败', '删除源目录记录失败！')
        
        deleted_folder_path = None
        if delete_folder:
            folder_deleted = delete_directory(local_item_path)
            deleted_folder_path = local_item_path
            if not folder_deleted:
                success = False
                xbmcgui.Dialog().ok('部分失败', '删除文件夹失败！')
        
        if success:
            if delete_record and delete_folder:
                xbmcgui.Dialog().ok('成功', '源目录记录及文件夹已成功删除！')
                refresh_container(is_folder_deleted=True, folder_path=deleted_folder_path)
            elif delete_folder:
                xbmcgui.Dialog().ok('成功', '文件夹已成功删除！')
                refresh_container(is_folder_deleted=True, folder_path=deleted_folder_path)
            elif delete_record:
                xbmcgui.Dialog().ok('成功', '源目录记录已成功删除！')
                refresh_container()
    
    except Exception as e:
        log_error(f"deletstrm模式执行异常：{str(e)}\n{traceback.format_exc()}")
        xbmcgui.Dialog().ok('删除错误', f'执行出错：{str(e)}')

# ===================== 主函数 - 仅保留少量启动日志 =====================
def main():
    """脚本主入口"""
    log_info("STRMSOURCE 脚本启动")
    try:
        args = sys.argv[1:] if len(sys.argv) > 1 else []
        is_delete_mode = 'delet' in args
        is_deletstrm_mode = 'deletstrm' in args
        
        if is_deletstrm_mode:
            handle_deletstrm_mode()
            return
        
        if is_delete_mode:
            primary_xml_dir = xbmcvfs.translatePath('/storage/videos/strm/')
            fallback_xml_dir = xbmcvfs.translatePath('C:\\storage\\videos\\strm\\')
            
            if xbmcvfs.exists(primary_xml_dir):
                xml_dir = primary_xml_dir
            elif xbmcvfs.exists(fallback_xml_dir):
                xml_dir = fallback_xml_dir
            else:
                xbmcgui.Dialog().ok('错误', '未找到源目录记录文件所在的文件夹！\n以下路径均不存在：\n1. /storage/videos/strm\n2. C:\\storage\\videos\\strm\\')
                return
            
            xml_files = []
            try:
                for filename in os.listdir(xbmcvfs.translatePath(xml_dir)):
                    file_path = os.path.join(xbmcvfs.translatePath(xml_dir), filename)
                    if os.path.isfile(file_path) and filename.lower().endswith('.xml'):
                        xml_files.append(file_path)
            except Exception as e:
                log_error(f"读取XML目录失败：{str(e)}")
                xbmcgui.Dialog().ok('错误', f'无法读取目录内容：{xml_dir}\n错误详情：{str(e)}')
                return
            
            if not xml_files:
                xbmcgui.Dialog().ok('错误', f'在目录\n{xml_dir}\n中未找到XML源目录记录文件！')
                return
            
            if len(xml_files) == 1:
                xml_local_path = xml_files[0]
            else:
                xml_file_names = [os.path.basename(f) for f in xml_files]
                selected_idx = xbmcgui.Dialog().select('选择源目录记录文件', xml_file_names)
                if selected_idx == -1:
                    return
                xml_local_path = xml_files[selected_idx]
            
            handle_delete_mode(xml_local_path, xml_dir)
            return
        
        # 正常模式
        xml_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
        if not xml_path:
            xbmcgui.Dialog().ok('错误', '未找到源目录列表！')
            return
        
        xml_local_path = xbmcvfs.translatePath(xml_path) if '://' in xml_path else xml_path
        xml_dir = os.path.dirname(xml_local_path)
        
        dir_list = get_xml_directory_content(xml_local_path)
        if not dir_list:
            xbmcgui.Dialog().ok('提示', '源目录列表为空，请添加源目录生成STRM文件！')
            return
        
        selected_idx = xbmcgui.Dialog().select('选择源目录', dir_list)
        if selected_idx == -1:
            return
        target_dir = dir_list[selected_idx]
        
        path_parts = split_path_to_parts(target_dir)
        if not path_parts:
            xbmcgui.Dialog().ok('错误', '目标目录路径无效，无法拆分！')
            return
        
        found_path = None
        for match_level in range(1, len(path_parts)+1):
            matches = search_matching_paths(xml_dir, path_parts, match_level)
            
            if len(matches) >= 1:
                found_path = matches[0]
                break
            elif len(matches) == 0:
                need_match = path_parts[:match_level][::-1]
                match_str = path_parts[0] if match_level == 1 else os.sep.join(need_match)
                xbmcgui.Dialog().ok('未找到', f'未找到包含「{match_str}」的路径！')
                return
        
        if found_path:
            kodi_path = xbmcvfs.makeLegalFilename(found_path).replace(os.sep, '/')
            kodi_path = xbmcvfs.validatePath(kodi_path)
            xbmc.executebuiltin(f'ActivateWindow(Videos,{kodi_path},return)')
        else:
            xbmcgui.Dialog().ok('未找到', '未找到匹配的路径！')
    
    except Exception as e:
        log_error(f"脚本运行异常：{str(e)}\n{traceback.format_exc()}")
        xbmcgui.Dialog().ok('脚本错误', f'运行出错：{str(e)}')
    finally:
        log_info("STRMSOURCE 脚本执行结束")

if __name__ == '__main__':
    main()