# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import json
import os
import re
from xml.etree import ElementTree as ET
from xml.dom import minidom
import sys
import time

# 检查Kodi版本并导入正确的路径函数
try:
    # Kodi 19及更高版本
    from xbmcvfs import translatePath
except ImportError:
    # Kodi 18及更低版本
    from xbmc import translatePath

def get_system_path():
    """
    获取系统路径，兼容CoreELEC和Windows
    """
    if xbmc.getCondVisibility('System.Platform.Linux'):
        # CoreELEC/Linux系统
        storage_path = '/storage/tvshows/'
        database_path = translatePath('special://userdata/Database/')
    else:
        # Windows系统
        storage_path = translatePath('special://root/storage/tvshows/')
        if not os.path.exists(storage_path):
            # 如果标准路径不存在，尝试其他可能的路径
            storage_path = os.path.join(os.path.expanduser('~'), 'tvshows/')
        database_path = translatePath('special://userdata/Database/')
    
    return storage_path, database_path

def ensure_xml_file_exists(xml_path):
    """
    确保XML文件存在，如果不存在则创建
    """
    if not os.path.exists(xml_path):
        # 创建目录（如果不存在）
        directory = os.path.dirname(xml_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        # 创建初始XML文件
        root = ET.Element("episodesubs")
        tree = ET.ElementTree(root)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        xbmc.log(f"创建新的XML文件: {xml_path}", xbmc.LOGINFO)

def parse_title_for_season_episode(title):
    """
    从标题中解析季和集信息
    """
    # 匹配 S##E## 或 S#E# 格式
    pattern = r'S(\d+)E(\d+)'
    match = re.search(pattern, title, re.IGNORECASE)
    
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        return season, episode
    
    return None, None

def parse_title_for_episode_only(title):
    """
    从标题中解析仅集数信息，匹配"第数字集"格式
    """
    # 匹配 "第数字集" 格式
    pattern = r'第(\d+)集'
    match = re.search(pattern, title, re.IGNORECASE)
    
    if match:
        episode = int(match.group(1))
        return episode
    
    return None

def parse_title_for_e_only(title):
    """
    从标题中解析仅集数信息，匹配"E数字"格式
    """
    # 匹配 "E数字" 格式，支持 E##, E###, E#### 等
    pattern = r'E(\d+)'
    matches = re.findall(pattern, title, re.IGNORECASE)
    
    if matches:
        # 返回第一个匹配的集数
        episode = int(matches[0])
        return episode
    
    return None

def update_skin_episode_title():
    """
    更新皮肤中的剧集标题显示
    """
    try:
        # 获取播放器标题
        title = xbmc.getInfoLabel('Player.Title')
        xbmc.log(f"获取到的播放器标题: {title}", xbmc.LOGINFO)
        
        # 尝试解析季集信息
        season, episode = parse_title_for_season_episode(title)
        
        # 如果没找到SxE格式，尝试解析"第X集"格式
        if season is None or episode is None:
            episode = parse_title_for_episode_only(title)
        
        # 如果还没找到，尝试解析"E数字"格式
        if season is None or episode is None:
            episode = parse_title_for_e_only(title)
        
        # 根据解析结果设置皮肤字符串
        if season is not None and episode is not None:
            skin_value = f"第{season}季 第{episode}集"
            xbmc.log(f"设置皮肤变量 episodetitle 为: {skin_value}", xbmc.LOGINFO)
            xbmc.executebuiltin(f'Skin.SetString(episodetitle,{skin_value})')
        elif episode is not None:
            skin_value = f"第{episode}集"
            xbmc.log(f"设置皮肤变量 episodetitle 为: {skin_value}", xbmc.LOGINFO)
            xbmc.executebuiltin(f'Skin.SetString(episodetitle,{skin_value})')
        else:
            xbmc.log("未能从标题中解析出季集信息", xbmc.LOGINFO)
            # 如果没有解析到任何信息，清空皮肤变量
            xbmc.executebuiltin('Skin.Reset(episodetitle)')
    
    except Exception as e:
        xbmc.log(f"更新皮肤剧集标题时发生错误: {str(e)}", xbmc.LOGERROR)

def get_episode_info_from_db(db_id):
    """Use Kodi's active profile/library; never hard-code a database version."""
    try:
        request = dict(jsonrpc='2.0', id=1, method='VideoLibrary.GetEpisodeDetails',
                       params=dict(episodeid=int(db_id), properties=['tvshowid', 'season', 'episode']))
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
        item = response.get('result', {}).get('episodedetails', {})
        return item.get('tvshowid'), item.get('season'), item.get('episode')
    except (ValueError, TypeError, KeyError) as exc:
        xbmc.log('Unable to read episode metadata: {}'.format(exc), xbmc.LOGWARNING)
        return None, None, None


def get_current_audio_index():
    """
    通过JSON-RPC获取当前使用音轨的index信息
    """
    try:
        # 构建JSON-RPC请求
        request = {
            "jsonrpc": "2.0",
            "method": "Player.GetProperties",
            "params": {
                "playerid": 1,
                "properties": ["currentaudiostream"]
            },
            "id": 1
        }
        
        # 执行JSON-RPC请求
        response = xbmc.executeJSONRPC(json.dumps(request))
        result = json.loads(response)
        
        # 检查是否有错误
        if 'error' in result:
            xbmc.log(f"JSON-RPC错误: {result['error']}", xbmc.LOGERROR)
            return None
        
        # 解析结果
        if 'result' in result:
            player_props = result['result']
            current_audiostream = player_props.get('currentaudiostream', {})
            
            # 获取当前音轨的索引
            index = current_audiostream.get('index', -1)
            return index
            
    except Exception as e:
        xbmc.log(f"获取当前音轨索引时发生错误: {str(e)}", xbmc.LOGERROR)
        return None

def set_audio_by_index(index):
    """
    通过JSON-RPC设置音轨索引
    """
    try:
        # 构建JSON-RPC请求来设置音轨
        request = {
            "jsonrpc": "2.0",
            "method": "Player.SetAudioStream",
            "params": {
                "playerid": 1,
                "stream": index
            },
            "id": 1
        }
        
        # 执行JSON-RPC请求
        response = xbmc.executeJSONRPC(json.dumps(request))
        result = json.loads(response)
        
        # 检查是否有错误
        if 'error' in result:
            xbmc.log(f"设置音轨时JSON-RPC错误: {result['error']}", xbmc.LOGERROR)
            return False
        
        xbmc.log(f"成功设置音轨索引为: {index}", xbmc.LOGINFO)
        return True
            
    except Exception as e:
        xbmc.log(f"设置音轨时发生错误: {str(e)}", xbmc.LOGERROR)
        return False

def format_xml(elem):
    """
    将XML元素格式化为带缩进的漂亮字符串
    """
    try:
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        xml_str = reparsed.toprettyxml(indent="    ")
        # 移除空行
        lines = [line for line in xml_str.split("\n") if line.strip()]
        return "\n".join(lines)
    except Exception as e:
        xbmc.log(f"XML格式化失败: {e}", xbmc.LOGERROR)
        # 如果格式化失败，返回基本格式
        return ET.tostring(elem, encoding='unicode')

def record_audio_index():
    """
    记录当前音轨索引
    """
    if xbmc.getSkinDir() == 'skin.yoplayer.infuse':
        return False  # Branch memory is written only by the explicit P1 action.
    try:
        # 获取存储路径
        storage_path, _ = get_system_path()
        xml_path = os.path.join(storage_path, 'episodesub.xml')
        
        # 确保XML文件存在
        ensure_xml_file_exists(xml_path)
        
        # 检查是否为剧集内容
        is_episode_content = xbmc.getCondVisibility('VideoPlayer.Content(Episodes)')
        
        if not is_episode_content:
            # 如果不是剧集内容，检查标题是否包含S/E信息
            title = xbmc.getInfoLabel('Player.Title')
            season, episode = parse_title_for_season_episode(title)
            
            if season is None or episode is None:
                episode = parse_title_for_e_only(title)
                
            if season is None or episode is None:
                xbmc.log("非剧集内容且标题不包含S/E信息或E信息，退出", xbmc.LOGINFO)
                return
        
        # 获取当前音轨索引
        current_index = get_current_audio_index()
        if current_index is None:
            xbmc.log("无法获取当前音轨索引", xbmc.LOGERROR)
            return
        
        # 加载XML文档
        if os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            root = tree.getroot()
        else:
            root = ET.Element("episodesubs")
            tree = ET.ElementTree(root)
        
        if is_episode_content:
            # 情况1：通过数据库ID查找剧集信息
            db_id = xbmc.getInfoLabel('VideoPlayer.DBID')
            if not db_id or db_id == '':
                xbmc.log("无法获取VideoPlayer.DBID", xbmc.LOGERROR)
                return
            
            db_id = int(db_id)
            id_show, id_season, episode_number = get_episode_info_from_db(db_id)
            
            if id_show is None or id_season is None:
                xbmc.log("无法从数据库获取剧集信息", xbmc.LOGERROR)
                return
            
            # 查找或创建记录
            found_record = False
            for record in root.findall('record'):
                if (record.get('idShow') == str(id_show) and 
                    record.get('idSeason') == str(id_season) and 
                    record.get('type') == 'audio'):
                    # 更新现有记录
                    record.text = str(current_index)
                    found_record = True
                    xbmc.log(f"更新音频记录: idShow={id_show}, idSeason={id_season}, index={current_index}", xbmc.LOGINFO)
                    break
            
            if not found_record:
                # 创建新记录
                new_record = ET.SubElement(root, 'record')
                new_record.set('idShow', str(id_show))
                new_record.set('idSeason', str(id_season))
                new_record.set('type', 'audio')
                new_record.text = str(current_index)
                xbmc.log(f"创建新音频记录: idShow={id_show}, idSeason={id_season}, index={current_index}", xbmc.LOGINFO)
        else:
            # 情况2：通过文件夹路径记录
            folder_path = xbmc.getInfoLabel('Player.Folderpath')
            if not folder_path:
                xbmc.log("无法获取Player.Folderpath", xbmc.LOGERROR)
                return
            
            # 查找或创建记录
            found_record = False
            for record in root.findall('record'):
                if (record.get('path') == folder_path and 
                    record.get('type') == 'audio'):
                    # 更新现有记录
                    record.text = str(current_index)
                    found_record = True
                    xbmc.log(f"更新音频记录: path={folder_path}, index={current_index}", xbmc.LOGINFO)
                    break
            
            if not found_record:
                # 创建新记录
                new_record = ET.SubElement(root, 'record')
                new_record.set('path', folder_path)
                new_record.set('type', 'audio')
                new_record.text = str(current_index)
                xbmc.log(f"创建新音频记录: path={folder_path}, index={current_index}", xbmc.LOGINFO)
        
        # 保存XML文件（格式化）
        formatted_xml = format_xml(root)
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(formatted_xml)
        xbmc.log(f"音轨索引已记录到: {xml_path}", xbmc.LOGINFO)
        
    except Exception as e:
        xbmc.log(f"记录音轨索引时发生错误: {str(e)}", xbmc.LOGERROR)

def apply_saved_audio_index():
    """
    应用保存的音轨索引
    """
    if xbmc.getSkinDir() == 'skin.yoplayer.infuse':
        return  # The skin runtime applies explicit memory once at AVStart.
    try:
        # 检查是否为剧集内容
        is_episode_content = xbmc.getCondVisibility('VideoPlayer.Content(Episodes)')
        
        if not is_episode_content:
            # 如果不是剧集内容，检查标题是否包含S/E信息
            title = xbmc.getInfoLabel('Player.Title')
            # 使用更宽松的匹配模式
            pattern = r'S\d+E\d+'
            match = re.search(pattern, title, re.IGNORECASE)
            
            if not match:
                # 再检查是否有E数字格式
                e_pattern = r'E\d+'
                e_match = re.search(e_pattern, title, re.IGNORECASE)
                
                if not e_match:
                    xbmc.log("非剧集内容且标题不包含S数字E数字格式或E数字格式，退出", xbmc.LOGINFO)
                    return
        
        # 获取存储路径
        storage_path, _ = get_system_path()
        xml_path = os.path.join(storage_path, 'episodesub.xml')
        
        # 检查XML文件是否存在
        if not os.path.exists(xml_path):
            xbmc.log("XML文件不存在", xbmc.LOGINFO)
            return
        
        # 加载XML文档
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        target_index = None
        
        if is_episode_content:
            # 情况1：通过数据库ID查找
            db_id = xbmc.getInfoLabel('VideoPlayer.DBID')
            if not db_id or db_id == '':
                xbmc.log("无法获取VideoPlayer.DBID", xbmc.LOGERROR)
                return
            
            db_id = int(db_id)
            id_show, id_season, episode_number = get_episode_info_from_db(db_id)
            
            if id_show is None or id_season is None:
                xbmc.log("无法从数据库获取剧集信息", xbmc.LOGERROR)
                return
            
            # 查找记录
            for record in root.findall('record'):
                if (record.get('idShow') == str(id_show) and 
                    record.get('idSeason') == str(id_season) and 
                    record.get('type') == 'audio'):
                    target_index = int(record.text) if record.text else None
                    xbmc.log(f"找到保存的音轨索引: {target_index}", xbmc.LOGINFO)
                    break
        else:
            # 情况2：通过文件夹路径查找
            folder_path = xbmc.getInfoLabel('Player.Folderpath')
            if not folder_path:
                xbmc.log("无法获取Player.Folderpath", xbmc.LOGERROR)
                return
            
            # 查找记录
            for record in root.findall('record'):
                if (record.get('path') == folder_path and 
                    record.get('type') == 'audio'):
                    target_index = int(record.text) if record.text else None
                    xbmc.log(f"找到保存的音轨索引: {target_index}", xbmc.LOGINFO)
                    break
        
        if target_index is None:
            xbmc.log("在XML文件中未找到匹配的音轨索引记录", xbmc.LOGINFO)
            return
        
        # 等待播放时间超过3秒
        timeout = 30  # 最大等待30秒
        waited = 0
        while waited < timeout:
            player_time = xbmc.getInfoLabel('Player.Time')
            try:
                # 尝试解析播放时间
                if player_time and player_time.strip():
                    # Player.Time通常是 "MM:SS" 或 "H:MM:SS" 格式
                    parts = player_time.split(':')
                    if len(parts) == 2:  # MM:SS
                        seconds = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:  # H:MM:SS
                        seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    else:
                        seconds = 0
                    
                    if seconds > 3:
                        break
            except ValueError:
                pass
            
            time.sleep(0.5)
            waited += 0.5
        
        # 获取当前音轨索引
        current_index = get_current_audio_index()
        if current_index is None:
            xbmc.log("无法获取当前音轨索引", xbmc.LOGERROR)
            return
        
        # 如果当前索引与记录的索引相同，则退出
        if current_index == target_index:
            xbmc.log("当前音轨索引与记录的索引相同，无需切换", xbmc.LOGINFO)
            return
        
        # 切换到保存的音轨索引
        success = set_audio_by_index(target_index)
        
        if success:
            xbmc.log(f"成功切换到音轨索引: {target_index}", xbmc.LOGINFO)
        else:
            xbmc.log(f"切换到音幕索引 {target_index} 失败", xbmc.LOGERROR)
    
    except Exception as e:
        xbmc.log(f"应用保存的音轨索引时发生错误: {str(e)}", xbmc.LOGERROR)

def record_subtitle_index():
    """
    记录当前字幕索引
    """
    if xbmc.getSkinDir() == 'skin.yoplayer.infuse':
        return False
    try:
        # 获取存储路径
        storage_path, _ = get_system_path()
        xml_path = os.path.join(storage_path, 'episodesub.xml')
        
        # 确保XML文件存在
        ensure_xml_file_exists(xml_path)
        
        # 检查是否为剧集内容
        is_episode_content = xbmc.getCondVisibility('VideoPlayer.Content(Episodes)')
        
        if not is_episode_content:
            # 如果不是剧集内容，检查标题是否包含S/E信息
            title = xbmc.getInfoLabel('Player.Title')
            season, episode = parse_title_for_season_episode(title)
            
            if season is None or episode is None:
                episode = parse_title_for_e_only(title)
                
            if season is None or episode is None:
                xbmc.log("非剧集内容且标题不包含S/E信息或E信息，退出", xbmc.LOGINFO)
                return
        
        # 获取当前字幕索引
        current_index = get_current_subtitle_index()
        if current_index is None:
            xbmc.log("无法获取当前字幕索引", xbmc.LOGERROR)
            return
        
        # 加载XML文档
        if os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            root = tree.getroot()
        else:
            root = ET.Element("episodesubs")
            tree = ET.ElementTree(root)
        
        if is_episode_content:
            # 情况1：通过数据库ID查找剧集信息
            db_id = xbmc.getInfoLabel('VideoPlayer.DBID')
            if not db_id or db_id == '':
                xbmc.log("无法获取VideoPlayer.DBID", xbmc.LOGERROR)
                return
            
            db_id = int(db_id)
            id_show, id_season, episode_number = get_episode_info_from_db(db_id)
            
            if id_show is None or id_season is None:
                xbmc.log("无法从数据库获取剧集信息", xbmc.LOGERROR)
                return
            
            # 查找或创建记录
            found_record = False
            for record in root.findall('record'):
                if (record.get('idShow') == str(id_show) and 
                    record.get('idSeason') == str(id_season) and 
                    record.get('type') == 'sub'):
                    # 更新现有记录
                    record.text = str(current_index)
                    found_record = True
                    xbmc.log(f"更新记录: idShow={id_show}, idSeason={id_season}, index={current_index}", xbmc.LOGINFO)
                    break
            
            if not found_record:
                # 创建新记录
                new_record = ET.SubElement(root, 'record')
                new_record.set('idShow', str(id_show))
                new_record.set('idSeason', str(id_season))
                new_record.set('type', 'sub')
                new_record.text = str(current_index)
                xbmc.log(f"创建新记录: idShow={id_show}, idSeason={id_season}, index={current_index}", xbmc.LOGINFO)
        else:
            # 情况2：通过文件夹路径记录
            folder_path = xbmc.getInfoLabel('Player.Folderpath')
            if not folder_path:
                xbmc.log("无法获取Player.Folderpath", xbmc.LOGERROR)
                return
            
            # 查找或创建记录
            found_record = False
            for record in root.findall('record'):
                if (record.get('path') == folder_path and 
                    record.get('type') == 'sub'):
                    # 更新现有记录
                    record.text = str(current_index)
                    found_record = True
                    xbmc.log(f"更新记录: path={folder_path}, index={current_index}", xbmc.LOGINFO)
                    break
            
            if not found_record:
                # 创建新记录
                new_record = ET.SubElement(root, 'record')
                new_record.set('path', folder_path)
                new_record.set('type', 'sub')
                new_record.text = str(current_index)
                xbmc.log(f"创建新记录: path={folder_path}, index={current_index}", xbmc.LOGINFO)
        
        # 保存XML文件（格式化）
        formatted_xml = format_xml(root)
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(formatted_xml)
        xbmc.log(f"字幕索引已记录到: {xml_path}", xbmc.LOGINFO)
        
    except Exception as e:
        xbmc.log(f"记录字幕索引时发生错误: {str(e)}", xbmc.LOGERROR)

def apply_saved_subtitle_index():
    """
    进一步优化版应用保存的字幕索引
    """
    if xbmc.getSkinDir() == 'skin.yoplayer.infuse':
        return  # Opening fullscreen must not override an in-session selection.
    try:
        # 检查是否为剧集内容
        is_episode_content = xbmc.getCondVisibility('VideoPlayer.Content(Episodes)')
        
        if not is_episode_content:
            # 如果不是剧集内容，检查标题是否包含S/E信息
            title = xbmc.getInfoLabel('Player.Title')
            # 使用更宽松的匹配模式
            pattern = r'S\d+E\d+'
            match = re.search(pattern, title, re.IGNORECASE)
            
            if not match:
                # 再检查是否有E数字格式
                e_pattern = r'E\d+'
                e_match = re.search(e_pattern, title, re.IGNORECASE)
                
                if not e_match:
                    xbmc.log("非剧集内容且标题不包含S数字E数字格式或E数字格式，退出", xbmc.LOGINFO)
                    return
        
        # 获取存储路径
        storage_path, _ = get_system_path()
        xml_path = os.path.join(storage_path, 'episodesub.xml')
        
        # 检查XML文件是否存在
        if not os.path.exists(xml_path):
            xbmc.log("XML文件不存在", xbmc.LOGINFO)
            return
        
        # 加载XML文档
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        target_sub_index = None
        target_audio_index = None
        
        if is_episode_content:
            # 情况1：通过数据库ID查找
            db_id = xbmc.getInfoLabel('VideoPlayer.DBID')
            if not db_id or db_id == '':
                xbmc.log("无法获取VideoPlayer.DBID", xbmc.LOGERROR)
                return
            
            db_id = int(db_id)
            id_show, id_season, episode_number = get_episode_info_from_db(db_id)
            
            if id_show is None or id_season is None:
                xbmc.log("无法从数据库获取剧集信息", xbmc.LOGERROR)
                return
            
            # 查找字幕和音轨记录
            for record in root.findall('record'):
                if (record.get('idShow') == str(id_show) and 
                    record.get('idSeason') == str(id_season) and 
                    record.get('type') == 'sub'):
                    target_sub_index = int(record.text) if record.text else None
                    xbmc.log(f"找到保存的字幕索引: {target_sub_index}", xbmc.LOGINFO)
                elif (record.get('idShow') == str(id_show) and 
                      record.get('idSeason') == str(id_season) and 
                      record.get('type') == 'audio'):
                    target_audio_index = int(record.text) if record.text else None
                    xbmc.log(f"找到保存的音轨索引: {target_audio_index}", xbmc.LOGINFO)
        else:
            # 情况2：通过文件夹路径查找
            folder_path = xbmc.getInfoLabel('Player.Folderpath')
            if not folder_path:
                xbmc.log("无法获取Player.Folderpath", xbmc.LOGERROR)
                return
            
            # 查找字幕和音轨记录
            for record in root.findall('record'):
                if (record.get('path') == folder_path and 
                    record.get('type') == 'sub'):
                    target_sub_index = int(record.text) if record.text else None
                    xbmc.log(f"找到保存的字幕索引: {target_sub_index}", xbmc.LOGINFO)
                elif (record.get('path') == folder_path and 
                      record.get('type') == 'audio'):
                    target_audio_index = int(record.text) if record.text else None
                    xbmc.log(f"找到保存的音轨索引: {target_audio_index}", xbmc.LOGINFO)
        
        # 获取当前字幕和音轨索引
        current_sub_index = get_current_subtitle_index()
        current_audio_index = get_current_audio_index()
        
        # 检查是否需要改变
        sub_needs_change = (target_sub_index is not None and 
                           current_sub_index is not None and 
                           current_sub_index != target_sub_index)
        audio_needs_change = (target_audio_index is not None and 
                             current_audio_index is not None and 
                             current_audio_index != target_audio_index)
        
        # 检查字幕是否启用
        subtitles_enabled = xbmc.getCondVisibility('VideoPlayer.SubtitlesEnabled')
        
        # 如果字幕未启用且有字幕记录，则启用字幕
        if not subtitles_enabled and target_sub_index is not None:
            xbmc.log("字幕未启用，执行ShowSubtitles操作", xbmc.LOGINFO)
            xbmc.executebuiltin('Action(ShowSubtitles)')
            # 等待片刻确保字幕已启用
            xbmc.sleep(500)
        
        # 如果当前索引与记录的索引都相同，则退出
        if not sub_needs_change and not audio_needs_change:
            xbmc.log("当前字幕和音轨索引与记录的索引都相同，无需切换", xbmc.LOGINFO)
            return
        
        # 切换到保存的字幕索引
        if sub_needs_change:
            success = set_subtitle_by_index(target_sub_index)
            if success:
                xbmc.log(f"成功切换到字幕索引: {target_sub_index}", xbmc.LOGINFO)
            else:
                xbmc.log(f"切换到字幕索引 {target_sub_index} 失败", xbmc.LOGERROR)
        
        # 切换到保存的音轨索引
        if audio_needs_change:
            success = set_audio_by_index(target_audio_index)
            if success:
                xbmc.log(f"成功切换到音轨索引: {target_audio_index}", xbmc.LOGINFO)
            else:
                xbmc.log(f"切换到音轨索引 {target_audio_index} 失败", xbmc.LOGERROR)
    
    except Exception as e:
        xbmc.log(f"应用保存的字幕索引时发生错误: {str(e)}", xbmc.LOGERROR)

def get_current_subtitle_index():
    """
    通过JSON-RPC获取当前使用字幕的index信息
    """
    try:
        # 构建JSON-RPC请求
        request = {
            "jsonrpc": "2.0",
            "method": "Player.GetProperties",
            "params": {
                "playerid": 1,
                "properties": ["currentsubtitle"]
            },
            "id": 1
        }
        
        # 执行JSON-RPC请求
        response = xbmc.executeJSONRPC(json.dumps(request))
        result = json.loads(response)
        
        # 检查是否有错误
        if 'error' in result:
            xbmc.log(f"JSON-RPC错误: {result['error']}", xbmc.LOGERROR)
            return None
        
        # 解析结果
        if 'result' in result:
            player_props = result['result']
            current_subtitle = player_props.get('currentsubtitle', {})
            
            # 获取当前字幕的索引
            index = current_subtitle.get('index', -1)
            return index
            
    except Exception as e:
        xbmc.log(f"获取当前字幕索引时发生错误: {str(e)}", xbmc.LOGERROR)
        return None

def set_subtitle_by_index(index):
    """
    通过JSON-RPC设置字幕索引
    """
    try:
        # 构建JSON-RPC请求来设置字幕
        request = {
            "jsonrpc": "2.0",
            "method": "Player.SetSubtitle",
            "params": {
                "playerid": 1,
                "subtitle": index
            },
            "id": 1
        }
        
        # 执行JSON-RPC请求
        response = xbmc.executeJSONRPC(json.dumps(request))
        result = json.loads(response)
        
        # 检查是否有错误
        if 'error' in result:
            xbmc.log(f"设置字幕时JSON-RPC错误: {result['error']}", xbmc.LOGERROR)
            return False
        
        xbmc.log(f"成功设置字幕索引为: {index}", xbmc.LOGINFO)
        return True
            
    except Exception as e:
        xbmc.log(f"设置字幕时发生错误: {str(e)}", xbmc.LOGERROR)
        return False

def main():
    """
    主函数：根据参数执行相应操作
    """
    try:
        # 获取脚本参数
        args = sys.argv[1:] if len(sys.argv) > 1 else []
        param = args[0].lower() if args else ''
        
        xbmc.log(f"脚本启动，参数: {param}", xbmc.LOGINFO)
        
        # 总是执行更新皮肤剧集标题的功能
        update_skin_episode_title()
        
        if param == 'record':
            xbmc.log("执行记录字幕索引操作", xbmc.LOGINFO)
            record_subtitle_index()
        elif param == 'sub':
            xbmc.log("执行应用保存的字幕索引操作", xbmc.LOGINFO)
            apply_saved_subtitle_index()
        elif param == 'audio':
            xbmc.log("执行记录音频索引操作", xbmc.LOGINFO)
            record_audio_index()
        elif param == 'applyaudio':
            xbmc.log("执行应用保存的音频索引操作", xbmc.LOGINFO)
            apply_saved_audio_index()
        else:
            xbmc.log(f"未知参数: {param}", xbmc.LOGWARNING)
            xbmc.log("使用方法: RunScript(special://skin/scripts/epsub.py, record|sub|audio|applyaudio)", xbmc.LOGINFO)
    
    except Exception as e:
        xbmc.log(f"执行脚本时发生错误: {str(e)}", xbmc.LOGERROR)

if __name__ == "__main__":
    main()
