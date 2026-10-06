# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
import json
import os
import re
import random
import difflib
import shutil

# 兼容不同Kodi版本的路径转换
try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath

# 常量
SKIN_SETTING_FOLDER = "thumbfolder"
FAV_XML_PATH = "special://userdata/favourites.xml"
LOCAL_THUMB_DIR_SPECIAL = "special://userdata/Thumbnails/favthumb/"
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')

def log(msg):
    xbmc.log("[favthumb.py] %s" % msg, level=xbmc.LOGINFO)

def get_skin_string(key):
    return xbmc.getInfoLabel("Skin.String(%s)" % key)

def set_skin_string(key, value):
    xbmc.executebuiltin("Skin.SetString(%s,%s)" % (key, value))

def get_images_recursive(folder_path):
    """递归获取指定文件夹及其子文件夹下的所有图片文件列表"""
    real_path = translatePath(folder_path)
    images = []
    if not os.path.exists(real_path):
        return images
    
    for root, dirs, files in os.walk(real_path):
        for f in files:
            if f.lower().endswith(IMAGE_EXTS):
                abs_path = os.path.join(root, f)
                # 存储绝对路径和文件名，方便后续复制
                images.append((abs_path, f))
    return images

def parse_favourites():
    """解析 favourites.xml"""
    favs = []
    xml_path = translatePath(FAV_XML_PATH)
    
    if not os.path.exists(xml_path):
        return favs
        
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for fav in root.findall('favourite'):
            name = fav.get('name', '')
            thumb = fav.get('thumb', '')
            action = fav.text.strip() if fav.text else ''
            
            # 提取 windowparameter (视频文件或文件夹路径)
            match = re.search(r'ActivateWindow\(\d+,\s*"([^"]+)"', action)
            window_param = match.group(1) if match else ''
            
            favs.append({
                'name': name,
                'thumb': thumb,
                'window_param': window_param,
                'action': action
            })
    except Exception as e:
        log("Error parsing favourites.xml: %s" % str(e))
        
    return favs

def calc_similarity(str1, str2):
    """计算两个字符串的相似度 (0.0 到 1.0)"""
    if not str1 or not str2:
        return 0.0
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def find_best_match_image(name, image_list):
    """在图片列表中查找与名称字符重合度最高的图片"""
    if not image_list:
        return None
        
    best_score = 0.0
    best_images = []
    
    for abs_path, img_filename in image_list:
        # 去除扩展名进行比较
        img_name_no_ext = os.path.splitext(img_filename)[0]
        score = calc_similarity(name, img_name_no_ext)
        
        if score > best_score:
            best_score = score
            best_images = [(abs_path, img_filename)]
        elif score == best_score and score > 0:
            best_images.append((abs_path, img_filename))
            
    # 如果没有任何重合字符 (best_score == 0)，则随机选择一个
    if best_score == 0:
        return random.choice(image_list)
        
    # 如果有多个最高分，随机选一个
    return random.choice(best_images)

def copy_image_to_local(src_abs_path, filename):
    """将图片复制到本地缩略图目录，直接覆盖同名文件"""
    dest_dir_real = translatePath(LOCAL_THUMB_DIR_SPECIAL)
    if not os.path.exists(dest_dir_real):
        os.makedirs(dest_dir_real)
        
    dest_abs_path = os.path.join(dest_dir_real, filename)
        
    try:
        # shutil.copy2 会保留元数据并覆盖目标文件
        shutil.copy2(src_abs_path, dest_abs_path)
        # 返回 special:// 路径供 Kodi 使用
        return LOCAL_THUMB_DIR_SPECIAL + filename
    except Exception as e:
        log("Copy failed: %s" % str(e))
        return None

def rpc_add_favourite(title, window_param, thumbnail):
    """通过 JSON-RPC 添加/更新收藏夹"""
    payload = {
        "jsonrpc": "2.0",
        "method": "Favourites.AddFavourite",
        "params": {
            "title": title,
            "windowparameter": window_param,
            "type": "window",
            "thumbnail": thumbnail,
            "window": "Videos"
        },
        "id": 1
    }
    query = json.dumps(payload)
    xbmc.executeJSONRPC(query)

def process_favourites(indices_to_process, all_favs, image_list):
    """处理选中的收藏夹条目"""
    count = 0
    
    progress = xbmcgui.DialogProgress()
    progress.create("处理中", "正在匹配封面图...")
    total = len(indices_to_process)
    
    for i, idx in enumerate(indices_to_process):
        if progress.iscanceled():
            break
            
        fav = all_favs[idx]
        name = fav['name']
        original_thumb = fav['thumb']
        window_param = fav['window_param']
        
        progress.update(int((i / total) * 100), "正在处理: %s" % name)
        
        # 1. 寻找最佳匹配图片
        best_match = find_best_match_image(name, image_list)
        if not best_match:
            continue
            
        src_abs_path, img_filename = best_match
        
        # 2. 复制图片到本地 (直接覆盖)
        local_thumb_path = copy_image_to_local(src_abs_path, img_filename)
        if not local_thumb_path:
            continue
            
        # 3. 执行两次 JSON-RPC
        # 第一次：带原封面图路径
        rpc_add_favourite(name, window_param, original_thumb)
        # 第二次：带新封面图路径
        rpc_add_favourite(name, window_param, local_thumb_path)
        
        count += 1
        log("Updated: %s -> %s" % (name, img_filename))
        
    progress.close()
    return count

def check_thumb_folder():
    """检查封面图文件夹及其子文件夹是否有效且包含图片"""
    thumb_folder = get_skin_string(SKIN_SETTING_FOLDER)
    images = get_images_recursive(thumb_folder)
    
    if not thumb_folder or not images:
        xbmcgui.Dialog().ok("错误", "封面图文件夹路径无效，请返回主选择菜单重新指定封面图文件夹!")
        return None, None
        
    return thumb_folder, images

def delete_all_local_thumbs():
    """删除 favthumb 目录下的所有文件"""
    dir_real = translatePath(LOCAL_THUMB_DIR_SPECIAL)
    if not os.path.exists(dir_real):
        return True
        
    try:
        for filename in os.listdir(dir_real):
            file_path = os.path.join(dir_real, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        return True
    except Exception as e:
        log("Delete failed: %s" % str(e))
        return False

def is_thumb_valid(thumb_path):
    """
    检查封面图路径是否有效且文件真实存在
    """
    if not thumb_path:
        return False
    
    try:
        # 将 special:// 路径转换为系统真实路径
        real_path = translatePath(thumb_path)
        # 检查文件是否存在
        return os.path.exists(real_path) and os.path.isfile(real_path)
    except Exception as e:
        log("Check thumb valid error: %s" % str(e))
        return False

def main():
    while True:
        options = [
            "指定封面图文件夹",
            "选择分库自动匹配封面图(可多选)",
            "所有分库自动匹配封面图",
            "[COLOR red]删除自动匹配的封面图及其残余文件[/COLOR]"
        ]
        
        selected = xbmcgui.Dialog().select("封面图管理菜单", options)
        
        # 用户按 ESC 或取消
        if selected == -1:
            break
            
        # ================= 选项 1 =================
        if selected == 0:
            path = xbmcgui.Dialog().browse(0, "选择封面图文件夹", "files")
            if path:
                if not path.endswith('/'):
                    path += '/'
                
                # 检查该路径及其子文件夹下是否包含图片文件
                images_check = get_images_recursive(path)
                if not images_check:
                    xbmcgui.Dialog().ok("提示", "您选择的封面图文件夹下没有图片文件，请返回主选择菜单重新指定封面图文件夹!")
                else:
                    set_skin_string(SKIN_SETTING_FOLDER, path)
                    xbmcgui.Dialog().notification("成功", "已设置封面图文件夹", xbmcgui.NOTIFICATION_INFO, 3000)
            continue
            
        # ================= 选项 4 =================
        elif selected == 3:
            # 弹出确认窗口
            if not xbmcgui.Dialog().yesno("确认", "此操作会删除所有自动匹配分库的封面图，是否继续？\n选择“是”继续进行，选择“否”取消操作。"):
                # 用户选择“否”，返回上一级选择窗口（即继续 while 循环）
                continue
                
            # 用户选择“是”，执行删除
            if delete_all_local_thumbs():
                # 执行 ReloadSkin
                xbmc.executebuiltin("ReloadSkin()")
                # 弹出确认窗口
                xbmcgui.Dialog().ok("完成", "已删除全部封面图残留文件！")
                # 用户确认后关闭脚本
                break
            else:
                xbmcgui.Dialog().ok("错误", "删除文件时发生错误，请查看日志。")
                # 出错也关闭脚本，或者可以选择 continue 让用户重试，这里按常规逻辑关闭
                break

        # ================= 选项 2 & 3 前置检查 =================
        thumb_folder, image_list = check_thumb_folder()
        if not thumb_folder:
            continue  # 返回主菜单
            
        all_favs = parse_favourites()
        if not all_favs:
            xbmcgui.Dialog().ok("提示", "未找到收藏夹条目 (favourites.xml 为空或不存在)")
            continue
            
        # ================= 选项 2 =================
        if selected == 1:
            # 构建多选列表
            display_list = []
            for fav in all_favs:
                name = fav['name']
                thumb = fav['thumb']
                
                # 优化逻辑：检查封面图路径是否存在且文件真实存在
                if is_thumb_valid(thumb):
                    label = "%s - [COLOR green]已有封面图[/COLOR]" % name
                else:
                    label = "%s - [COLOR yellow]没有封面图[/COLOR]" % name
                    
                display_list.append(label)
                
            selected_indices = xbmcgui.Dialog().multiselect("选择要匹配的收藏夹", display_list)
            if not selected_indices:
                continue
                
            modified_count = process_favourites(selected_indices, all_favs, image_list)
            xbmcgui.Dialog().ok("完成", "已完成自动匹配封面图 %d 个！" % modified_count)
            break  # 关闭脚本
            
        # ================= 选项 3 =================
        elif selected == 2:
            if not xbmcgui.Dialog().yesno("确认", "此操作会覆盖原有手动选择的封面图，是否继续？\n选择“是”继续进行，选择“否”取消操作。"):
                continue
                
            # 全选所有条目
            all_indices = list(range(len(all_favs)))
            modified_count = process_favourites(all_indices, all_favs, image_list)
            xbmcgui.Dialog().ok("完成", "已完成自动匹配封面图 %d 个！" % modified_count)
            break  # 关闭脚本

if __name__ == '__main__':
    main()