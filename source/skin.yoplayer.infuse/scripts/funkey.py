# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
from threading import Timer
import os
import shutil

# ------------------- 核心配置参数（可自定义修改） -------------------
BUTTON_CONFIGS = [
    {"name": "一键呼出搜索(全局生效)", "function": "RunScript(special://skin/scripts/search.py,select)"},
    {"name": "一键启动巨库(需安装巨库插件)(全局生效)", "function": "RunAddon(plugin.video.juku)"},
    {"name": "一键呼出影视分库页面(全局生效)", "function": "ActivateWindow(Favouritesbrowser)"},
    {"name": "一键电视直播页(全局生效)", "function": "ActivateWindow(TVChannels)"},
    {"name": "一键视频源页(全局生效)", "function": "ActivateWindow(Videos,Files,return)"},
    {"name": "一键电影页面(全局生效)", "function": "ActivateWindow(Videos,MovieTitles,return)"},
    {"name": "一键剧集页面(全局生效)", "function": "ActivateWindow(Videos,TVShowTitles,return)"},
    {"name": "一键插件页面(全局生效)", "function": "ActivateWindow(addonbrowser,addons://user/,return)"},
    {"name": "一键设置页面(全局生效)", "function": "ActivateWindow(Settings)"},
    {"name": "一键快速关机(全局生效)", "function": "RunScript(special://skin/scripts/fastoff.py)"},
    {"name": "一键截图(全局生效)", "function": "Screenshot"},
    {"name": "一键呼出信息页(播放中生效)", "function": "playerprocessinfo"},
    {"name": "一键呼出字幕(播放中生效)", "function": "activatewindow(1144)"},
    {"name": "一键呼出音轨(播放中生效)", "function": "activatewindow(1145)"},
    {"name": "一键VS10转换(播放中生效)", "function": "activatewindow(1116)"},
    {"name": "一键呼出DEBUG页(播放中生效)", "function": "playerdebug"},
    {"name": "片头片尾标记(播放中生效)", "function": "RunScript(special://skin/scripts/tvjump.py,record)"},
    {"name": "删除片头片尾标记(播放中生效)", "function": "RunScript(special://skin/scripts/tvjump.py,delet)"},
    {"name": "弹出剧集列表(播放中生效)", "function": "activatewindow(1140)"},
    {"name": "退出播放弹出确认窗(播放中生效)", "function": "ActivateWindow(1126)"},
    {"name": "R10内核字幕上移(播放中生效)", "function": "RunScript(special://skin/scripts/subtitleset.py,posup)"},
    {"name": "R10内核字幕下移(播放中生效)", "function": "RunScript(special://skin/scripts/subtitleset.py,posdown)"},
    {"name": "R10内核字幕放大(播放中生效)", "function": "RunScript(special://skin/scripts/subtitleset.py,zoomup)"},
    {"name": "R10内核字幕缩小(播放中生效)", "function": "RunScript(special://skin/scripts/subtitleset.py,zoomdown)"},
    {"name": "步进增加播放倍速(播放中生效)", "function": "PlayerControl(tempoup)"},
    {"name": "步进降低播放倍速(播放中生效)", "function": "PlayerControl(tempodown)"},
    {"name": "1.5倍速播放(播放中生效)", "function": "PlayerControl(tempo(1.5))"},
    {"name": "快进(播放中生效)", "function": "FastForward"},
    {"name": "回退(播放中生效)", "function": "Rewind"},
    {"name": "下一集/频道/首(播放中生效)", "function": "RunScript(special://skin/scripts/nextitem.py,next)"},
    {"name": "上一集/频道/首(播放中生效)", "function": "RunScript(special://skin/scripts/nextitem.py,Previous)"},
    {"name": "快进10分钟(播放中生效)", "function": "BigStepForward"},
    {"name": "快退10分钟(播放中生效)", "function": "BigStepBack"},
    {"name": "呼出音频偏移窗口(播放中生效)", "function": "AudioDelay"},
    {"name": "呼出字幕偏移窗口(播放中生效)", "function": "subtitledelay"},
    {"name": "字幕位置向上移动(播放中生效)", "function": "subtitleshiftup"},
    {"name": "字幕位置向下移动(播放中生效)", "function": "subtitleshiftdown"},
    {"name": "呼出晓大筛选(需安装晓大筛选插件)(全局生效)", "function": "RunScript(plugin.video.filteredmovies)"},
    {"name": "一键缩放画面(播放中生效)", "function": "RunScript(special://skin/scripts/videozoom.py,remote)"},
    {"name": "设置缩放比例(播放中生效)", "function": "RunScript(special://skin/scripts/videozoom.py,set)"},
    {"name": "切换画面长宽比例(播放中生效)", "function": "AspectRatio"}
]

# ------------------- 全局变量 -------------------
MODIFIED_FLAG = False  # 标记genkey.xml是否被修改

# ------------------- 通用工具函数 -------------------
def log(message, level=xbmc.LOGINFO):
    """KODI日志输出函数"""
    xbmc.log(f"[MultiKeySetting] {message}", level)

def get_kodi_version():
    """获取KODI主版本号（如18、19、20）"""
    version = xbmc.getInfoLabel("System.BuildVersion")
    main_version = int(version.split('.')[0]) if version else 18
    log(f"检测到KODI版本：{main_version}")
    return main_version

def translate_special_path(special_path):
    """兼容所有KODI版本的特殊路径转换"""
    kodi_version = get_kodi_version()
    if kodi_version >= 19:
        abs_path = xbmcvfs.translatePath(special_path)
    else:
        abs_path = xbmc.translatePath(special_path)
    abs_path = os.path.normpath(abs_path)
    log(f"转换路径：{special_path} → {abs_path}")
    return abs_path

def get_gen_xml_path():
    """获取gen.xml的绝对路径（兼容所有KODI系统+版本）"""
    userdata_path = translate_special_path("special://userdata/")
    keymaps_dir = os.path.join(userdata_path, "keymaps")
    if not xbmcvfs.exists(keymaps_dir):
        xbmcvfs.mkdirs(keymaps_dir)
        log(f"创建keymaps文件夹：{keymaps_dir}")
    gen_xml_path = os.path.join(keymaps_dir, "gen.xml")
    log(f"gen.xml最终路径：{gen_xml_path}")
    return gen_xml_path

def get_genkey_xml_path():
    """获取genkey.xml临时文件的绝对路径"""
    gen_xml_path = get_gen_xml_path()
    genkey_xml_path = os.path.join(os.path.dirname(gen_xml_path), "genkey.xml")
    log(f"genkey.xml临时文件路径：{genkey_xml_path}")
    return genkey_xml_path

def prettify_xml(element, indent='  ', level=0):
    """
    对XML节点进行完美缩进格式化，完全匹配KODI keymaps标准格式
    """
    space = indent * level
    space_child = indent * (level + 1)
    result = f"{space}<{element.tag}"
    for key, value in element.attrib.items():
        result += f' {key}="{value}"'
    children = list(element)
    if element.text and element.text.strip() and not children:
        result += f">{element.text}</{element.tag}>\n"
    else:
        result += ">\n"
        if children:
            for child in children:
                result += prettify_xml(child, indent, level + 1)
        result += f"{space}</{element.tag}>\n"
    return result

def init_gen_xml():
    """初始化gen.xml文件（不存在则创建指定结构）"""
    gen_xml_path = get_gen_xml_path()
    if not xbmcvfs.exists(gen_xml_path):
        root = ET.Element("keymap")
        global_node = ET.SubElement(root, "global")
        ET.SubElement(global_node, "keyboard")
        home_node = ET.SubElement(root, "Home")
        ET.SubElement(home_node, "keyboard")
        fullscreenvideo_node = ET.SubElement(root, "fullscreenvideo")
        ET.SubElement(fullscreenvideo_node, "keyboard")
        fullscreenlivetv_node = ET.SubElement(root, "fullscreenlivetv")
        ET.SubElement(fullscreenlivetv_node, "keyboard")
        
        xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'
        xml_body = prettify_xml(root)
        final_xml = xml_header + xml_body
        
        with open(gen_xml_path, 'w', encoding='utf-8') as f:
            f.write(final_xml)
        log(f"创建默认结构的gen.xml文件：{gen_xml_path}")

def init_genkey_xml():
    """初始化genkey.xml临时文件（删除原有→复制gen.xml）"""
    gen_xml_path = get_gen_xml_path()
    genkey_xml_path = get_genkey_xml_path()
    
    if xbmcvfs.exists(genkey_xml_path):
        os.remove(genkey_xml_path)
        log(f"删除已存在的genkey.xml：{genkey_xml_path}")
    
    shutil.copy2(gen_xml_path, genkey_xml_path)
    log(f"创建genkey.xml临时文件（复制自gen.xml）：{genkey_xml_path}")

def get_or_create_single_node(parent, child_tag):
    """确保父节点下只有一个指定标签的子节点"""
    child_node = parent.find(child_tag)
    if child_node is None:
        child_node = ET.SubElement(parent, child_tag)
        log(f"在{parent.tag}下创建唯一的{child_tag}节点")
    return child_node

def get_target_parent_node_info(root, function_name):
    """根据功能名称决定将按键配置到哪个父节点"""
    if "全局生效" in function_name:
        global_node = get_or_create_single_node(root, "global")
        keyboard_node = get_or_create_single_node(global_node, "keyboard")
        log(f"功能'{function_name}'将配置到global节点下")
        return keyboard_node, "global"
    else:
        fullscreenvideo_node = get_or_create_single_node(root, "fullscreenvideo")
        keyboard_node = get_or_create_single_node(fullscreenvideo_node, "keyboard")
        log(f"功能'{function_name}'将配置到fullscreenvideo节点下")
        return keyboard_node, "fullscreenvideo"

def get_or_create_playerprocessinfo_node(root):
    """获取或创建playerprocessinfo节点及其keyboard子节点"""
    playerprocessinfo_node = root.find("playerprocessinfo")
    if playerprocessinfo_node is None:
        playerprocessinfo_node = ET.SubElement(root, "playerprocessinfo")
    keyboard_node = playerprocessinfo_node.find("keyboard")
    if keyboard_node is None:
        keyboard_node = ET.SubElement(playerprocessinfo_node, "keyboard")
    return keyboard_node

def get_or_create_fullscreenlivetv_node(root):
    """获取或创建fullscreenlivetv节点及其keyboard子节点"""
    fullscreenlivetv_node = root.find("fullscreenlivetv")
    if fullscreenlivetv_node is None:
        fullscreenlivetv_node = ET.SubElement(root, "fullscreenlivetv")
    keyboard_node = fullscreenlivetv_node.find("keyboard")
    if keyboard_node is None:
        keyboard_node = ET.SubElement(fullscreenlivetv_node, "keyboard")
    return keyboard_node

# ------------------- 删除按键相关函数 -------------------
def delete_single_button_key(button_index):
    """删除单个功能对应的按键节点"""
    global MODIFIED_FLAG
    button = BUTTON_CONFIGS[button_index]
    function = button["function"]
    genkey_xml_path = get_genkey_xml_path()
    
    if not xbmcvfs.exists(genkey_xml_path):
        return False
    
    try:
        tree = ET.parse(genkey_xml_path)
        root = tree.getroot()
        target_keyboard_node, _ = get_target_parent_node_info(root, button["name"])
        
        deleted = False
        target_nodes = [k for k in target_keyboard_node.findall("key") if k.text and k.text.strip() == function]
        for node in target_nodes:
            target_keyboard_node.remove(node)
            deleted = True
            
        if function == "playerprocessinfo":
            pp_kb = get_or_create_playerprocessinfo_node(root)
            for node in [k for k in pp_kb.findall("key") if k.text and k.text.strip() == "back"]:
                pp_kb.remove(node)
                deleted = True
                
        if function == "RunScript(special://skin/scripts/nextitem.py,next)":
            tv_kb = get_or_create_fullscreenlivetv_node(root)
            for node in [k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelUp"]:
                tv_kb.remove(node)
                deleted = True
        elif function == "RunScript(special://skin/scripts/nextitem.py,Previous)":
            tv_kb = get_or_create_fullscreenlivetv_node(root)
            for node in [k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelDown"]:
                tv_kb.remove(node)
                deleted = True
        
        if deleted:
            xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'
            with open(genkey_xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_header + prettify_xml(root))
            MODIFIED_FLAG = True
            return True
        return False
    except Exception as e:
        log(f"删除单个按键配置失败：{e}", xbmc.LOGERROR)
        return False

def delete_all_button_keys():
    """遍历所有功能按键，删除genkey.xml中已配置的按键节点"""
    global MODIFIED_FLAG
    genkey_xml_path = get_genkey_xml_path()
    if not xbmcvfs.exists(genkey_xml_path):
        xbmcgui.Dialog().ok("提示", "临时配置文件不存在，无需删除")
        return
    
    # 【修改】增加二次确认窗口
    dialog = xbmcgui.Dialog()
    if not dialog.yesno("确认删除", "确定要删除[COLOR red]所有[/COLOR]已配置的多功能按键ID吗？\n此操作不可撤销。"):
        return

    try:
        tree = ET.parse(genkey_xml_path)
        root = tree.getroot()
        deleted_count = 0
        
        for idx, button in enumerate(BUTTON_CONFIGS):
            function = button["function"]
            if get_button_current_key_id_and_mode(function) == "空白":
                continue
            
            target_keyboard_node, _ = get_target_parent_node_info(root, button["name"])
            for node in [k for k in target_keyboard_node.findall("key") if k.text and k.text.strip() == function]:
                target_keyboard_node.remove(node)
                deleted_count += 1
            
            if function == "playerprocessinfo":
                pp_kb = get_or_create_playerprocessinfo_node(root)
                for node in [k for k in pp_kb.findall("key") if k.text and k.text.strip() == "back"]:
                    pp_kb.remove(node)
                    deleted_count += 1
            if function == "RunScript(special://skin/scripts/nextitem.py,next)":
                tv_kb = get_or_create_fullscreenlivetv_node(root)
                for node in [k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelUp"]:
                    tv_kb.remove(node)
                    deleted_count += 1
            elif function == "RunScript(special://skin/scripts/nextitem.py,Previous)":
                tv_kb = get_or_create_fullscreenlivetv_node(root)
                for node in [k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelDown"]:
                    tv_kb.remove(node)
                    deleted_count += 1
        
        if deleted_count > 0:
            xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'
            with open(genkey_xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_header + prettify_xml(root))
            MODIFIED_FLAG = True
            xbmcgui.Dialog().ok("完成", f"成功删除{deleted_count}个多功能按键配置")
        else:
            xbmcgui.Dialog().ok("提示", "未找到任何已配置的多功能按键，无需删除")
    except Exception as e:
        log(f"删除所有按键配置失败：{e}", xbmc.LOGERROR)

# 【新增】按分类删除按键配置
def delete_category_button_keys(category_type):
    """
    删除指定分类（全局/播放中）下的所有已配置按键
    :param category_type: "global" 或 "playing"
    """
    global MODIFIED_FLAG
    genkey_xml_path = get_genkey_xml_path()
    if not xbmcvfs.exists(genkey_xml_path):
        xbmcgui.Dialog().ok("提示", "临时配置文件不存在，无需删除")
        return
    
    # 【修改】增加二次确认窗口
    dialog = xbmcgui.Dialog()
    category_name = "全局生效" if category_type == "global" else "播放中生效"
    if not dialog.yesno("确认删除", f"确定要删除[COLOR red]{category_name}[/COLOR]分类下所有已配置的多功能按键ID吗？\n此操作不可撤销。"):
        return

    try:
        tree = ET.parse(genkey_xml_path)
        root = tree.getroot()
        deleted_count = 0
        
        for idx, button in enumerate(BUTTON_CONFIGS):
            name = button["name"]
            # 分类过滤逻辑
            if category_type == "global" and "全局生效" not in name:
                continue
            if category_type == "playing" and "播放中生效" not in name:
                continue
                
            function = button["function"]
            if get_button_current_key_id_and_mode(function) == "空白":
                continue
            
            target_keyboard_node, _ = get_target_parent_node_info(root, button["name"])
            for node in [k for k in target_keyboard_node.findall("key") if k.text and k.text.strip() == function]:
                target_keyboard_node.remove(node)
                deleted_count += 1
            
            if function == "playerprocessinfo":
                pp_kb = get_or_create_playerprocessinfo_node(root)
                for node in [k for k in pp_kb.findall("key") if k.text and k.text.strip() == "back"]:
                    pp_kb.remove(node)
                    deleted_count += 1
            if function == "RunScript(special://skin/scripts/nextitem.py,next)":
                tv_kb = get_or_create_fullscreenlivetv_node(root)
                for node in [k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelUp"]:
                    tv_kb.remove(node)
                    deleted_count += 1
            elif function == "RunScript(special://skin/scripts/nextitem.py,Previous)":
                tv_kb = get_or_create_fullscreenlivetv_node(root)
                for node in [k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelDown"]:
                    tv_kb.remove(node)
                    deleted_count += 1
        
        if deleted_count > 0:
            xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'
            with open(genkey_xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_header + prettify_xml(root))
            MODIFIED_FLAG = True
            xbmcgui.Dialog().ok("完成", f"成功删除{deleted_count}个当前分类的多功能按键配置")
        else:
            xbmcgui.Dialog().ok("提示", "当前分类下未找到任何已配置的多功能按键，无需删除")
    except Exception as e:
        log(f"删除当前分类按键配置失败：{e}", xbmc.LOGERROR)

# ------------------- XML操作核心函数 -------------------
def get_button_current_key_id_and_mode(function):
    """从genkey.xml中查找指定function对应的按键ID和模式"""
    genkey_xml_path = get_genkey_xml_path()
    if not xbmcvfs.exists(genkey_xml_path):
        return "空白"
    
    try:
        tree = ET.parse(genkey_xml_path)
        root = tree.getroot()
        
        for button in BUTTON_CONFIGS:
            if button["function"] == function:
                target_keyboard_node, _ = get_target_parent_node_info(root, button["name"])
                for key_elem in target_keyboard_node.findall("key"):
                    if key_elem.text and key_elem.text.strip() == function:
                        result_key = key_elem.get("id", "空白")
                        mod_value = key_elem.get("mod", "")
                        if mod_value == "longpress":
                            return f"{result_key}-长按"
                        elif mod_value:
                            return f"{result_key}-{mod_value}"
                        return result_key
        return "空白"
    except Exception as e:
        log(f"读取当前按键ID失败：{e}", xbmc.LOGERROR)
        return "空白"

def update_button_keymap(button_index, new_key_id, is_longpress):
    """修改genkey.xml中指定功能的按键映射"""
    global MODIFIED_FLAG
    button = BUTTON_CONFIGS[button_index]
    target_function = button["function"]
    genkey_xml_path = get_genkey_xml_path()
    
    try:
        tree = ET.parse(genkey_xml_path)
        root = tree.getroot()
        target_keyboard_node, parent_node_name = get_target_parent_node_info(root, button["name"])

        target_node = None
        for key_elem in target_keyboard_node.findall("key"):
            if key_elem.text and key_elem.text.strip() == target_function:
                target_node = key_elem
                break

        if target_node is None:
            new_key_elem = ET.Element("key", id=new_key_id)
            new_key_elem.text = target_function
            if is_longpress: new_key_elem.set("mod", "longpress")
            target_keyboard_node.append(new_key_elem)
        else:
            target_node.set("id", new_key_id)
            if is_longpress:
                target_node.set("mod", "longpress")
            else:
                if "mod" in target_node.attrib: del target_node.attrib["mod"]

        if target_function == "playerprocessinfo":
            pp_kb = get_or_create_playerprocessinfo_node(root)
            back_node = next((k for k in pp_kb.findall("key") if k.text and k.text.strip() == "back"), None)
            if back_node is None:
                back_elem = ET.Element("key", id=new_key_id)
                back_elem.text = "back"
                if is_longpress: back_elem.set("mod", "longpress")
                pp_kb.append(back_elem)
            else:
                back_node.set("id", new_key_id)
                if is_longpress: back_node.set("mod", "longpress")
                elif "mod" in back_node.attrib: del back_node.attrib["mod"]

        if target_function == "RunScript(special://skin/scripts/nextitem.py,next)":
            tv_kb = get_or_create_fullscreenlivetv_node(root)
            ch_node = next((k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelUp"), None)
            if ch_node is None:
                ch_elem = ET.Element("key", id=new_key_id)
                ch_elem.text = "ChannelUp"
                if is_longpress: ch_elem.set("mod", "longpress")
                tv_kb.append(ch_elem)
            else:
                ch_node.set("id", new_key_id)
                if is_longpress: ch_node.set("mod", "longpress")
                elif "mod" in ch_node.attrib: del ch_node.attrib["mod"]
                
        elif target_function == "RunScript(special://skin/scripts/nextitem.py,Previous)":
            tv_kb = get_or_create_fullscreenlivetv_node(root)
            ch_node = next((k for k in tv_kb.findall("key") if k.text and k.text.strip() == "ChannelDown"), None)
            if ch_node is None:
                ch_elem = ET.Element("key", id=new_key_id)
                ch_elem.text = "ChannelDown"
                if is_longpress: ch_elem.set("mod", "longpress")
                tv_kb.append(ch_elem)
            else:
                ch_node.set("id", new_key_id)
                if is_longpress: ch_node.set("mod", "longpress")
                elif "mod" in ch_node.attrib: del ch_node.attrib["mod"]

        xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'
        with open(genkey_xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_header + prettify_xml(root))
        
        MODIFIED_FLAG = True
        return True
    except Exception as e:
        log(f"修改genkey.xml失败：{e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"修改按键映射文件失败：{str(e)}")
        return False

# ------------------- 按键监听类 -------------------
class KeyListener(xbmcgui.WindowXMLDialog):
    TIMEOUT = 5

    def __new__(cls):
        try:
            import xbmcaddon
            gui_api = tuple(map(int, xbmcaddon.Addon('xbmc.gui').getAddonInfo('version').split('.')))
            file_name = "DialogNotification.xml" if gui_api >= (5, 11, 0) else "DialogKaiToast.xml"
            return super(KeyListener, cls).__new__(cls, file_name, "")
        except Exception as e:
            return super(KeyListener, cls).__new__(cls, "DialogNotification.xml", "")

    def __init__(self):
        self.key_code = None

    def start_countdown(self):
        dialog = xbmcgui.Dialog()
        for i in range(self.TIMEOUT, 0, -1):
            if self.key_code is not None: break
            dialog.notification(
                "[COLOR ff64e535]设定(超时删除原键值)[/COLOR]",
                f"请在5秒钟内设定按键（剩余{i}秒）",
                xbmcgui.NOTIFICATION_INFO, 1000
            )
            xbmc.sleep(1000)

    def onAction(self, action):
        code = action.getButtonCode()
        if code != 0:
            self.key_code = str(code)
            self.close()

    @staticmethod
    def record_key_with_countdown():
        listener = KeyListener()
        countdown_timer = Timer(0, listener.start_countdown)
        countdown_timer.start()
        timeout_timer = Timer(listener.TIMEOUT, listener.close)
        timeout_timer.start()
        listener.doModal()
        timeout_timer.cancel()
        countdown_timer.join()
        key_code = listener.key_code
        del listener
        return key_code

# ------------------- 主交互逻辑 -------------------
def show_category_menu():
    """显示一级分类菜单"""
    menu_items = [
        "自定义全局生效按键",
        "自定义播放中生效按键",
        "删除所有多功能按键ID",
        "重置遥控器配置文件(需重新选择预设遥控器)"
    ]
    return xbmcgui.Dialog().select("请选择配置类别", menu_items)

def show_sub_menu(category_type):
    """
    显示二级子菜单
    :return: -1(取消返回), -2(删除本页), 或具体的button_index
    """
    # 【修改】第一项固定为“删除本页多功能按键ID”
    menu_items = ["[COLOR red]删除本页多功能按键ID[/COLOR]"]
    index_map = [-2]  # -2 代表删除操作的特殊标记
    
    for idx, button in enumerate(BUTTON_CONFIGS):
        name = button["name"]
        if category_type == "global" and "全局生效" in name:
            current_key = get_button_current_key_id_and_mode(button["function"])
            menu_items.append(f"{button['name']} - {current_key}")
            index_map.append(idx)
        elif category_type == "playing" and "播放中生效" in name:
            current_key = get_button_current_key_id_and_mode(button["function"])
            menu_items.append(f"{button['name']} - {current_key}")
            index_map.append(idx)
            
    if len(menu_items) <= 1:
        xbmcgui.Dialog().ok("提示", "该分类下没有可用的功能项")
        return -1

    title = "自定义全局生效按键" if category_type == "global" else "自定义播放中生效按键"
    selected_idx = xbmcgui.Dialog().select(title, menu_items)
    
    if selected_idx == -1:
        return -1  # 用户按返回键
    
    return index_map[selected_idx]  # 返回 -2 或 具体的 button_index

def process_button_config(button_index):
    """处理单个按钮的配置流程"""
    button = BUTTON_CONFIGS[button_index]
    dialog = xbmcgui.Dialog()
    current_key_id = get_button_current_key_id_and_mode(button["function"])

    key_code = KeyListener.record_key_with_countdown()
    
    if not key_code or key_code == "0":
        if current_key_id != "空白":
            if delete_single_button_key(button_index):
                dialog.ok("提示", f"5秒内未检测到有效按键，已删除「{button['name']}」原有的按键配置")
            else:
                dialog.ok("提示", "5秒内未检测到有效按键，配置取消（删除原有配置失败）")
        else:
            dialog.ok("提示", "5秒内未检测到有效按键，配置取消")
        return False

    is_longpress = dialog.yesno("按键模式选择", "是否添加为长按操作？\n\n选择「是」=该按键长按生效\n选择「否」=该按键短按生效")
    press_type = "长按" if is_longpress else "短按"
    
    confirm = dialog.yesno(
        "按键确认",
        f"您设定的多功能按键ID为{press_type}「{key_code}」\n\n是否将{press_type}该按键设为“{button['name']}”呼出按键？"
    )
    if not confirm:
        return False

    return update_button_keymap(button_index, key_code, is_longpress)

def handle_exit():
    """退出流程处理"""
    global MODIFIED_FLAG
    dialog = xbmcgui.Dialog()
    
    if not MODIFIED_FLAG:
        if dialog.yesno("退出确认", "您未修改任何按键，是否退出？"):
            genkey_xml_path = get_genkey_xml_path()
            if xbmcvfs.exists(genkey_xml_path):
                os.remove(genkey_xml_path)
            return True
        return False
    else:
        if not dialog.yesno("保存确认", "您已修改自定义按键，是否保存？"):
            if dialog.yesno("退出确认", "您之前的修改将还原，是否退出？"):
                genkey_xml_path = get_genkey_xml_path()
                if xbmcvfs.exists(genkey_xml_path):
                    os.remove(genkey_xml_path)
                return True
            return False
        else:
            gen_xml_path = get_gen_xml_path()
            genkey_xml_path = get_genkey_xml_path()
            if xbmcvfs.exists(gen_xml_path): os.remove(gen_xml_path)
            os.rename(genkey_xml_path, gen_xml_path)
            xbmc.executebuiltin('action(reloadkeymaps)')
            dialog.ok("设置完成", "设定已完成，功能按键映射已生效")
            return True

def main():
    """脚本主入口"""
    global MODIFIED_FLAG
    MODIFIED_FLAG = False
    
    init_gen_xml()
    init_genkey_xml()
    
    # 外层循环：处理一级菜单
    while True:
        category_idx = show_category_menu()
        
        if category_idx == -1:
            if handle_exit():
                break
            continue
        
        if category_idx == 2:
            delete_all_button_keys()
            continue
        
        # 【新增】处理重置遥控器配置文件选项
        if category_idx == 3:
            xbmc.executebuiltin("RunScript(special://skin/scripts/resetremote.py)")
            # 执行重置指令后，清理临时文件并退出脚本
            genkey_xml_path = get_genkey_xml_path()
            if xbmcvfs.exists(genkey_xml_path):
                os.remove(genkey_xml_path)
            break
        
        category_type = "global" if category_idx == 0 else "playing" if category_idx == 1 else None
        if not category_type:
            continue
            
        # 【修改】内层循环：处理二级菜单，确保配置完成后返回二级菜单
        while True:
            selected_idx = show_sub_menu(category_type)
            
            if selected_idx == -1:
                # 用户在二级菜单按返回键，跳出内层循环，回到一级菜单
                break
            elif selected_idx == -2:
                # 用户选择了“删除本页多功能按键ID”
                delete_category_button_keys(category_type)
                # 删除后继续循环，重新显示二级菜单
                continue
            else:
                # 用户选择了具体功能进行配置
                process_button_config(selected_idx)
                # 配置完成后不 break，继续循环，重新显示二级菜单

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"脚本执行出错：{e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("错误", f"脚本执行失败：{str(e)}")
        genkey_xml_path = get_genkey_xml_path()
        if xbmcvfs.exists(genkey_xml_path):
            os.remove(genkey_xml_path) 