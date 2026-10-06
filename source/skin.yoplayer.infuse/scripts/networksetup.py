# -*- coding: utf-8 -*-
"""
Kodi网络路径管理脚本 - 优化版
此脚本提供了多种方式来管理和配置Kodi的网络路径设置
包含详细的日志输出用于故障排查
新增功能：修改网络名称后自动重载皮肤，以便刷新显示新的网络名称
重载成功后执行setfocus(9000)指令
"""

import xbmc
import xbmcgui
import xbmcvfs  # 新增导入，适配新版本Kodi路径转换
import time
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import traceback  # 用于详细异常追踪

def log_message(message, level=xbmc.LOGINFO):
    """统一的日志记录函数"""
    xbmc.log(f"[网络路径脚本优化版] {message}", level)

def show_yesno_dialog(title, message):
    """显示确认对话框"""
    log_message(f"显示确认对话框: {title}")
    dialog = xbmcgui.Dialog()
    result = dialog.yesno(title, message)
    log_message(f"确认对话框结果: {result}")
    return result

def show_input_dialog(title, default=""):
    """显示输入对话框"""
    log_message(f"显示输入对话框: {title}, 默认值: {default}")
    dialog = xbmcgui.Dialog()
    result = dialog.input(title, default, type=xbmcgui.INPUT_ALPHANUM)
    log_message(f"输入对话框结果: {result}")
    return result

def show_select_dialog(title, options):
    """显示选择对话框"""
    log_message(f"显示选择对话框: {title}, 选项数量: {len(options)}")
    dialog = xbmcgui.Dialog()
    ret = dialog.select(title, options)
    if ret >= 0:
        selected = options[ret]
        log_message(f"选择对话框结果: {selected}")
        return selected
    else:
        log_message("选择对话框取消")
        return None

def escape_url_component(component):
    """对URL组件进行编码"""
    if not component:
        log_message("URL组件为空，返回空字符串")
        return ""
    encoded = re.sub(r'([^a-zA-Z0-9._~-])', lambda m: "%%%02X" % ord(m.group(1)), component)
    log_message(f"URL组件编码: {component} -> {encoded}")
    return encoded

def wait_for_window(window_identifier, timeout=10, by_xml=False):
    """
    等待指定窗口弹出，超时返回False。
    :param window_identifier: 窗口ID (整数) 或 XML文件名 (字符串)。
    :param timeout: 超时时间，单位秒。
    :param by_xml: 如果为True，则window_identifier被视为XML文件名。
    :return: 成功找到返回True，否则返回False。
    """
    log_message(f"开始等待窗口。标识符: '{window_identifier}', 通过XML: {by_xml}")
    start_time = time.time()
    attempt_count = 0
    
    while time.time() - start_time < timeout:
        attempt_count += 1
        log_message(f"等待窗口尝试 #{attempt_count}: {time.time() - start_time:.2f}s")
        
        if by_xml:
            current_xml = xbmc.getInfoLabel('Window.Property(xmlfile)')
            log_message(f"当前XML文件: {current_xml}")
            if window_identifier in current_xml:
                log_message(f"成功检测到窗口 (XML: {window_identifier})")
                return True
        else:
            current_window_id = xbmcgui.getCurrentWindowId()
            log_message(f"当前窗口ID: {current_window_id}, 目标ID: {window_identifier}")
            if current_window_id == window_identifier:
                log_message(f"成功检测到窗口 (ID: {window_identifier})")
                return True
        
        time.sleep(0.05)
    
    log_message(f"等待窗口超时。标识符: '{window_identifier}', 总尝试次数: {attempt_count}", xbmc.LOGERROR)
    return False

def prettify_xml(elem):
    """美化XML输出，添加缩进（保持Kodi原生格式）"""
    try:
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        # 去除空行并格式化缩进
        xml_str = reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
        result = '\n'.join([line for line in xml_str.split('\n') if line.strip()])
        log_message("XML美化完成")
        return result
    except Exception as e:
        log_message(f"XML美化失败: {str(e)}", xbmc.LOGERROR)
        return ET.tostring(elem, 'utf-8').decode('utf-8')

def get_userdata_path():
    """获取Kodi userdata路径（兼容新旧版本）"""
    try:
        if hasattr(xbmc, 'translatePath'):
            # 旧版本Kodi（Leia 18及以下）
            userdata_path = xbmc.translatePath("special://userdata/")
            log_message(f"使用旧版路径转换方法: {userdata_path}")
        else:
            # 新版本Kodi（Matrix 19及以上）
            userdata_path = xbmcvfs.translatePath("special://userdata/")
            log_message(f"使用新版路径转换方法: {userdata_path}")
        
        # 兼容路径格式（确保末尾有分隔符）
        if not userdata_path.endswith(os.sep):
            userdata_path += os.sep
            log_message(f"修正路径格式，添加分隔符: {userdata_path}")
        
        log_message(f"最终userdata路径: {userdata_path}")
        return userdata_path
    except Exception as e:
        log_message(f"获取userdata路径失败: {str(e)}", xbmc.LOGERROR)
        raise

def update_mediasources_xml(url):
    """将URL添加到mediasources.xml的<network>节点中（按序号排序）"""
    try:
        log_message(f"开始更新mediasources.xml，URL: {url}")
        
        userdata_path = get_userdata_path()
        mediasources_path = os.path.join(userdata_path, "mediasources.xml")
        log_message(f"mediasources.xml路径: {mediasources_path}")

        # 解析或创建XML文件
        if os.path.exists(mediasources_path):
            log_message("mediasources.xml已存在，正在解析...")
            tree = ET.parse(mediasources_path)
            root = tree.getroot()
        else:
            # 文件不存在时创建根节点
            root = ET.Element("mediasources")
            tree = ET.ElementTree(root)
            log_message("mediasources.xml不存在，创建新文件")

        # 查找或创建<network>节点
        network_node = root.find("network")
        if network_node is None:
            network_node = ET.SubElement(root, "network")
            log_message("<network>节点不存在，创建新节点")
        else:
            log_message(f"找到<network>节点，现有location数量: {len(network_node.findall('location'))}")

        # 获取当前最大ID序号（确保序号连续递增）
        max_id = 0
        for location in network_node.findall("location"):
            loc_id = location.get("id")
            if loc_id and loc_id.isdigit():
                current_id = int(loc_id)
                if current_id > max_id:
                    max_id = current_id
                log_message(f"发现现有location ID: {current_id}")

        # 生成新序号并创建节点
        new_id = max_id + 1
        new_location = ET.SubElement(network_node, "location")
        new_location.set("id", str(new_id))
        new_location.text = url
        log_message(f"添加新location节点: id={new_id}, URL={url}")

        # 美化XML并写入文件
        xml_content = prettify_xml(root)
        log_message(f"XML内容长度: {len(xml_content)} 字符")
        
        with open(mediasources_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        log_message(f"成功更新mediasources.xml，新ID: {new_id}")

    except Exception as e:
        error_msg = f"更新mediasources.xml失败: {str(e)}"
        log_message(error_msg, xbmc.LOGERROR)
        log_message(f"详细错误信息: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"更新网络源配置文件失败:\n{str(e)}")

def reload_skin():
    """重载当前皮肤以刷新显示"""
    log_message("开始执行皮肤重载操作")
    
    # 记录当前皮肤名称
    current_skin = xbmc.getSkinDir()
    log_message(f"当前皮肤: {current_skin}")
    
    # 重载皮肤
    xbmc.executebuiltin('ReloadSkin()')
    log_message("皮肤重载命令已发送")
    
    # 等待皮肤重载完成
    time.sleep(0.8)
    log_message("皮肤重载操作完成，界面应已更新显示新的网络名称")
    
    # 设置焦点到指定控件
    log_message("执行 setfocus(9000) 指令")
    xbmc.executebuiltin('SetFocus(9000)')
    log_message("焦点已设置到控件ID 9000")

def action_modify_network_name():
    """修改网络名称：读取network目录下所有文件，允许用户修改文件名和添加名称"""
    try:
        log_message("开始执行修改网络名称操作")
        
        # 获取network目录路径
        network_path = xbmcvfs.translatePath("special://userdata/network/")
        log_message(f"Network目录路径: {network_path}")
        
        # 检查目录是否存在
        if not xbmcvfs.exists(network_path):
            log_message("network目录不存在", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok("提示", "network目录不存在")
            return
        
        # 使用os.listdir来列出目录中的所有项目
        try:
            items = os.listdir(network_path)
            log_message(f"使用os.listdir获取到的项目数量: {len(items)}")
        except OSError as e:
            log_message(f"os.listdir失败: {str(e)}", xbmc.LOGERROR)
            # 如果os.listdir失败，回退到xbmcvfs.listdir
            items = xbmcvfs.listdir(network_path)[0]
            log_message(f"使用xbmcvfs.listdir获取到的项目数量: {len(items)}")
        
        # 获取目录中的所有文件
        files = []
        for item in items:
            log_message(f"检查项目: {item}")
            if not item.startswith('.'):  # 跳过隐藏文件
                file_path = os.path.join(network_path, item)
                log_message(f"检查文件路径: {file_path}")
                
                # 使用os.path.isfile来检查是否为文件
                if os.path.isfile(file_path):
                    files.append(item)
                    log_message(f"发现网络配置文件: {item}")
                else:
                    log_message(f"项目 {item} 不是文件")
        
        log_message(f"总共找到 {len(files)} 个网络配置文件")
        
        if not files:
            log_message("network目录中没有网络配置文件", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok("提示", "network目录中没有网络配置文件")
            return
        
        # 弹出选择对话框
        selected_file = show_select_dialog("选择要修改的网络配置文件", files)
        if not selected_file:
            log_message("用户取消选择文件")
            return
        
        log_message(f"用户选择了文件: {selected_file}")
        
        # 获取用户输入的新名称
        new_name = show_input_dialog("输入新的网络名称", default="")
        if not new_name:
            log_message("用户未输入新名称")
            return
        
        log_message(f"用户输入的新名称: {new_name}")
        
        # 获取当前文件的完整路径
        old_file_path = os.path.join(network_path, selected_file)
        file_extension = os.path.splitext(selected_file)[1]  # 保留原文件扩展名
        new_file_name = new_name + file_extension
        new_file_path = os.path.join(network_path, new_file_name)
        
        log_message(f"文件重命名: {old_file_path} -> {new_file_path}")
        
        # 重命名文件
        try:
            os.rename(old_file_path, new_file_path)
            log_message(f"文件重命名成功: {selected_file} -> {new_file_name}")
        except Exception as e:
            error_msg = f"重命名文件失败: {str(e)}"
            log_message(error_msg, xbmc.LOGERROR)
            log_message(f"详细错误信息: {traceback.format_exc()}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", f"重命名文件失败:\n{str(e)}")
            return
        
        # Update file content, add name field
        try:
            log_message(f"开始更新文件内容: {new_file_path}")
            with open(new_file_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                log_message(f"原始文件内容长度: {len(content)} 字符")
                
                # Check if name field already exists
                lines = content.split('\n')
                name_exists = any(line.strip().startswith('Name:') for line in lines)
                log_message(f"文件中name字段存在: {name_exists}")
                
                # Move pointer to beginning of file
                f.seek(0)
                
                if name_exists:
                    # If name field already exists, update it
                    updated_lines = []
                    for line in lines:
                        if line.strip().startswith('Name:'):
                            updated_lines.append(f"Name: {new_name}")
                            log_message("更新现有的Name字段")
                        else:
                            updated_lines.append(line)
                    f.write('\n'.join(updated_lines))
                else:
                    # If name field doesn't exist, add it to the beginning of the file
                    lines.insert(0, f"Name: {new_name}")
                    f.write('\n'.join(lines))
                    log_message("添加新的Name字段到文件开头")
                
                f.truncate()  # Truncate possible extra bytes
            
            log_message(f"文件内容更新成功，添加了Name: {new_name}")
        except Exception as e:
            error_msg = f"更新文件内容失败: {str(e)}"
            log_message(error_msg, xbmc.LOGERROR)
            log_message(f"详细错误信息: {traceback.format_exc()}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", f"更新文件内容失败:\n{str(e)}")
            return
        
        log_message(f"网络名称修改成功: {new_file_name}")
        xbmcgui.Dialog().ok("成功", f"网络名称已修改为: {new_file_name}")
        
        # 在用户确认后执行重载皮肤和设置焦点
        log_message("用户确认网络名称修改成功，开始重载皮肤并设置焦点")
        reload_skin()
        log_message("皮肤重载和焦点设置操作完成")
        
    except Exception as e:
        error_msg = f"修改网络名称失败: {str(e)}"
        log_message(error_msg, xbmc.LOGERROR)
        log_message(f"详细错误信息: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"修改网络名称失败:\n{str(e)}")

def action_temp_add():
    """临时添加：给"本地网络"添加路径，并写入mediasources.xml"""
    log_message("开始执行临时添加操作")
    
    # 1. Select protocol
    protocol = show_select_dialog("选择网络协议", ["SMB", "NFS", "WebDAV"])
    if not protocol:
        log_message("用户取消协议选择")
        return
    
    log_message(f"用户选择协议: {protocol}")
        
    # 2. Input share name (IP address)
    share_name = show_input_dialog("输入共享名(IP地址)")
    if not share_name:
        log_message("用户未输入共享名")
        return
    
    log_message(f"用户输入共享名: {share_name}")
        
    # 3. Process parameters according to protocol and build URL
    username = ""
    password = ""
    url = ""
    
    if protocol == "SMB":
        log_message("处理SMB协议")
        username = show_input_dialog("输入用户名(无则直接确定)")
        if username:
            password = show_input_dialog("输入密码")
            if not password:
                log_message("用户未输入密码")
                xbmcgui.Dialog().ok("错误", "密码不能为空！")
                return
        url = f"smb://{escape_url_component(username)}:{escape_url_component(password)}@{share_name}/" if username and password else f"smb://{share_name}/"
            
    elif protocol == "NFS":
        log_message("处理NFS协议")
        url = f"nfs://{share_name}/"
        
    elif protocol == "WebDAV":
        log_message("处理WebDAV协议")
        port = show_input_dialog("输入端口号", "80") or "80"
        remote_path = show_input_dialog("输入远程路径", "")
        username = show_input_dialog("输入用户名(无则直接确定)")
        
        if username:
            password = show_input_dialog("输入密码")
            if not password:
                log_message("用户未输入密码")
                xbmcgui.Dialog().ok("错误", "密码不能为空！")
                return
        
        user_pass = f"{escape_url_component(username)}:{escape_url_component(password)}@" if username and password else ""
        path_part = escape_url_component(remote_path) if remote_path else ""
        if path_part and not path_part.startswith("/"):
            path_part = "/" + path_part
        if path_part and not path_part.endswith("/"):
            path_part = path_part + "/"
            
        url = f"dav://{user_pass}{share_name}:{port}{path_part}"
    
    log_message(f"构建的URL: {url}")
    
    # 4. Confirm information
    confirm_result = show_yesno_dialog("确认信息", f"协议: {protocol}\nURL: {url}\n\n是否确认？")
    if not confirm_result:
        log_message("用户取消确认")
        return
        
    # 5. Set KODI skin properties
    log_message(f"设置皮肤属性: Skin.SetBool(lanUseCustompath)")
    xbmc.executebuiltin(f'Skin.SetBool(lanUseCustompath)')
    log_message(f"设置皮肤字符串: Skin.SetString(lanCustompath,{url})")
    xbmc.executebuiltin(f'Skin.SetString(lanCustompath,{url})')
    
    # 6. Write URL to <network> node in mediasources.xml
    log_message("开始更新mediasources.xml")
    update_mediasources_xml(url)
    
    # Pop up jump confirmation dialog
    log_message("显示跳转确认对话框")
    dialog = xbmcgui.Dialog()
    go_to_location = dialog.yesno(
        "成功", 
        "以后点击本地网络将进入您设置的网络位置\n（已同步添加到系统网络源配置）\n\n是否立即跳转到该网络位置？"
    )
    
    if go_to_location:
        # User chooses to jump: directly open network location and execute script
        log_message(f"用户选择跳转，打开URL: {url}")
        xbmc.executebuiltin(f'ActivateWindow(Videos, "{url}", return)')
        xbmc.executebuiltin('RunScript(special://skin/scripts/network.py)')
    else:
        # User chooses not to jump: execute original script and simulation operations
        log_message("用户选择不跳转，执行原有操作")
        xbmc.executebuiltin('RunScript(special://skin/scripts/network.py)')

def action_permanent_add():
    """正式添加：留存自定义网络路径记录（按新逻辑执行）"""
    log_message("=== 开始执行 '正式添加' 流程 ===")

    # 1. Activate video file window
    log_message("步骤 1: 执行 ActivateWindow(Videos,Files,return)")
    xbmc.executebuiltin('ActivateWindow(Videos,Files,return)')
    
    # Wait for Videos window (10025) to pop up
    log_message("等待Videos窗口(10025)弹出")
    if not wait_for_window(10025, timeout=5):
        log_message("未能打开视频文件窗口", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", "未能打开视频文件窗口")
        return
    
    # 2. Find and click "add" item
    log_message("步骤 2: 开始查找 'add' 项目")
    current_path = xbmc.getInfoLabel('ListItem.FilenameAndPath')
    log_message(f"当前焦点项目路径: '{current_path}'")

    if current_path == "add":
        log_message("找到 'add' 项目，准备点击")
        xbmc.executebuiltin('Action(Select)')
    else:
        log_message("当前项目不是 'add'，准备遍历查找")
        container_id = xbmc.getInfoLabel('System.CurrentControlID')
        log_message(f"获取到的当前容器ID: '{container_id}'")
        if not container_id.isdigit():
            log_message("无法获取当前容器ID", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "无法获取当前容器ID")
            return
        container_id = int(container_id)
        
        log_message(f"步骤 2a: 聚焦到容器 {container_id} 的第一个元素")
        xbmc.executebuiltin(f'SetFocus({container_id}, 0, true)')
        time.sleep(0.1)
        
        max_attempts = 200
        attempts = 0
        found = False
        while attempts < max_attempts:
            current_path = xbmc.getInfoLabel('ListItem.FilenameAndPath')
            log_message(f"查找中... 尝试 {attempts}: 当前路径为 '{current_path}'")
            if current_path == "add":
                log_message("找到 'add' 项目，准备点击")
                xbmc.executebuiltin('Action(Select)')
                found = True
                break
            xbmc.executebuiltin(f'Control.Move({container_id}, -1)')
            time.sleep(0.05)
            attempts += 1
        if not found:
            log_message("未找到路径为 'add' 的项目", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "未找到路径为 'add' 的项目")
            return
    
    # 3. Click button(11) after delay
    log_message("步骤 3: 点击 'add' 后，延时0.2秒")
    time.sleep(0.2)
    log_message("准备点击 button(11)")
    xbmc.executebuiltin('SetFocus(11)')
    time.sleep(0.05)
    xbmc.executebuiltin('Action(Select)')
    log_message("已发送点击 button(11) 的指令")

    # 4. Wait for FileBrowser window to pop up (via XML filename)
    log_message("步骤 4: 等待文件浏览器窗口 (XML: FileBrowser.xml)")
    if not wait_for_window("FileBrowser.xml", timeout=5, by_xml=True):
        log_message("未能打开文件浏览器窗口", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", "未能打开文件浏览器窗口。")
        return

    # 5. Execute upward movement and click
    log_message("步骤 5: 执行 Action(Up) 然后 Action(Select)")
    xbmc.executebuiltin('Action(Up)')
    time.sleep(0.05)
    xbmc.executebuiltin('Action(Select)')

    log_message("=== '正式添加' 流程结束 ===")

def action_select_existing():
    """选择已添加的网络源：触发皮肤的路径选择对话框"""
    log_message("=== 开始执行 '选择已添加网络源' 流程 ===")
    
    # Check current setting state
    has_custom_path = xbmc.getCondVisibility("Skin.HasSetting(lanUseCustompath)")
    log_message(f"当前lanUseCustompath设置状态: {has_custom_path}")
    
    # Execute skin operation instructions
    if not has_custom_path:
        log_message("切换lanUseCustompath设置")
        xbmc.executebuiltin('Skin.ToggleSetting(lanUseCustompath)')
    
    log_message("触发Skin.SetPath(lanCustompath)")
    xbmc.executebuiltin('Skin.SetPath(lanCustompath)')
    
    log_message("=== '选择已添加网络源' 流程结束 ===")

def action_delete_location():
    """删除网络位置：从mediasources.xml中移除选定的location节点"""
    try:
        log_message("开始执行删除网络位置操作")
        
        userdata_path = get_userdata_path()
        mediasources_path = os.path.join(userdata_path, "mediasources.xml")
        log_message(f"mediasources.xml路径: {mediasources_path}")

        # Check if file exists
        if not os.path.exists(mediasources_path):
            log_message("mediasources.xml文件不存在", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok("提示", "mediasources.xml文件不存在，无网络位置可删除")
            return
        
        # Parse XML file
        log_message("解析XML文件")
        tree = ET.parse(mediasources_path)
        root = tree.getroot()
        network_node = root.find("network")
        
        # Check if network node exists and if there are location sub-nodes
        if network_node is None or len(network_node.findall("location")) == 0:
            log_message("当前没有已添加的网络位置", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok("提示", "当前没有已添加的网络位置")
            return
        
        # Collect all location node information (use index matching)
        location_list = []  # Store: {"node": node object, "display": display text}
        select_options = []
        for loc_node in network_node.findall("location"):
            loc_id = loc_node.get("id") or "未知ID"
            loc_url = loc_node.text.strip() if loc_node.text else ""
            display_text = f"{loc_id}: {loc_url}"
            location_list.append({"node": loc_node, "display": display_text})
            select_options.append(display_text)
            log_message(f"找到网络位置: {display_text}")
        
        if not select_options:
            log_message("没有可删除的网络位置", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok("提示", "当前没有已添加的网络位置")
            return
        
        # Let user select which network location to delete
        selected_option = show_select_dialog("选择要删除的网络位置", select_options)
        if not selected_option:
            log_message("用户取消选择")
            return
        
        # Get selected node by index (more reliable)
        try:
            selected_index = select_options.index(selected_option)
            target_node = location_list[selected_index]["node"]
            target_display = location_list[selected_index]["display"]
            log_message(f"用户选择删除: {target_display}")
        except (ValueError, IndexError):
            log_message("无法匹配选中的网络位置", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "无法匹配选中的网络位置")
            return
        
        # Confirm deletion operation
        confirm_result = show_yesno_dialog("确认删除", f"是否确定删除以下网络位置？\n{target_display.split(':', 1)[1].strip()}")
        if not confirm_result:
            log_message("用户取消删除操作")
            return
        
        # Delete node and save file
        network_node.remove(target_node)
        log_message(f"成功删除location节点: {target_display}")
        
        # Prettify XML and write to file
        xml_content = prettify_xml(root)
        with open(mediasources_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        log_message("网络位置删除成功")
        xbmcgui.Dialog().ok("成功", "网络位置已成功删除")
        
        # Execute skin script
        xbmc.executebuiltin('RunScript(special://skin/scripts/network.py)')
        
    except Exception as e:
        error_msg = f"删除网络位置失败: {str(e)}"
        log_message(error_msg, xbmc.LOGERROR)
        log_message(f"详细错误信息: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"删除网络位置失败:\n{str(e)}")

def main():
    """主函数：显示操作选择菜单"""
    log_message("启动网络路径管理脚本优化版")
    
    action_choice = show_select_dialog(
        "选择操作",
        [
            "临时添加(给本地网络添加路径)",
            "正式添加(添加网络源记录，自定义网络路径可选择)",
            "已添加网络源, 选择网络路径",
            "删除网络位置",
            "修改网络名称"
        ]
    )
    
    if action_choice == "临时添加(给本地网络添加路径)":
        log_message("用户选择临时添加操作")
        action_temp_add()
    elif action_choice == "正式添加(添加网络源记录，自定义网络路径可选择)":
        log_message("用户选择正式添加操作")
        action_permanent_add()
    elif action_choice == "已添加网络源, 选择网络路径":
        log_message("用户选择选择已添加网络源操作")
        action_select_existing()
    elif action_choice == "删除网络位置":
        log_message("用户选择删除网络位置操作")
        action_delete_location()
    elif action_choice == "修改网络名称":
        log_message("用户选择修改网络名称操作")
        action_modify_network_name()

if __name__ == "__main__":
    main()