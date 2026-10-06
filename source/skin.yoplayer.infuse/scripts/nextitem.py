#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KODI智能播放控制脚本
支持数据库查询和文件系统查找两种方式
优化版本：确保执行播放后立即退出，不影响其他脚本
优化逻辑：在播放新内容前先停止当前播放
修复问题：优先选择相同扩展名的视频文件，改进EXXX/EpisodeXXX格式匹配
"""

import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import re
import os
import sys
import urllib.parse
from contextlib import closing
import json
import time

LOG_PREFIX = "[NextItemPlayer] "

class NextItemPlayer:
    def __init__(self):
        self.player = xbmc.Player()
        
    def get_current_filename(self):
        """获取当前播放文件名"""
        try:
            # 尝试通过JSON-RPC获取当前播放文件
            result = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.GetItem", "params": {"playerid": 1, "properties": ["file"]}, "id": 1}')
            if '"file"' in result:
                import json
                data = json.loads(result)
                return data['result']['item'].get('file', '')
        except:
            pass
            
        try:
            # 尝试音频播放器ID
            result = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.GetItem", "params": {"playerid": 0, "properties": ["file"]}, "id": 1}')
            if '"file"' in result:
                import json
                data = json.loads(result)
                return data['result']['item'].get('file', '')
        except:
            pass
            
        # 最后尝试使用InfoLabel
        try:
            filename = xbmc.getInfoLabel('Player.Filenameandpath')
            if filename and filename != "":
                return filename
        except:
            pass
            
        return ""

    def get_current_folder_path(self):
        """获取当前播放文件所在目录，支持局域网协议"""
        current_file = self.get_current_filename()
        if not current_file:
            return ""
        
        # 检测是否为网络路径协议
        network_protocols = ['smb://', 'nfs://', 'dav://', 'ftp://', 'ftps://', 'http://', 'https://', 'upnp://', 'plugin://']
        
        is_network_path = any(current_file.startswith(protocol) for protocol in network_protocols)
        
        if is_network_path:
            # 对于网络路径，使用urllib解析来获取目录部分
            parsed_url = urllib.parse.urlparse(current_file)
            path = parsed_url.path
            
            # 获取目录部分
            dir_path = os.path.dirname(path)
            
            # 重新构建URL
            folder_path = f"{parsed_url.scheme}://{parsed_url.netloc}{dir_path}"
            xbmc.log(f'{LOG_PREFIX} Network path detected, folder: {folder_path}', xbmc.LOGDEBUG)
            return folder_path
        else:
            # 本地路径处理
            if os.path.isfile(current_file):
                return os.path.dirname(current_file)
        
        return ""

    def get_current_label(self):
        """获取当前播放项的标签"""
        try:
            label = xbmc.getInfoLabel('ListItem.Label')
            if label and label != "":
                return label
        except:
            pass
            
        # 如果ListItem.Label不可用，从文件路径中提取
        current_file = self.get_current_filename()
        if current_file:
            return os.path.basename(current_file)
        return ""

    def get_player_type(self):
        """获取当前播放类型"""
        try:
            result = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.GetProperties", "params": {"playerid": 1, "properties": ["type"]}, "id": 1}')
            if '"type"' in result:
                import json
                data = json.loads(result)
                return data['result'].get('type', 'unknown')
        except:
            pass
            
        try:
            result = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.GetProperties", "params": {"playerid": 0, "properties": ["type"]}, "id": 1}')
            if '"type"' in result:
                import json
                data = json.loads(result)
                return data['result'].get('type', 'unknown')
        except:
            pass
            
        return 'unknown'

    def play_media_by_episode_id(self, episode_id):
        """通过episode ID播放媒体"""
        # 先停止当前播放
        self.player_control('stop')
        # 等待一小段时间确保播放已停止
        time.sleep(0.5)
        
        # 构造JSON-RPC请求
        json_rpc_request = {
            "jsonrpc": "2.0",
            "method": "Player.Open",
            "params": {
                "item": {
                    "episodeid": episode_id
                }
            },
            "id": 1
        }
        
        result = xbmc.executeJSONRPC(str(json_rpc_request).replace("'", '"'))
        xbmc.log(f'{LOG_PREFIX} JSON-RPC result: {result}', xbmc.LOGDEBUG)
        return result

    def get_database_path(self):
        """获取数据库路径"""
        # 使用xbmcvfs.translatePath替代xbmc.translatePath
        db_path = xbmcvfs.translatePath("special://home/userdata/Database/MyVideos131.db")
        return db_path

    def query_episode_by_dbid(self, dbid):
        """根据DBID查询episode信息"""
        db_path = self.get_database_path()
        
        if not os.path.exists(db_path):
            xbmc.log(f'{LOG_PREFIX} Database not found: {db_path}', xbmc.LOGERROR)
            return None
            
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                cursor = conn.cursor()
                query = """
                SELECT idShow, idSeason, c13 
                FROM episode_view 
                WHERE idEpisode = ?
                """
                cursor.execute(query, (dbid,))
                result = cursor.fetchone()
                
                if result:
                    return {
                        'idShow': result[0],
                        'idSeason': result[1],
                        'episode_num': int(float(result[2]))
                    }
                else:
                    xbmc.log(f'{LOG_PREFIX} Episode with DBID {dbid} not found in database', xbmc.LOGWARNING)
                    return None
                    
        except Exception as e:
            xbmc.log(f'{LOG_PREFIX} Error querying database: {str(e)}', xbmc.LOGERROR)
            return None

    def find_next_episode_by_db(self, current_info):
        """根据当前信息查找下一集"""
        db_path = self.get_database_path()
        
        if not os.path.exists(db_path):
            xbmc.log(f'{LOG_PREFIX} Database not found: {db_path}', xbmc.LOGERROR)
            return None
            
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                cursor = conn.cursor()
                query = """
                SELECT idEpisode 
                FROM episode_view 
                WHERE idShow = ? AND idSeason = ? AND CAST(c13 AS INTEGER) = ?
                """
                cursor.execute(query, (current_info['idShow'], current_info['idSeason'], current_info['episode_num'] + 1))
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                else:
                    xbmc.log(f'{LOG_PREFIX} Next episode not found in database', xbmc.LOGDEBUG)
                    return None
                    
        except Exception as e:
            xbmc.log(f'{LOG_PREFIX} Error querying next episode: {str(e)}', xbmc.LOGERROR)
            return None

    def find_prev_episode_by_db(self, current_info):
        """根据当前信息查找上一集"""
        db_path = self.get_database_path()
        
        if not os.path.exists(db_path):
            xbmc.log(f'{LOG_PREFIX} Database not found: {db_path}', xbmc.LOGERROR)
            return None
            
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                cursor = conn.cursor()
                query = """
                SELECT idEpisode 
                FROM episode_view 
                WHERE idShow = ? AND idSeason = ? AND CAST(c13 AS INTEGER) = ?
                """
                cursor.execute(query, (current_info['idShow'], current_info['idSeason'], current_info['episode_num'] - 1))
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                else:
                    xbmc.log(f'{LOG_PREFIX} Previous episode not found in database', xbmc.LOGDEBUG)
                    return None
                    
        except Exception as e:
            xbmc.log(f'{LOG_PREFIX} Error querying previous episode: {str(e)}', xbmc.LOGERROR)
            return None

    def play_media(self, filepath):
        """播放媒体文件"""
        if filepath:
            # 先停止当前播放
            self.player_control('stop')
            # 等待一小段时间确保播放已停止
            time.sleep(0.5)
            # 播放新文件
            xbmc.executebuiltin('PlayMedia("%s")' % filepath)
        else:
            xbmc.log(f'{LOG_PREFIX} Cannot play media, file does not exist: {filepath}', xbmc.LOGWARNING)

    def player_control(self, command):
        """执行播放器控制命令"""
        xbmc.executebuiltin('PlayerControl(%s)' % command)

    def get_file_extension(self, filepath):
        """获取文件扩展名"""
        if isinstance(filepath, str):
            _, ext = os.path.splitext(filepath.lower())
            return ext
        return ""

    def is_media_file(self, filepath):
        """检查文件是否为媒体文件"""
        # 获取文件扩展名
        if isinstance(filepath, str):
            _, ext = os.path.splitext(filepath.lower())
            media_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.m2ts', '.ts', '.vob', '.iso', '.m3u8', '.mp3', '.flac', '.aac', '.wma', '.wav']
            return ext in media_extensions
        return False

    def extract_episode_number(self, filename):
        """提取E数字格式的集数 - 优先提取SXXEXX格式，其次是EXX格式"""
        if not filename:
            return None
            
        # 解码URL编码的字符（如果有的话）
        decoded_filename = urllib.parse.unquote(os.path.basename(filename))
        
        # 优先匹配 S01E05 这种格式
        se_pattern = r'[Ss](\d+)[Ee](\d+)'
        se_match = re.search(se_pattern, decoded_filename, re.IGNORECASE)
        if se_match:
            try:
                return int(se_match.group(2))  # 返回E后面的数字（集数）
            except ValueError:
                pass
        
        # 然后匹配 E05 或 Episode05 这种格式 - 修复正则表达式
        e_pattern = r'[Ee][Pp]?(\d{1,4})\b'
        e_match = re.search(e_pattern, decoded_filename, re.IGNORECASE)
        if e_match:
            try:
                return int(e_match.group(1))
            except ValueError:
                pass
                
        return None

    def extract_numbers_from_filename(self, filename):
        """从文件名中提取数字序列（排除年份、分辨率等）"""
        if not filename:
            return []
            
        # 解码URL编码的字符（如果有的话）
        decoded_filename = urllib.parse.unquote(os.path.basename(filename))

        
        # 去掉常见年份格式（四位数字，1900-2099）
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        # 去掉常见分辨率格式
        resolution_patterns = [
            r'\b(2160|1080|720)[Pp]?\b',
            r'\b4k\b',
            r'\b[0-9]{3,4}[Xx][0-9]{3,4}\b'
        ]
        # 去掉常见编码格式
        codec_patterns = [
            r'\b[Hh]26[45]\b',
            r'\b[Xx]26[45]\b',
            r'\b[AV]VC\d*\b',
            r'\bDTS\b',
            r'\bAAC\b',
            r'\bAC3\b',
            r'\bDDP?\d*\b'
        ]
        
        # 移除不需要的模式
        clean_name = re.sub(year_pattern, ' ', decoded_filename)
        for pattern in resolution_patterns:
            clean_name = re.sub(pattern, ' ', clean_name)
        for pattern in codec_patterns:
            clean_name = re.sub(pattern, ' ', clean_name)
        
        # 提取剩余的数字序列，但排除SXXEXX中的数字
        # 先移除SXXEXX格式
        clean_name = re.sub(r'[Ss]\d+[Ee]\d+', ' ', clean_name)
        
        # 提取剩余的数字序列
        numbers = []
        matches = re.findall(r'\b\d{1,4}\b', clean_name)  # 限制数字长度防止误匹配，使用单词边界
        for num_str in matches:
            try:
                num = int(num_str)
                # 排除太小的数字（可能是其他编号）以及明显的非集数
                if 0 < num < 1000:  # 一般集数不会超过1000
                    numbers.append(num)
            except ValueError:
                continue
        
        return sorted(list(set(numbers)))  # 去重并排序

    def find_next_episode_file(self, folder_path, current_episode, label, current_file_extension=None):
        """查找下一集文件 - 优先查找E数字格式，其次查找普通数字格式，优先选择相同扩展名的文件"""
        if not folder_path or current_episode is None:
            return None
            
        next_episode = current_episode + 1
        xbmc.log(f'{LOG_PREFIX} Looking for next episode: {next_episode} in {folder_path}', xbmc.LOGDEBUG)
        
        # 获取目录列表
        files = self.list_directory(folder_path)
        
        # 首先查找相同扩展名的媒体文件
        same_ext_files = []
        other_media_files = []
        
        for file in files:
            if self.is_media_file(file):
                file_ext = self.get_file_extension(file)
                if current_file_extension and file_ext == current_file_extension:
                    same_ext_files.append(file)
                else:
                    other_media_files.append(file)
        
        # 优先在相同扩展名的文件中查找
        for file in same_ext_files:
            decoded_file = urllib.parse.unquote(file)
            
            # 检查SXXEXX格式 - 支持各种数字长度，如 S01E87, S01E087, S1E87 等
            se_pattern = r'[Ss]\d+[Ee]%d(?:\D|$)' % next_episode
            # 检查SXXEXX格式，也支持零填充版本（如 S01E087）
            se_zero_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(next_episode).zfill(2)
            # 检查SXXEXX格式，支持更多零填充情况
            se_more_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(next_episode).zfill(3)
            
            # 检查E数字格式（包括Episode形式）- 修复正则表达式以支持多种格式
            e_pattern = r'[Ee][Pp]?%d(?:\D|$)' % next_episode
            e_zero_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(next_episode).zfill(2)
            e_more_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(next_episode).zfill(3)
            
            # 分别检查每个条件
            se_match = re.search(se_pattern, decoded_file, re.IGNORECASE)
            se_zero_match = re.search(se_zero_padded_pattern, decoded_file, re.IGNORECASE)
            se_more_match = re.search(se_more_padded_pattern, decoded_file, re.IGNORECASE)
            e_match = re.search(e_pattern, decoded_file, re.IGNORECASE)
            e_zero_match = re.search(e_zero_padded_pattern, decoded_file, re.IGNORECASE)
            e_more_match = re.search(e_more_padded_pattern, decoded_file, re.IGNORECASE)
            
            # 检查文件是否匹配任一模式
            if (se_match or se_zero_match or se_more_match or 
                e_match or e_zero_match or e_more_match):
                
                filepath = self.build_file_path(folder_path, file)
                
                # 检查文件是否存在
                if self.file_exists(filepath):
                    xbmc.log(f'{LOG_PREFIX} Same extension file exists, returning: {filepath}', xbmc.LOGDEBUG)
                    return filepath
                else:
                    xbmc.log(f'{LOG_PREFIX} Same extension file does not exist: {filepath}', xbmc.LOGDEBUG)
        
        # 如果相同扩展名中没找到，在其他媒体文件中查找
        for file in other_media_files:
            decoded_file = urllib.parse.unquote(file)
            
            # 检查SXXEXX格式
            se_pattern = r'[Ss]\d+[Ee]%d(?:\D|$)' % next_episode
            se_zero_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(next_episode).zfill(2)
            se_more_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(next_episode).zfill(3)
            
            # 检查E数字格式
            e_pattern = r'[Ee][Pp]?%d(?:\D|$)' % next_episode
            e_zero_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(next_episode).zfill(2)
            e_more_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(next_episode).zfill(3)
            
            # 分别检查每个条件
            se_match = re.search(se_pattern, decoded_file, re.IGNORECASE)
            se_zero_match = re.search(se_zero_padded_pattern, decoded_file, re.IGNORECASE)
            se_more_match = re.search(se_more_padded_pattern, decoded_file, re.IGNORECASE)
            e_match = re.search(e_pattern, decoded_file, re.IGNORECASE)
            e_zero_match = re.search(e_zero_padded_pattern, decoded_file, re.IGNORECASE)
            e_more_match = re.search(e_more_padded_pattern, decoded_file, re.IGNORECASE)
            
            # 检查文件是否匹配任一模式
            if (se_match or se_zero_match or se_more_match or 
                e_match or e_zero_match or e_more_match):
                
                filepath = self.build_file_path(folder_path, file)
                
                if self.file_exists(filepath):
                    xbmc.log(f'{LOG_PREFIX} Other extension media file exists, returning: {filepath}', xbmc.LOGDEBUG)
                    return filepath
                else:
                    xbmc.log(f'{LOG_PREFIX} Other extension media file does not exist: {filepath}', xbmc.LOGDEBUG)
        
        # 如果没找到E数字格式，再查找普通数字序列（仍优先考虑相同扩展名）
        current_numbers = self.extract_numbers_from_filename(label)
        for current_num in reversed(current_numbers):  # 从最大的数字开始尝试
            next_num = current_num + 1
            
            # 先检查相同扩展名的文件
            for file in same_ext_files:
                decoded_file = urllib.parse.unquote(file)
                # 使用单词边界确保精确匹配
                number_match = re.search(r'\b%d\b' % next_num, decoded_file)
                
                if number_match:
                    filepath = self.build_file_path(folder_path, file)
                    
                    if self.file_exists(filepath):
                        xbmc.log(f'{LOG_PREFIX} Same extension number-based match found: {filepath}', xbmc.LOGDEBUG)
                        return filepath
                    else:
                        xbmc.log(f'{LOG_PREFIX} Same extension file does not exist: {filepath}', xbmc.LOGDEBUG)
            
            # 再检查其他媒体文件
            for file in other_media_files:
                decoded_file = urllib.parse.unquote(file)
                # 使用单词边界确保精确匹配
                number_match = re.search(r'\b%d\b' % next_num, decoded_file)
                
                if number_match:
                    filepath = self.build_file_path(folder_path, file)
                    
                    if self.file_exists(filepath):
                        xbmc.log(f'{LOG_PREFIX} Other extension number-based match found: {filepath}', xbmc.LOGDEBUG)
                        return filepath
                    else:
                        xbmc.log(f'{LOG_PREFIX} Other extension file does not exist: {filepath}', xbmc.LOGDEBUG)
        
        xbmc.log(f'{LOG_PREFIX} Could not find next episode after {current_episode}', xbmc.LOGDEBUG)
        return None

    def find_previous_episode_file(self, folder_path, current_episode, label, current_file_extension=None):
        """查找上一集文件 - 优先查找E数字格式，其次查找普通数字格式，优先选择相同扩展名的文件"""
        if not folder_path or current_episode is None or current_episode <= 1:
            return None
            
        prev_episode = current_episode - 1
        xbmc.log(f'{LOG_PREFIX} Looking for previous episode: {prev_episode} in {folder_path}', xbmc.LOGDEBUG)
        
        # 获取目录列表
        files = self.list_directory(folder_path)
        
        # 首先查找相同扩展名的媒体文件
        same_ext_files = []
        other_media_files = []
        
        for file in files:
            if self.is_media_file(file):
                file_ext = self.get_file_extension(file)
                if current_file_extension and file_ext == current_file_extension:
                    same_ext_files.append(file)
                else:
                    other_media_files.append(file)
        
        # 优先在相同扩展名的文件中查找
        for file in same_ext_files:
            decoded_file = urllib.parse.unquote(file)
            
            # 检查SXXEXX格式 - 支持各种数字长度，如 S01E86, S01E086, S1E86 等
            se_pattern = r'[Ss]\d+[Ee]%d(?:\D|$)' % prev_episode
            # 检查SXXEXX格式，也支持零填充版本（如 S01E086）
            se_zero_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(prev_episode).zfill(2)
            # 检查SXXEXX格式，支持更多零填充情况
            se_more_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(prev_episode).zfill(3)
            
            # 检查E数字格式（包括Episode形式）- 修复正则表达式
            e_pattern = r'[Ee][Pp]?%d(?:\D|$)' % prev_episode
            e_zero_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(prev_episode).zfill(2)
            e_more_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(prev_episode).zfill(3)
            
            # 分别检查每个条件
            se_match = re.search(se_pattern, decoded_file, re.IGNORECASE)
            se_zero_match = re.search(se_zero_padded_pattern, decoded_file, re.IGNORECASE)
            se_more_match = re.search(se_more_padded_pattern, decoded_file, re.IGNORECASE)
            e_match = re.search(e_pattern, decoded_file, re.IGNORECASE)
            e_zero_match = re.search(e_zero_padded_pattern, decoded_file, re.IGNORECASE)
            e_more_match = re.search(e_more_padded_pattern, decoded_file, re.IGNORECASE)
            
            # 检查文件是否匹配任一模式
            if (se_match or se_zero_match or se_more_match or 
                e_match or e_zero_match or e_more_match):
                
                filepath = self.build_file_path(folder_path, file)
                
                if self.file_exists(filepath):
                    xbmc.log(f'{LOG_PREFIX} Same extension file exists, returning: {filepath}', xbmc.LOGDEBUG)
                    return filepath
                else:
                    xbmc.log(f'{LOG_PREFIX} Same extension file does not exist: {filepath}', xbmc.LOGDEBUG)
        
        # 如果相同扩展名中没找到，在其他媒体文件中查找
        for file in other_media_files:
            decoded_file = urllib.parse.unquote(file)
            
            # 检查SXXEXX格式
            se_pattern = r'[Ss]\d+[Ee]%d(?:\D|$)' % prev_episode
            se_zero_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(prev_episode).zfill(2)
            se_more_padded_pattern = r'[Ss]\d+[Ee]%s(?:\D|$)' % str(prev_episode).zfill(3)
            
            # 检查E数字格式
            e_pattern = r'[Ee][Pp]?%d(?:\D|$)' % prev_episode
            e_zero_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(prev_episode).zfill(2)
            e_more_padded_pattern = r'[Ee][Pp]?%s(?:\D|$)' % str(prev_episode).zfill(3)
            
            # 分别检查每个条件
            se_match = re.search(se_pattern, decoded_file, re.IGNORECASE)
            se_zero_match = re.search(se_zero_padded_pattern, decoded_file, re.IGNORECASE)
            se_more_match = re.search(se_more_padded_pattern, decoded_file, re.IGNORECASE)
            e_match = re.search(e_pattern, decoded_file, re.IGNORECASE)
            e_zero_match = re.search(e_zero_padded_pattern, decoded_file, re.IGNORECASE)
            e_more_match = re.search(e_more_padded_pattern, decoded_file, re.IGNORECASE)
            
            # 检查文件是否匹配任一模式
            if (se_match or se_zero_match or se_more_match or 
                e_match or e_zero_match or e_more_match):
                
                filepath = self.build_file_path(folder_path, file)
                
                if self.file_exists(filepath):
                    xbmc.log(f'{LOG_PREFIX} Other extension media file exists, returning: {filepath}', xbmc.LOGDEBUG)
                    return filepath
                else:
                    xbmc.log(f'{LOG_PREFIX} Other extension media file does not exist: {filepath}', xbmc.LOGDEBUG)
        
        # 如果没找到E数字格式，再查找普通数字序列（仍优先考虑相同扩展名）
        current_numbers = self.extract_numbers_from_filename(label)
        for current_num in reversed(current_numbers):  # 从最大的数字开始尝试
            if current_num <= 1:
                continue
            prev_num = current_num - 1
            
            # 先检查相同扩展名的文件
            for file in same_ext_files:
                decoded_file = urllib.parse.unquote(file)
                # 使用单词边界确保精确匹配
                number_match = re.search(r'\b%d\b' % prev_num, decoded_file)
                
                if number_match:
                    filepath = self.build_file_path(folder_path, file)
                    
                    if self.file_exists(filepath):
                        xbmc.log(f'{LOG_PREFIX} Same extension previous number-based match found: {filepath}', xbmc.LOGDEBUG)
                        return filepath
                    else:
                        xbmc.log(f'{LOG_PREFIX} Same extension file does not exist: {filepath}', xbmc.LOGDEBUG)
            
            # 再检查其他媒体文件
            for file in other_media_files:
                decoded_file = urllib.parse.unquote(file)
                # 使用单词边界确保精确匹配
                number_match = re.search(r'\b%d\b' % prev_num, decoded_file)
                
                if number_match:
                    filepath = self.build_file_path(folder_path, file)
                    
                    if self.file_exists(filepath):
                        xbmc.log(f'{LOG_PREFIX} Other extension previous number-based match found: {filepath}', xbmc.LOGDEBUG)
                        return filepath
                    else:
                        xbmc.log(f'{LOG_PREFIX} Other extension file does not exist: {filepath}', xbmc.LOGDEBUG)
        
        xbmc.log(f'{LOG_PREFIX} Could not find previous episode before {current_episode}', xbmc.LOGDEBUG)
        return None

    def file_exists(self, filepath):
        """检查文件是否存在，支持局域网协议"""
        network_protocols = ['smb://', 'nfs://', 'dav://', 'ftp://', 'ftps://', 'http://', 'https://', 'upnp://', 'plugin://']
        
        is_network_path = any(filepath.startswith(protocol) for protocol in network_protocols)
        
        if is_network_path:
            # 对于网络路径，使用xbmcvfs检查
            try:
                return xbmcvfs.exists(filepath)
            except:
                return False
        else:
            # 本地路径处理
            return os.path.isfile(filepath)

    def build_file_path(self, folder_path, filename):
        """构建文件路径，处理不同协议"""
        network_protocols = ['smb://', 'nfs://', 'dav://', 'ftp://', 'ftps://', 'http://', 'https://', 'upnp://', 'plugin://']
        
        is_network_path = any(folder_path.startswith(protocol) for protocol in network_protocols)
        
        if is_network_path:
            # 对于网络路径，使用URL拼接方式
            if folder_path.endswith('/'):
                return folder_path + filename
            else:
                return folder_path + '/' + filename
        else:
            # 本地路径处理
            return os.path.join(folder_path, filename)

    def list_directory(self, path):
        """列出目录中的文件，支持局域网协议"""
        if not path:
            return []
            
        files = []
        try:
            # 尝试使用xbmcvfs
            dirs, files_list = xbmcvfs.listdir(path)
            files.extend(files_list)
            files.extend(dirs)
        except Exception as e:
            xbmc.log(f'{LOG_PREFIX} xbmcvfs.listdir failed: {str(e)}', xbmc.LOGDEBUG)
            # 如果xbmcvfs失败，使用os模块（仅限本地路径）
            try:
                if not any(path.startswith(protocol) for protocol in ['smb://', 'nfs://', 'dav://', 'ftp://', 'ftps://', 'http://', 'https://', 'upnp://', 'plugin://']):
                    files = os.listdir(path)
                else:
                    # 对于网络路径，返回空列表，因为os无法处理这些路径
                    xbmc.log(f'{LOG_PREFIX} Cannot list network directory with os module: {path}', xbmc.LOGDEBUG)
                    return []
            except Exception as e2:
                xbmc.log(f'{LOG_PREFIX} Cannot list directory: {path} - Error: {str(e2)}', xbmc.LOGERROR)
                return []
        
        return files

    def is_dir(self, path):
        """检查路径是否为目录"""
        try:
            # 尝试使用xbmcvfs
            return xbmcvfs.exists(path) and xbmcvfs.isdir(path)
        except:
            # 对于网络路径，无法可靠判断是否为目录，返回False
            network_protocols = ['smb://', 'nfs://', 'dav://', 'ftp://', 'ftps://', 'http://', 'https://', 'upnp://', 'plugin://']
            if any(path.startswith(protocol) for protocol in network_protocols):
                return False
            # 对于本地路径，使用os模块
            return os.path.isdir(path)

    def format_seconds(self, seconds):
        """将秒数格式化为 HH:MM:SS 或 MM:SS 字符串。"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def parse_time_string(self, time_str):
        """将 "HH:MM:SS" 或 "MM:SS" 格式的字符串解析为总秒数。"""
        if not time_str:
            return 0
        match = re.match(r'^(?:(\d+):)?(\d+):(\d+)$', time_str)
        if not match:
            xbmc.log(f'{LOG_PREFIX} 时间格式无效: \'{time_str}\'', xbmc.LOGERROR)
            return 0
        hours, minutes, seconds = match.groups()
        hours = int(hours) if hours else 0
        return hours * 3600 + int(minutes) * 60 + int(seconds)

    def get_next_episode_info(self, id_show, id_season, current_episode_number):
        """从数据库获取下一集的信息。"""
        db_path = self.get_database_path()
        if not xbmcvfs.exists(db_path):
            xbmc.log(f'{LOG_PREFIX} 数据库文件不存在: {db_path}', xbmc.LOGERROR)
            return None

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 查询下一集的idEpisode
            query = """
            SELECT idEpisode
            FROM episode_view
            WHERE idShow = ? AND idSeason = ? AND CAST(c13 AS INTEGER) = ?
            """
            next_episode_number = current_episode_number + 1
            cursor.execute(query, (id_show, id_season, next_episode_number))
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return result[0]
            else:
                xbmc.log(f'{LOG_PREFIX} 未找到下一集: idShow={id_show}, idSeason={id_season}, EpisodeNumber={next_episode_number}')
                return None
        except Exception as e:
            xbmc.log(f'{LOG_PREFIX} 查询数据库失败: {e}', xbmc.LOGERROR)
            return None

    def play_next_episode_db(self, dbid, id_show, id_season, current_episode_number):
        """使用数据库信息播放下一集。"""
        # 获取下一集信息
        next_dbid = self.get_next_episode_info(id_show, id_season, current_episode_number)
        
        if next_dbid is None:
            xbmc.log(f'{LOG_PREFIX} 未找到下一集，可能是季末或剧终。')
            xbmcgui.Dialog().notification("提示", "当前剧集已全部播放完毕", xbmcgui.NOTIFICATION_INFO, 5000)
            return False
        
        # 先停止当前播放
        self.player_control('stop')
        # 等待一小段时间确保播放已停止
        time.sleep(0.5)
        
        # 使用JSON-RPC播放下一集
        try:
            params = {
                "item": {
                    "episodeid": next_dbid
                }
            }
            result = xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "method": "Player.Open",
                "params": params,
                "id": 1
            }))
            
            response = json.loads(result)
            if "error" in response:
                xbmc.log(f'{LOG_PREFIX} 播放下一集失败: {response["error"]["message"]}', xbmc.LOGERROR)
                return False
            else:
                xbmc.log(f'{LOG_PREFIX} 成功播放下一集 (DBID: {next_dbid})')
                return True
        except Exception as e:
            xbmc.log(f'{LOG_PREFIX} 调用JSON-RPC播放下一集时出错: {e}', xbmc.LOGERROR)
            return False

    def play_next_episode_silent(self):
        """
        静默尝试播放下一集，包含备用方案。
        1. 尝试 PlayerControl(next)
        2. 如果失败，直接进入基于文件名模式的备用方案
        """
        # 获取当前播放的文件名和路径信息
        current_filename = xbmc.getInfoLabel("Player.Filename")
        folder_path = xbmc.getInfoLabel("Player.Folderpath")
        
        if not current_filename or not folder_path:
            xbmc.log(f'{LOG_PREFIX} 无法获取当前播放的文件名或路径，无法执行备用方案。', xbmc.LOGERROR)
            return False
            
        xbmc.log(f'{LOG_PREFIX} 静默尝试播放下一集: CurrentFile=\'{os.path.join(folder_path, current_filename)}\'')
        
        xbmc.executebuiltin("PlayerControl(next)")
        time.sleep(1.5)

        if self.player.isPlaying():
            # 检查是否还在播放当前文件
            new_filename = xbmc.getInfoLabel("Player.Filename")
            new_folder_path = xbmc.getInfoLabel("Player.Folderpath")
            if new_filename != current_filename or new_folder_path != folder_path:
                xbmc.log(f'{LOG_PREFIX} 成功使用 PlayerControl(next) 切换到下一集。')
                return True
            else:
                xbmc.log(f'{LOG_PREFIX} PlayerControl(next) 未切换到新文件，继续尝试备用方案。')
        
        xbmc.log(f'{LOG_PREFIX} PlayerControl(next) 失败，直接进入备用方案。')
        
        # 这里需要实现 get_next_episode_path 函数
        def get_next_episode_path(current_filename, folder_path):
            """
            根据当前文件名和文件夹路径，查找下一集的文件路径。
            采用多级策略，从最精确到最通用。
            """
            xbmc.log(f'{LOG_PREFIX} 尝试查找下一集: CurrentFilename=\'{current_filename}\', FolderPath=\'{folder_path}\'')
            
            # --- 获取当前文件的扩展名 ---
            current_file_ext = self.get_file_extension(current_filename)
            xbmc.log(f'{LOG_PREFIX} 当前文件扩展名: \'{current_file_ext}\'')
            
            # --- 关键修正：分离文件名和扩展名 ---
            # 只对文件名主体部分进行分析，避免匹配到扩展名中的数字
            name_without_ext, ext = os.path.splitext(current_filename)
            xbmc.log(f'{LOG_PREFIX} 分离文件名和扩展名: \'{name_without_ext}\', \'{ext}\'')
            
            # --- 读取文件夹中的所有文件 ---
            dirs, all_files = xbmcvfs.listdir(folder_path)
            
            # 分类文件：相同扩展名的文件和其他媒体文件
            same_ext_files = []
            other_media_files = []
            
            for filename in all_files:
                if self.is_media_file(filename):
                    file_ext = self.get_file_extension(filename)
                    if file_ext == current_file_ext:
                        same_ext_files.append(filename)
                    else:
                        other_media_files.append(filename)
            
            # --- 策略 1: 查找 SxxExx 或 Exx 格式 (最高优先级) ---
            sxxexx_match = re.search(r'S(\d+)E(\d+)', name_without_ext, re.IGNORECASE)
            if sxxexx_match:
                season_num = int(sxxexx_match.group(1))
                episode_num = int(sxxexx_match.group(2))
                next_episode_num = episode_num + 1
                episode_digits = len(sxxexx_match.group(2))
                next_pattern = re.compile(f"S{season_num:02d}E{next_episode_num:0{episode_digits}d}", re.IGNORECASE)
                xbmc.log(f'{LOG_PREFIX} 查找模式: {next_pattern.pattern} (SxxExx格式)')
                
                # 优先在相同扩展名的文件中查找
                for filename in same_ext_files:
                    if next_pattern.search(filename):
                        next_file_path = os.path.join(folder_path, filename)
                        xbmc.log(f'{LOG_PREFIX} 找到下一集 (相同扩展名): {next_file_path}')
                        return next_file_path
                
                # 如果相同扩展名中没找到，在其他媒体文件中查找
                for filename in other_media_files:
                    if next_pattern.search(filename):
                        next_file_path = os.path.join(folder_path, filename)
                        xbmc.log(f'{LOG_PREFIX} 找到下一集 (其他扩展名): {next_file_path}')
                        return next_file_path
                
                xbmc.log(f'{LOG_PREFIX} 在 SxxExx 模式下未找到下一集。')
            else:
                # 修复EXX或EpisodeXX格式的匹配
                exx_match = re.search(r'[Ee][Pp]?(\d+)', name_without_ext, re.IGNORECASE)
                if exx_match:
                    episode_num = int(exx_match.group(1))
                    next_episode_num = episode_num + 1
                    episode_digits = len(exx_match.group(1))
                    # 修复正则表达式：使用更精确的匹配
                    next_pattern = re.compile(rf'[Ee][Pp]?{next_episode_num}(?=\D|$)', re.IGNORECASE)
                    xbmc.log(f'{LOG_PREFIX} 查找模式: {next_pattern.pattern} (Exx/EpisodeXX格式)')
                    
                    # 优先在相同扩展名的文件中查找
                    for filename in same_ext_files:
                        if next_pattern.search(filename):
                            next_file_path = os.path.join(folder_path, filename)
                            xbmc.log(f'{LOG_PREFIX} 找到下一集 (相同扩展名): {next_file_path}')
                            return next_file_path
                    
                    # 如果相同扩展名中没找到，在其他媒体文件中查找
                    for filename in other_media_files:
                        if next_pattern.search(filename):
                            next_file_path = os.path.join(folder_path, filename)
                            xbmc.log(f'{LOG_PREFIX} 找到下一集 (其他扩展名): {next_file_path}')
                            return next_file_path
                    
                    xbmc.log(f'{LOG_PREFIX} 在 Exx/EpisodeXX 模式下未找到下一集。')
                else:
                    next_pattern = None

            if next_pattern:
                # 已在上面处理过了
                pass
            else:
                # --- 策略 2: 智能提取数字串 (兜底策略) ---
                xbmc.log(f'{LOG_PREFIX} 未找到 SxxExx 或 Exx 格式，启动智能数字提取策略。')
                
                exclude_patterns = [
                    re.compile(r'(19|20)\d{2}'),
                    re.compile(r'\b(720|1080|2160|4320)\b'),
                    re.compile(r'\b(H264|H265|x264|x265)\b')
                ]
                
                candidate_patterns = [
                    re.compile(r'(集|EP|e|p)\s*(\d+)', re.IGNORECASE),
                    re.compile(r'\b(\d+)\b')
                ]
                
                current_episode_str = None
                for pattern in candidate_patterns:
                    matches = pattern.findall(name_without_ext) # 使用不含扩展名的文件名
                    for match in matches:
                        num_str = match[1] if isinstance(match, tuple) else match
                        
                        is_excluded = any(excl_pattern.search(num_str) for excl_pattern in exclude_patterns)
                        if not is_excluded:
                            current_episode_str = num_str
                            xbmc.log(f'{LOG_PREFIX} 成功提取到候选集数: \'{current_episode_str}\'')
                            break
                    if current_episode_str:
                        break

                if not current_episode_str:
                    xbmc.log(f'{LOG_PREFIX} 未能从文件名中提取到有效的集数数字串。')
                    return None

                try:
                    current_episode_num = int(current_episode_str)
                    next_episode_num = current_episode_num + 1
                    next_episode_str = f"{next_episode_num:0{len(current_episode_str)}d}"
                    
                    xbmc.log(f'{LOG_PREFIX} 尝试查找包含下一集数字 \'{next_episode_str}\' 的文件。')
                    
                    next_pattern = re.compile(re.escape(next_episode_str))
                    
                    # 优先在相同扩展名的文件中查找
                    for filename in same_ext_files:
                        if next_pattern.search(filename):
                            next_file_path = os.path.join(folder_path, filename)
                            xbmc.log(f'{LOG_PREFIX} 通过智能策略找到下一集 (相同扩展名): {next_file_path}')
                            return next_file_path
                    
                    # 如果相同扩展名中没找到，在其他媒体文件中查找
                    for filename in other_media_files:
                        if next_pattern.search(filename):
                            next_file_path = os.path.join(folder_path, filename)
                            xbmc.log(f'{LOG_PREFIX} 通过智能策略找到下一集 (其他扩展名): {next_file_path}')
                            return next_file_path
                    
                    xbmc.log(f'{LOG_PREFIX} 在文件夹中未找到包含数字 \'{next_episode_str}\' 的文件。')

                except ValueError:
                    xbmc.log(f'{LOG_PREFIX} 提取的数字串 \'{current_episode_str}\' 无法转换为整数。')

            return None

        next_episode_path = get_next_episode_path(current_filename, folder_path)
        
        if next_episode_path:
            # 先停止当前播放
            self.player_control('stop')
            # 等待一小段时间确保播放已停止
            time.sleep(0.5)
            # 播放新文件
            xbmc.log(f'{LOG_PREFIX} 使用备用方案播放: {next_episode_path}')
            self.player.play(next_episode_path)
            return True
        else:
            xbmc.log(f'{LOG_PREFIX} 所有尝试都失败，无法播放下一集。')
            xbmcgui.Dialog().notification("提示", "无法找到或播放下一集", xbmcgui.NOTIFICATION_INFO, 5000)
            return False

    def run_next(self):
        """执行下一集操作"""
        # 检查当前内容类型
        is_episodes_content = xbmc.getCondVisibility('VideoPlayer.Content(Episodes)')
        xbmc.log(f'{LOG_PREFIX} VideoPlayer.Content(Episodes) condition: {is_episodes_content}', xbmc.LOGDEBUG)
        
        if is_episodes_content:
            # 情况1：如果是剧集内容，使用数据库查询
            dbid = xbmc.getInfoLabel('VideoPlayer.DBID')
            if not dbid or dbid == '':
                xbmc.log(f'{LOG_PREFIX} No DBID found, falling back to file system method', xbmc.LOGDEBUG)
                self.run_next_filesystem()
                return
                
            try:
                dbid = int(dbid)
            except ValueError:
                xbmc.log(f'{LOG_PREFIX} Invalid DBID format: {dbid}', xbmc.LOGERROR)
                self.run_next_filesystem()
                return
                
            # 查询当前剧集信息
            current_info = self.query_episode_by_dbid(dbid)
            if not current_info:
                xbmc.log(f'{LOG_PREFIX} Could not find episode info for DBID {dbid}, falling back to file system method', xbmc.LOGDEBUG)
                self.run_next_filesystem()
                return
                
            # 查找下一集
            next_episode_id = self.find_next_episode_by_db(current_info)
            if next_episode_id:
                # 播放下一集（已在play_media_by_episode_id中先停止再播放）
                result = self.play_media_by_episode_id(next_episode_id)
                xbmc.log(f'{LOG_PREFIX} Played next episode with ID {next_episode_id}, result: {result}', xbmc.LOGDEBUG)
                # 立即退出，防止影响其他脚本
                sys.exit(0)
            else:
                # 没有下一集，显示通知
                xbmcgui.Dialog().notification(
                    "提示",
                    "当前剧集已全部播放完毕",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                xbmc.log(f'{LOG_PREFIX} No next episode found in database', xbmc.LOGDEBUG)
                # 即使没有找到下一集也要退出，避免后续执行
                sys.exit(0)
        else:
            # 情况2：如果不是剧集内容，使用文件系统方法
            self.run_next_filesystem()

    def run_next_filesystem(self):
        """执行下一集操作（文件系统方法）"""
        player_type = self.get_player_type()
        
        if player_type == 'audio':
            xbmc.log(f'{LOG_PREFIX} Audio playing, using default next', xbmc.LOGDEBUG)
            self.player_control('next')
            # 音频播放也需要立即退出
            sys.exit(0)
            return

        if player_type != 'video':
            # 不是视频也不是音频，直接返回
            xbmc.log(f'{LOG_PREFIX} Unknown player type: {player_type}, using default next', xbmc.LOGDEBUG)
            self.player_control('next')
            # 即使未知类型也要退出
            sys.exit(0)
            return

        current_file = self.get_current_filename()
        current_label = self.get_current_label()
        current_file_extension = self.get_file_extension(current_file)
        
        xbmc.log(f'{LOG_PREFIX} Current file: {current_file}', xbmc.LOGDEBUG)
        xbmc.log(f'{LOG_PREFIX} Current label: {current_label}', xbmc.LOGDEBUG)
        xbmc.log(f'{LOG_PREFIX} Current file extension: {current_file_extension}', xbmc.LOGDEBUG)
        
        # 检查是否包含E数字格式
        episode_num = self.extract_episode_number(current_file)
        if episode_num is not None:
            xbmc.log(f'{LOG_PREFIX} Found episode number: {episode_num}', xbmc.LOGDEBUG)
            # 包含E数字格式，停止当前播放并查找下一集
            folder_path = self.get_current_folder_path()
            if folder_path:
                next_file = self.find_next_episode_file(folder_path, episode_num, current_label, current_file_extension)
                
                if next_file:
                    # 播放下一集（已在play_media中先停止再播放）
                    self.play_media(next_file)
                    xbmc.log(f'{LOG_PREFIX} Successfully played next episode: {next_file}', xbmc.LOGDEBUG)
                    # 播放成功后立即退出
                    sys.exit(0)
                else:
                    # 如果没找到下一集，继续使用默认行为
                    xbmc.log(f'{LOG_PREFIX} Could not find next episode, using default next', xbmc.LOGDEBUG)
                    self.player_control('next')
                    # 执行完后立即退出
                    sys.exit(0)
            else:
                xbmc.log(f'{LOG_PREFIX} Could not determine folder path, using default next', xbmc.LOGDEBUG)
                self.player_control('next')
                # 执行完后立即退出
                sys.exit(0)
        else:
            # 不包含E数字格式，直接执行默认行为
            xbmc.log(f'{LOG_PREFIX} No episode number found, using default next', xbmc.LOGDEBUG)
            self.player_control('next')
            # 执行完后立即退出
            sys.exit(0)

    def run_next_with_end_logic(self):
        """执行下一集操作，使用tvjump脚本的end逻辑"""
        xbmc.log(f'{LOG_PREFIX} 运行带有end逻辑的下一集功能', xbmc.LOGDEBUG)
        
        if not xbmc.getCondVisibility('VideoPlayer.Content(Episodes)'):
            # 非剧集内容，使用静默播放下一集
            success = self.play_next_episode_silent()
            if not success:
                xbmc.log(f'{LOG_PREFIX} 静默播放下一集失败，使用默认播放控制', xbmc.LOGDEBUG)
                self.player_control('next')
            sys.exit(0)
        else:
            # 剧集内容，使用数据库信息
            current_dbid_str = xbmc.getInfoLabel("VideoPlayer.DBID")
            current_dbid = int(current_dbid_str) if current_dbid_str.isdigit() else None
            
            if not current_dbid:
                xbmc.log(f'{LOG_PREFIX} 无法获取有效的DBID，使用静默播放下一集', xbmc.LOGDEBUG)
                success = self.play_next_episode_silent()
                if not success:
                    self.player_control('next')
                sys.exit(0)
            
            # 获取当前剧集信息
            current_info = self.query_episode_by_dbid(current_dbid)
            if not current_info:
                xbmc.log(f'{LOG_PREFIX} 无法获取剧集信息，使用静默播放下一集', xbmc.LOGDEBUG)
                success = self.play_next_episode_silent()
                if not success:
                    self.player_control('next')
                sys.exit(0)
            
            # 使用数据库信息播放下一集
            success = self.play_next_episode_db(current_dbid, current_info['idShow'], current_info['idSeason'], current_info['episode_num'])
            if not success:
                xbmc.log(f'{LOG_PREFIX} 使用数据库信息播放下一集失败，使用静默播放下一集', xbmc.LOGDEBUG)
                success = self.play_next_episode_silent()
                if not success:
                    self.player_control('next')
            sys.exit(0)

    def run_previous(self):
        """执行上一集操作"""
        # 检查当前内容类型
        is_episodes_content = xbmc.getCondVisibility('VideoPlayer.Content(Episodes)')
        xbmc.log(f'{LOG_PREFIX} VideoPlayer.Content(Episodes) condition: {is_episodes_content}', xbmc.LOGDEBUG)
        
        if is_episodes_content:
            # 情况1：如果是剧集内容，使用数据库查询
            dbid = xbmc.getInfoLabel('VideoPlayer.DBID')
            if not dbid or dbid == '':
                xbmc.log(f'{LOG_PREFIX} No DBID found, falling back to file system method', xbmc.LOGDEBUG)
                self.run_previous_filesystem()
                return
                
            try:
                dbid = int(dbid)
            except ValueError:
                xbmc.log(f'{LOG_PREFIX} Invalid DBID format: {dbid}', xbmc.LOGERROR)
                self.run_previous_filesystem()
                return
                
            # 查询当前剧集信息
            current_info = self.query_episode_by_dbid(dbid)
            if not current_info:
                xbmc.log(f'{LOG_PREFIX} Could not find episode info for DBID {dbid}, falling back to file system method', xbmc.LOGDEBUG)
                self.run_previous_filesystem()
                return
                
            # 查找上一集
            prev_episode_id = self.find_prev_episode_by_db(current_info)
            if prev_episode_id:
                # 播放上一集（已在play_media_by_episode_id中先停止再播放）
                result = self.play_media_by_episode_id(prev_episode_id)
                xbmc.log(f'{LOG_PREFIX} Played previous episode with ID {prev_episode_id}, result: {result}', xbmc.LOGDEBUG)
                # 立即退出，防止影响其他脚本
                sys.exit(0)
            else:
                # 没有上一集，显示通知
                xbmcgui.Dialog().notification(
                    "提示",
                    "未找到上一集",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                xbmc.log(f'{LOG_PREFIX} No previous episode found in database', xbmc.LOGDEBUG)
                # 即使没有找到上一集也要退出
                sys.exit(0)
        else:
            # 情况2：如果不是剧集内容，使用文件系统方法
            self.run_previous_filesystem()

    def run_previous_filesystem(self):
        """执行上一集操作（文件系统方法）"""
        player_type = self.get_player_type()
        
        if player_type == 'audio':
            xbmc.log(f'{LOG_PREFIX} Audio playing, using default previous', xbmc.LOGDEBUG)
            self.player_control('previous')
            # 音频播放也需要立即退出
            sys.exit(0)
            return

        if player_type != 'video':
            # 不是视频也不是音频，直接返回
            xbmc.log(f'{LOG_PREFIX} Unknown player type: {player_type}, using default previous', xbmc.LOGDEBUG)
            self.player_control('previous')
            # 即使未知类型也要退出
            sys.exit(0)
            return

        current_file = self.get_current_filename()
        current_label = self.get_current_label()
        current_file_extension = self.get_file_extension(current_file)
        
        xbmc.log(f'{LOG_PREFIX} Current file: {current_file}', xbmc.LOGDEBUG)
        xbmc.log(f'{LOG_PREFIX} Current label: {current_label}', xbmc.LOGDEBUG)
        xbmc.log(f'{LOG_PREFIX} Current file extension: {current_file_extension}', xbmc.LOGDEBUG)
        
        # 检查是否包含E数字格式
        episode_num = self.extract_episode_number(current_file)
        if episode_num is not None and episode_num > 1:
            xbmc.log(f'{LOG_PREFIX} Found episode number: {episode_num}', xbmc.LOGDEBUG)
            # 包含E数字格式，停止当前播放并查找上一集
            folder_path = self.get_current_folder_path()
            if folder_path:
                prev_file = self.find_previous_episode_file(folder_path, episode_num, current_label, current_file_extension)
                
                if prev_file:
                    # 播放上一集（已在play_media中先停止再播放）
                    self.play_media(prev_file)
                    xbmc.log(f'{LOG_PREFIX} Successfully played previous episode: {prev_file}', xbmc.LOGDEBUG)
                    # 播放成功后立即退出
                    sys.exit(0)
                else:
                    # 如果没找到上一集，继续使用默认行为
                    xbmc.log(f'{LOG_PREFIX} Could not find previous episode, using default previous', xbmc.LOGDEBUG)
                    self.player_control('previous')
                    # 执行完后立即退出
                    sys.exit(0)
            else:
                xbmc.log(f'{LOG_PREFIX} Could not determine folder path, using default previous', xbmc.LOGDEBUG)
                self.player_control('previous')
                # 执行完后立即退出
                sys.exit(0)
        else:
            # 不包含E数字格式或已是第一集，直接执行默认行为
            xbmc.log(f'{LOG_PREFIX} No episode number found or first episode, using default previous', xbmc.LOGDEBUG)
            self.player_control('previous')
            # 执行完后立即退出
            sys.exit(0)

def main():
    if len(sys.argv) < 2:
        xbmc.log(f'{LOG_PREFIX} No argument provided', xbmc.LOGERROR)
        # 即使参数不足也退出
        sys.exit(1)
        return

    action = sys.argv[1].lower()
    xbmc.log(f'{LOG_PREFIX} Running with action: {action}', xbmc.LOGDEBUG)

    player = NextItemPlayer()
    
    if action == 'next':
        player.run_next_with_end_logic()  # 使用tvjump的end逻辑
    elif action == 'previous':
        player.run_previous()
    else:
        xbmc.log(f'{LOG_PREFIX} Invalid argument: {action}', xbmc.LOGERROR)
        # 即使参数无效也退出
        sys.exit(1)

if __name__ == '__main__':
    main()