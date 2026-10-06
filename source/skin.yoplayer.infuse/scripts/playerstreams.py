# Minsk-R2
# -*- coding: utf-8 -*-
# Module: default
# Author: jurialmunkey
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html
from xbmcgui import ListItem
from jurialmunkey.jsnrpc import get_jsonrpc
from jurialmunkey.litems import ContainerDirectory
import xbmc


PLAYERSTREAMS = {
    'audio': {'key': 'audiostreams', 'cur': 'currentaudiostream'},
    'subtitle': {'key': 'subtitles', 'cur': 'currentsubtitle'}
}


def get_language_sort_priority(language, is_default=False, stream_type='audio'):
    """获取语言的排序优先级"""
    language = language.upper() if language else ""
    
    # 默认音轨优先级最高（适用于所有流类型）
    if is_default:
        return 0
    
    if stream_type == 'subtitle':
        if "CHI" in language or "ZH" in language or "中文" in language or "CHINESE" in language:
            return 1  # 中文第一优先级
        elif "ENG" in language or "EN" in language or "ENGLISH" in language:
            return 2  # 英文第二优先级
        else:
            return 3  # 其他语言最低优先级
    else:  # 音轨或其他类型
        if "CHI" in language or "ZH" in language or "中文" in language or "CHINESE" in language:
            return 1  # 中文第二优先级
        elif "ENG" in language or "EN" in language or "ENGLISH" in language:
            return 2  # 英文第三优先级
        else:
            return 3  # 其他语言最低优先级


def sort_streams_by_language(streams, default_index, stream_type='audio'):
    """按语言优先级排序流"""
    def sort_key(stream):
        language = stream.get('language', '')
        # 检查是否为默认音轨（这里假设有一个default属性来标识默认音轨）
        # 在实际应用中，这可能需要从流信息中获取默认音轨的标识
        is_default = stream.get('index') == default_index
        
        # 优先按语言优先级排序，然后按名称排序
        return (get_language_sort_priority(language, is_default, stream_type), 
                0 if is_default else 1,  # 默认音轨在同语言优先级中排最前
                stream.get('name', ''))
    
    return sorted(streams, key=sort_key)


class ListGetPlayerStreams(ContainerDirectory):
    def get_directory(self, stream_type=None, **kwargs):

        def _get_items(stream_type):
            def make_item(i):
                label = i.get("language", "UND")
                label2 = i.get("name", "")
                path = f'plugin://script.skinvariables/?info=set_player_streams&stream_index={i.get("index")}&stream_type={stream_type}'

                infoproperties = {}
                for k, v in i.items():
                    if v:  # 非空判断
                        if k == "bitrate":
                            try:
                                infoproperties[k] = f'{int(float(v) / 1000)}'  # 转 kbps
                            except (ValueError, TypeError):
                                infoproperties[k] = f'{v}'
                        else:
                            infoproperties[k] = f'{v}'

                if cur_strm == i.get('index'):
                    infoproperties['iscurrent'] = 'true'
                infoproperties['isfolder'] = 'false'

                listitem = ListItem(label=label, label2=label2, path=path, offscreen=True)
                listitem.setProperties(infoproperties)
                return listitem

            ps_def = PLAYERSTREAMS.get(stream_type)
            if not ps_def:
                return []

            method = "Player.GetProperties"
            params = {"playerid": 1, "properties": [ps_def['key'], ps_def['cur']]}
            response = get_jsonrpc(method, params) or {}
            response = response.get('result', {})
            all_strm = response.get(ps_def['key']) or []
            if not all_strm:
                return []

            cur_strm = response.get(ps_def['cur'], {}).get('index', 0)
            
            # 获取默认音轨索引 - 通常默认音轨是第一个可用音轨或有特殊标识的音轨
            # 这里我们假设默认音轨是系统首选的音轨，可能需要根据实际情况调整
            default_strm = self._get_default_stream_index(all_strm, stream_type)
            
            all_strm = sort_streams_by_language(all_strm, default_strm, stream_type)
            
            return [make_item(i) for i in all_strm if i]

        if not stream_type:
            return

        items = [
            (li.getPath(), li, li.getProperty('isfolder').lower() == 'true', )
            for li in _get_items(stream_type) if li]

        self.add_items(items)

    def _get_default_stream_index(self, streams, stream_type):
        """
        获取默认音轨索引
        在实际实现中，这可能需要通过其他API调用来确定默认音轨
        这里提供几种可能的实现方式：
        """
        if not streams:
            return None
            
        # 方案1: 尝试查找标记为默认的音轨
        for stream in streams:
            if stream.get('isdefault', False):  # 假设有isdefault字段
                return stream.get('index')
        
        # 方案2: 对于音频，返回第一个中文音轨
        if stream_type == 'audio':
            for stream in streams:
                lang = stream.get('language', '').upper()
                if "CHI" in lang or "ZH" in lang or "中文" in lang or "CHINESE" in lang:
                    return stream.get('index')
        
        # 方案3: 返回第一个英文音轨
        for stream in streams:
            lang = stream.get('language', '').upper()
            if "ENG" in lang or "EN" in lang or "ENGLISH" in lang:
                return stream.get('index')
        
        # 方案4: 返回第一个音轨
        return streams[0].get('index')


class ListSetPlayerStreams(ContainerDirectory):
    def get_directory(self, stream_type=None, stream_index=None, **kwargs):
        if not stream_type or stream_index is None:
            return
        if stream_type == 'audio':
            from resources.lib.method import set_player_audiostream
            set_player_audiostream(stream_index)
            return
        if stream_type == 'subtitle':
            from resources.lib.method import set_player_subtitle
            set_player_subtitle(stream_index)
            return
