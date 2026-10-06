import xbmc
import xbmcvfs
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import os
import time
import shutil
import sys
import re

def translate_path(path):
    """兼容新旧Kodi版本的路径转换"""
    if hasattr(xbmcvfs, 'translatePath'):
        return xbmcvfs.translatePath(path)
    elif hasattr(xbmc, 'translatePath'):
        return xbmc.translatePath(path)
    return path

def get_real_path(network_path, filename):
    """获取本地真实文件路径"""
    return os.path.normpath(translate_path(f"{network_path}/{filename}"))

def force_delete(path):
    """终极强制删除（处理各种顽固文件/文件夹）"""
    if not os.path.exists(path):
        return True
    
    try:
        if os.path.isfile(path):
            os.remove(path)
            return not os.path.exists(path)
        else:
            shutil.rmtree(path, ignore_errors=True)
            return not os.path.exists(path)
    except:
        pass
    
    # Windows特殊处理
    if os.name == 'nt':
        try:
            import subprocess
            subprocess.run(['cmd', '/c', 'rmdir' if os.path.isdir(path) else 'del', 
                          '/s', '/q', path], capture_output=True, timeout=5)
            return not os.path.exists(path)
        except:
            pass
    
    # 最后的降级方案：标记为待删
    try:
        os.rename(path, path + ".to_delete")
        return True
    except:
        return False

def ensure_network_folder():
    """确保network文件夹存在"""
    network_path = xbmcvfs.makeLegalFilename(translate_path('special://userdata/network/'))
    if not xbmcvfs.exists(network_path):
        xbmcvfs.mkdirs(network_path)
        xbmc.log(f"创建network文件夹: {network_path}", xbmc.LOGINFO)
    return network_path

def parse_mediasources():
    """解析mediasources.xml，返回包含协议、名称、原始URL的网络位置信息"""
    mediasources_path = translate_path('special://userdata/mediasources.xml')
    network_locations = []
    
    if not xbmcvfs.exists(mediasources_path):
        xbmc.log("mediasources.xml不存在", xbmc.LOGWARNING)
        return network_locations
    
    try:
        with xbmcvfs.File(mediasources_path, 'r') as f:
            tree = ET.parse(f)
        root = tree.getroot()
        network_node = root.find('network')
        
        if not network_node:
            xbmc.log("未找到<network>节点", xbmc.LOGINFO)
            return network_locations
        
        for location in network_node.findall('location'):
            if location.text:
                url = location.text.strip()
                if not url:
                    continue
                
                # 提取协议（smb/http/nfs/dav等）
                protocol_end = url.find('://')
                if protocol_end == -1:
                    protocol = 'unknown'
                else:
                    protocol = url[:protocol_end].lower()
                
                # 提取IP/服务器名和端口
                server_and_port = ""
                if '@' in url:
                    # 带用户名密码：@后第一个/前的内容
                    server_part = url.split('@')[1].split('/')[0]
                else:
                    # 不带用户名密码：//后第一个/前的内容
                    server_part = url.split('//')[1].split('/')[0] if '//' in url else url.split('/')[0]
                
                # 检查是否有端口号
                port_match = re.search(r':(\d+)(?=/|$)', server_part)
                if port_match:
                    # 包含端口号的情况
                    port = port_match.group(1)
                    server_base = server_part.replace(f":{port}", "")
                    server_and_port = f"{server_base}_{port}"
                else:
                    # 不包含端口号的情况
                    server_and_port = server_part
                
                if server_and_port:
                    # 生成标准文件名：IP/服务器名_端口.协议
                    filename = f"{server_and_port}.{protocol}"
                    network_locations.append({
                        'protocol': protocol,
                        'name': server_part,  # 包含端口的完整服务器信息
                        'server_and_port': server_and_port,  # 用于生成文件名的服务器+端口
                        'filename': filename,
                        'url': url
                    })
                    xbmc.log(f"识别到网络位置: {filename} -> {url}", xbmc.LOGINFO)
        
        return network_locations
    
    except Exception as e:
        xbmc.log(f"解析mediasources.xml失败: {str(e)}", xbmc.LOGERROR)
        return network_locations

def find_existing_files_without_server_name(network_path, network_locations):
    """查找network目录下文件名中不包含服务器名/IP但内容URL匹配的文件"""
    existing_files_map = {}  # URL -> filename mapping
    real_network_path = translate_path(network_path)
    
    if os.path.exists(real_network_path):
        for item in os.listdir(real_network_path):
            item_path = os.path.join(real_network_path, item)
            
            # 只处理文件，跳过文件夹和隐藏文件
            if not os.path.isfile(item_path) or item.startswith('.'):
                continue
            
            # 检查文件内容中的Original URL
            original_url = None
            try:
                with open(item_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        stripped_line = line.strip()
                        if stripped_line.startswith("Original URL:"):
                            original_url = stripped_line.split("Original URL:", 1)[1].strip()
                            break
            except Exception as e:
                xbmc.log(f"读取文件失败 {item}: {str(e)}", xbmc.LOGERROR)
                continue
            
            if original_url:
                # 检查这个文件名是否包含任何网络位置的服务器名/IP
                contains_server_name = False
                for loc in network_locations:
                    if loc['server_and_port'] in item:
                        contains_server_name = True
                        break
                
                # 如果文件名中不包含服务器名/IP，但内容中的URL匹配某个网络位置
                if not contains_server_name:
                    for loc in network_locations:
                        if loc['url'] == original_url:
                            existing_files_map[loc['url']] = item
                            xbmc.log(f"发现匹配的现有文件: {item} -> {original_url}", xbmc.LOGINFO)
                            break
    
    return existing_files_map

def sync_network_files(network_path, network_locations, existing_files_map):
    """同步network文件夹：创建/更新文件 + 删除无效内容"""
    real_network_path = translate_path(network_path)
    
    # 过滤掉需要保留的网络位置（这些位置的文件名不包含服务器名但内容匹配）
    filtered_network_locations = []
    for loc in network_locations:
        if loc['url'] in existing_files_map:
            # 跳过这个网络位置，因为它对应的文件名不包含服务器名但URL匹配
            xbmc.log(f"跳过网络位置（保留现有文件）: {loc['filename']} -> {loc['url']}", xbmc.LOGINFO)
        else:
            filtered_network_locations.append(loc)
    
    valid_filenames = [loc['filename'] for loc in filtered_network_locations]
    
    # 1. 创建/更新有效文件
    for loc in filtered_network_locations:
        filename = loc['filename']
        file_path = get_real_path(network_path, filename)
        
        # 删除同名文件夹（如果存在）
        if os.path.isdir(file_path):
            xbmc.log(f"删除同名文件夹: {filename}", xbmc.LOGINFO)
            force_delete(file_path)
        
        # 创建或更新文件内容
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Network Location Configuration\n")
                f.write(f"Protocol: {loc['protocol']}\n")
                f.write(f"Server/IP: {loc['name']}\n")
                f.write(f"Original URL: {loc['url']}\n")
                f.write(f"Created/Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            xbmc.log(f"创建/更新文件: {filename}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"操作文件失败 {filename}: {str(e)}", xbmc.LOGERROR)
    
    # 2. 删除无效内容（直接操作本地文件系统）
    # 构建要保留的文件列表（包括过滤掉的那些）
    files_to_keep = set(valid_filenames)
    for url, filename in existing_files_map.items():
        files_to_keep.add(filename)
    
    if os.path.exists(real_network_path):
        for item in os.listdir(real_network_path):
            item_path = os.path.join(real_network_path, item)
            
            # 跳过系统隐藏文件和有效文件
            if item.startswith('.') or item in files_to_keep:
                continue
            
            # 强制删除无效项
            if force_delete(item_path):
                xbmc.log(f"删除无效项: {item}", xbmc.LOGINFO)
            else:
                xbmc.log(f"无法删除: {item}（已标记为下次删除）", xbmc.LOGWARNING)

def get_folder_state(folder_path):
    """获取文件夹的状态（文件和文件夹列表）"""
    state = {
        'files': [],
        'folders': []
    }
    real_path = translate_path(folder_path)
    if os.path.exists(real_path):
        for item in os.listdir(real_path):
            if item.startswith('.'):
                continue
            item_path = os.path.join(real_path, item)
            if os.path.isfile(item_path):
                state['files'].append(item)
            elif os.path.isdir(item_path):
                state['folders'].append(item)
    # 排序以便比较
    state['files'].sort()
    state['folders'].sort()
    return state

def get_sync_status(network_path, valid_filenames, existing_files_map):
    """获取最终同步状态"""
    real_path = translate_path(network_path)
    current_files = []
    remaining_folders = []
    
    if os.path.exists(real_path):
        for item in os.listdir(real_path):
            item_path = os.path.join(real_path, item)
            if not item.startswith('.'):
                if os.path.isfile(item_path):
                    current_files.append(item)
                elif os.path.isdir(item_path):
                    remaining_folders.append(item)
    
    # 添加保留的文件到有效文件列表
    all_valid_filenames = set(valid_filenames)
    for url, filename in existing_files_map.items():
        all_valid_filenames.add(filename)
    
    return {
        'valid_filenames': sorted(list(all_valid_filenames)),
        'current_files': sorted(current_files),
        'remaining_folders': sorted(remaining_folders)
    }

def open_network_browser():
    """处理browser参数：通过ListItem.FileNameAndPath获取选中文件并打开网络位置"""
    xbmc.log("===== 执行网络位置浏览功能 =====", xbmc.LOGINFO)
    
    # 1. 获取选中文件的完整路径（严格使用ListItem.FileNameAndPath）
    selected_filepath = xbmc.getInfoLabel("ListItem.FileNameAndPath")
    if not selected_filepath:
        xbmc.log("错误：无法获取ListItem.FileNameAndPath", xbmc.LOGERROR)
        xbmc.executebuiltin("Notification(错误,未获取到选中文件路径,5000)")
        return
    
    xbmc.log(f"获取到选中文件路径: {selected_filepath}", xbmc.LOGINFO)
    
    # 2. 转换为本地系统路径并验证文件存在性
    local_filepath = translate_path(selected_filepath)
    if not os.path.exists(local_filepath) or not os.path.isfile(local_filepath):
        xbmc.log(f"错误：选中路径不是有效文件 - {local_filepath}", xbmc.LOGERROR)
        xbmc.executebuiltin("Notification(错误,选中项不是有效文件,5000)")
        return
    
    # 3. 读取文件内容提取Original URL
    original_url = None
    try:
        with open(local_filepath, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line.startswith("Original URL:"):
                    # 提取URL部分（分割后去除前后空格）
                    original_url = stripped_line.split("Original URL:", 1)[1].strip()
                    break
    except Exception as e:
        xbmc.log(f"错误：读取文件失败 - {str(e)}", xbmc.LOGERROR)
        xbmc.executebuiltin("Notification(错误,读取文件内容失败,5000)")
        return
    
    # 4. 验证URL提取结果
    if not original_url:
        xbmc.log("错误：文件中未找到Original URL条目", xbmc.LOGERROR)
        xbmc.executebuiltin("Notification(错误,文件格式无效,5000)")
        return
    
    xbmc.log(f"成功提取Original URL: {original_url}", xbmc.LOGINFO)
    
    # 5. 执行ActivateWindow打开视频窗口（处理特殊字符）
    try:
        # 对URL进行Kodi命令兼容的转义处理
        escaped_url = original_url.replace("'", "\\'").replace('"', '\\"').replace(' ', '%20')
        activate_command = f"ActivateWindow(Videos,{escaped_url},return)"
        xbmc.log(f"执行命令: {activate_command}", xbmc.LOGINFO)
        
        # 执行命令并反馈
        xbmc.executebuiltin(activate_command)
        
    except Exception as e:
        xbmc.log(f"错误：执行命令失败 - {str(e)}", xbmc.LOGERROR)
        xbmc.executebuiltin("Notification(错误,打开网络位置失败,5000)")

def main():
    """主执行函数"""
    # 处理脚本参数
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    if "browser" in args:
        open_network_browser()
        return
    
    # 原始同步逻辑
    xbmc.log("===== 开始同步Network文件夹 =====", xbmc.LOGINFO)
    
    # 初始化
    network_path = ensure_network_folder()
    network_locations = parse_mediasources()
    
    # 查找network目录下文件名中不包含服务器名/IP但内容URL匹配的文件
    existing_files_map = find_existing_files_without_server_name(network_path, network_locations)
    
    valid_filenames = [loc['filename'] for loc in network_locations]
    
    xbmc.log(f"有效文件列表: {valid_filenames}", xbmc.LOGINFO)
    
    # 同步前获取文件夹状态
    before_state = get_folder_state(network_path)
    
    # 核心同步操作
    sync_network_files(network_path, network_locations, existing_files_map)
    
    # 同步后获取文件夹状态
    after_state = get_folder_state(network_path)
    
    # 获取同步状态
    status = get_sync_status(network_path, valid_filenames, existing_files_map)
    
    # 输出状态报告
    xbmc.log(f"\n===== 同步状态报告 =====", xbmc.LOGINFO)
    xbmc.log(f"预期文件: {status['valid_filenames']}", xbmc.LOGINFO)
    xbmc.log(f"实际文件: {status['current_files']}", xbmc.LOGINFO)
    xbmc.log(f"残留文件夹: {status['remaining_folders']}", xbmc.LOGINFO)
    
    # 验证结果
    if status['remaining_folders']:
        xbmc.log(f"⚠️ 警告：存在残留文件夹，请检查", xbmc.LOGWARNING)
    if set(status['valid_filenames']) == set(status['current_files']):
        xbmc.log(f"✅ 同步成功！所有文件匹配", xbmc.LOGINFO)
    else:
        xbmc.log(f"❌ 同步异常！文件不匹配", xbmc.LOGERROR)
    
    # 检测内容变化并决定是否重载皮肤
    if before_state != after_state:
        xbmc.log("检测到文件夹内容发生变化，执行皮肤重载", xbmc.LOGINFO)
        xbmc.executebuiltin("ReloadSkin()")
    else:
        xbmc.log("文件夹内容无变化，无需重载皮肤", xbmc.LOGINFO)
    
    xbmc.log("===== Network文件夹同步完成 =====\n", xbmc.LOGINFO)

if __name__ == "__main__":
    main()