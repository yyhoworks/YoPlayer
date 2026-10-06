# -*- coding: utf-8 -*-
"""
KODI播放历史记录脚本
此脚本可以从JSON文件读取播放记录，并在KODI中显示历史列表
使用ActivateWindow打开视频库窗口显示历史记录
"""
import sys
import json
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

def get_script_params():
    """获取脚本参数"""
    script_params = sys.argv[1:]
    params = {}
    for param in script_params:
        if '=' in param:
            key, value = param.split('=', 1)
            params[key] = value
    return params

def get_json_file_path():
    """获取播放记录JSON文件路径"""
    # 直接到special://profile/addon_data/skin.yoplayer.infuse/路径获取lastPlayed.json文件
    txtpath = xbmcvfs.translatePath("special://profile/addon_data/skin.yoplayer.infuse/")
    if not xbmcvfs.exists(txtpath):
        xbmcvfs.mkdirs(txtpath)
    
    json_file = txtpath + "lastPlayed.json"
    return json_file

def load_history_records(json_file):
    """加载播放历史记录 - 支持多种格式和容错处理"""
    if not xbmcvfs.exists(json_file):
        xbmc.log("播放历史文件不存在: " + json_file, xbmc.LOGINFO)
        return []
    
    try:
        f = xbmcvfs.File(json_file)
        content = f.read()
        f.close()
        
        if not content:
            xbmc.log("播放历史文件为空", xbmc.LOGINFO)
            return []
        
        # 尝试标准JSON解析
        try:
            records = json.loads(content)
            if isinstance(records, list):
                xbmc.log(f"成功加载 {len(records)} 条播放历史记录 (标准JSON格式)", xbmc.LOGINFO)
                return records
        except:
            pass
        
        # 如果标准解析失败，尝试逐行解析（支持多行JSON对象）
        lines = content.split('\n')
        records = []
        current_obj = ''
        brace_count = 0
        
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
                
            # 计算大括号数量，用于识别完整的JSON对象
            for char in stripped_line:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
            
            current_obj += stripped_line
            
            # 当大括号平衡时，尝试解析这个对象
            if brace_count == 0 and current_obj:
                try:
                    obj = json.loads(current_obj)
                    if isinstance(obj, dict):
                        records.append(obj)
                    current_obj = ''
                except:
                    # 如果解析失败，继续累加字符
                    current_obj += '\n'
            else:
                current_obj += '\n'
        
        # 如果还有剩余内容，尝试解析
        if current_obj.strip():
            try:
                obj = json.loads(current_obj.strip())
                if isinstance(obj, dict):
                    records.append(obj)
            except:
                pass
        
        # 再次尝试：使用正则表达式提取JSON对象
        if not records:
            import re
            # 查找所有可能的JSON对象
            pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'  # 简单的嵌套匹配
            matches = re.findall(pattern, content.replace('\n', '').replace('\r', ''))
            
            for match in matches:
                try:
                    obj = json.loads(match)
                    if isinstance(obj, dict):
                        records.append(obj)
                except:
                    # 尝试修复常见的JSON问题
                    fixed_match = match
                    # 替换单引号为双引号（注意：仅在合适的情况下）
                    # 修复常见的转义问题
                    try:
                        obj = json.loads(fixed_match)
                        if isinstance(obj, dict):
                            records.append(obj)
                    except:
                        pass
        
        xbmc.log(f"成功加载 {len(records)} 条播放历史记录 (兼容模式)", xbmc.LOGINFO)
        return records
        
    except Exception as e:
        xbmc.log(f"加载播放历史失败: {str(e)}", xbmc.LOGERROR)
        return []

def get_media_category(media_type, show_title):
    """获取媒体类别显示文本"""
    if media_type == 'movie':
        return '影'
    elif media_type == 'episode':
        return '剧'
    elif show_title:  # 如果有剧集名称，即使类型不是episode也认为是剧集
        return '剧'
    else:
        return '非'


def visible_history(records):
    if xbmc.getSkinDir() != 'skin.yoplayer.infuse':return records
    try:
        from infuse import import_actions
        import_actions()
        from provider import filter_legacy_history
        return filter_legacy_history(records)
    except (ImportError, OSError, ValueError, RuntimeError):
        xbmc.log('YoPlayer: history membership unavailable; original records retained', xbmc.LOGWARNING)
        return records

def activate_history_window():
    """激活包含播放历史的视频窗口"""
    # 创建一个临时播放列表来存储历史记录
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()  # 清空现有播放列表
    
    # 加载播放历史
    json_file = get_json_file_path()
    records = visible_history(load_history_records(json_file))
    
    if not records:
        xbmcgui.Dialog().ok("播放历史", "没有找到播放历史记录。")
        return
    
    # 为每条记录创建列表项并添加到播放列表
    for i, record in enumerate(records):
        # 确保记录是字典类型
        if not isinstance(record, dict):
            xbmc.log(f"跳过非字典类型的记录 #{i}: {type(record)}", xbmc.LOGINFO)
            continue
            
        # 按照指定格式构建显示标题: [COLOR YELLOW][月-日 小时:分钟][/COLOR][COLOR green][类别(电影/剧集/视频)][/COLOR]剧集名称 季数&集数 文件名
        date_part = record.get('date', '')
        time_part = record.get('time', '')
        
        # 提取月份和日期
        month_day = ""
        if date_part:
            # 假设日期格式为 YYYY-MM-DD
            parts = date_part.split('-')
            if len(parts) >= 3:
                month_day = f"{parts[1]}-{parts[2]}"
        
        # 组合时间部分
        formatted_time = ""
        if time_part:
            # 假设时间格式为 HH:MM:SS
            time_parts = time_part.split(':')
            if len(time_parts) >= 2:
                formatted_time = f"{time_parts[0]}:{time_parts[1]}"
        
        # 构建标题部分
        title_part = record.get('title', 'Unknown')
        
        # 获取媒体类型、季、集信息
        media_type = record.get('type', 'video').lower()
        season = record.get('season', '')
        episode = record.get('episode', '')
        
        # 获取剧集名称（如果是电视剧的话）
        show_title = record.get('show', record.get('showtitle', record.get('tvshowtitle', '')))
        
        # 构建季数和集数信息
        season_episode_info = ""
        if media_type == 'episode' and show_title:
            if season and episode:
                season_episode_info = f" {int(season)}x{int(episode)} "
            elif season:
                season_episode_info = f" {int(season)} "
            elif episode:
                season_episode_info = f" {int(episode)} "
            else:
                season_episode_info = " "
        else:
            season_episode_info = " "
        
        # 获取媒体类别
        category = get_media_category(media_type, show_title)
        
        # 构建最终标题
        # [COLOR YELLOW][月-日 小时:分钟][/COLOR][COLOR green][类别(电影/剧集/视频)][/COLOR]剧集名称 季数&集数 文件名
        time_part_colored = f"[COLOR yellow][{month_day} {formatted_time}][/COLOR]"
        
        # 设置不同类别的颜色
        if category == '影':  # 电影
            category_part_colored = f"[COLOR green]{{{category}}}[/COLOR]"
        elif category == '剧':  # 剧集
            category_part_colored = f"[COLOR orange]{{{category}}}[/COLOR]"
        else:  # 视频 -> 非
            category_part_colored = f"[COLOR white]{{{category}}}[/COLOR]"  # 使用white作为普通色
        
        if show_title:
            final_title = f"{time_part_colored}{category_part_colored}{show_title}{season_episode_info}{title_part}"
        else:
            final_title = f"{time_part_colored}{category_part_colored}{title_part}"
        
        # 创建列表项
        li = xbmcgui.ListItem(label=final_title)
        
        # 使用新的InfoTagVideo API设置视频信息
        info_tag = li.getVideoInfoTag()
        info_tag.setTitle(final_title)
        info_tag.setOriginalTitle(final_title)
        if record.get('year'):
            info_tag.setYear(int(record.get('year')))
        if record.get('type'):
            info_tag.setMediaType(record.get('type', 'video'))
        if record.get('plot'):
            info_tag.setPlot(f"来源: {record.get('source', 'Unknown')}\n类型: {record.get('type', 'Unknown')}\n日期: {record.get('date', '')} {record.get('time', '')}")
        if record.get('date') and record.get('time'):
            info_tag.setLastPlayed(f"{record.get('date')} {record.get('time')}")
        if season and media_type == 'episode':
            info_tag.setSeason(int(season))
        if episode and media_type == 'episode':
            info_tag.setEpisode(int(episode))
        if show_title:
            info_tag.setTvShowTitle(show_title)
        
        # 设置恢复点 - 确保参数为数字类型
        resume_time_str = record.get('resume_time', 0)
        total_time_str = record.get('total_time', 0)
        
        # 转换为浮点数，如果转换失败则使用默认值0
        try:
            resume_time = float(resume_time_str) if resume_time_str else 0.0
        except (ValueError, TypeError):
            resume_time = 0.0
            
        try:
            total_time = float(total_time_str) if total_time_str else 0.0
        except (ValueError, TypeError):
            total_time = 0.0
        
        if resume_time or total_time:
            info_tag.setResumePoint(resume_time, total_time)
        
        # 设置艺术资源 - 优化处理null值的情况
        art_dict = {}
        
        # 处理海报和缩略图
        thumbnail = record.get('thumbnail', '')
        if thumbnail and thumbnail != 'null' and isinstance(thumbnail, str) and thumbnail.strip():
            art_dict["poster"] = thumbnail.strip()
            art_dict["thumbnail"] = thumbnail.strip()
        
        # 处理背景图
        fanart = record.get('fanart', '')
        if fanart and fanart != 'null' and isinstance(fanart, str) and fanart.strip():
            art_dict["fanart"] = fanart.strip()
        
        # 处理图标
        icon = record.get('icon', '')
        if icon and icon != 'null' and isinstance(icon, str) and icon.strip():
            art_dict["icon"] = icon.strip()
        
        # 如果art_dict不为空才设置艺术资源
        if art_dict:
            li.setArt(art_dict)
        
        # 设置为可播放
        li.setProperty('IsPlayable', 'true')
        
        # 获取实际播放路径
        play_url = record.get('file', '')
        if not play_url:
            play_url = record.get('video', '')
        
        if play_url:
            # 添加上下文菜单
            commands = []
            
            # 删除记录命令
            delete_cmd = (
                "删除记录",
                f"RunScript(special://skin/scripts/delethistory.py)"
            )
            commands.append(delete_cmd)
            
            # 重新播放命令
            play_cmd = (
               "打开所在文件夹",
                f"RunScript(special://skin/scripts/episodelist.py)"
            )
            commands.append(play_cmd)
            
            li.addContextMenuItems(commands)
            
            # 添加到播放列表
            playlist.add(url=play_url, listitem=li)
    
    # 首先激活视频窗口
    xbmc.executebuiltin('ActivateWindow(Videos,playlistvideo://,return)')
    
    # 延时0.5秒让窗口加载
    xbmc.sleep(100)
    
    # 刷新容器
    xbmc.executebuiltin('Container.Refresh')
    
    # 设置排序为按标题排序（名称）
    xbmc.executebuiltin('Container.SetSortMethod(1)')  # 1 = Sort by Title
    xbmc.sleep(500)
    # 使用Container.SortOrder检测当前排序方式
    current_sort_order = xbmc.getInfoLabel('Container.SortOrder')
    
    # 如果当前排序不是降序，则设置为降序
    # Container.SortOrder返回"Ascending"或"Descending"
    if current_sort_order.lower() != '降序':
        xbmc.executebuiltin('Container.SetSortDirection(-1)')  # 设置为降序

def delete_record(index):
    """删除指定索引的记录"""
    json_file = get_json_file_path()
    records = load_history_records(json_file)
    
    if 0 <= index < len(records):
        deleted_record = records.pop(index)
        xbmc.log(f"删除播放记录: {deleted_record.get('title', 'Unknown')}", xbmc.LOGINFO)
        
        # 保存更新后的记录
        try:
            f = xbmcvfs.File(json_file, 'w')
            json.dump(records, f)
            f.close()
            xbmcgui.Dialog().notification(
                "删除成功", 
                f"已删除: {deleted_record.get('title', 'Unknown')}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
        except Exception as e:
            xbmc.log(f"保存播放历史失败: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("错误", "无法保存更改。")
    else:
        xbmcgui.Dialog().ok("错误", "无效的记录索引。")

def main():
    """主函数"""
    # 检查播放历史文件是否存在，只有存在时才设置皮肤变量
    json_file = get_json_file_path()
    records = load_history_records(json_file)
    
    if records:  # 只有当存在播放历史记录时才设置皮肤变量
        xbmc.executebuiltin('Skin.SetString(plhistory,1)')
        xbmc.log("播放历史文件存在，已设置皮肤变量 plhistory=1", xbmc.LOGINFO)
    else:
        xbmc.log("播放历史文件不存在或为空，跳过设置皮肤变量 plhistory", xbmc.LOGINFO)
    
    xbmc.log("启动播放历史脚本", xbmc.LOGINFO)
    
    # 解析参数
    params = get_script_params()
    action = params.get('action', 'show')
    index = params.get('index', None)
    
    if action == 'delete' and index is not None:
        try:
            delete_record(int(index))
        except ValueError:
            xbmc.log("无效的索引值", xbmc.LOGERROR)
    elif action == 'show' or action is None:
        # 激活包含播放历史的视频窗口
        activate_history_window()
    else:
        xbmc.log(f"未知操作: {action}", xbmc.LOGWARNING)

# 确保脚本可以独立运行
if __name__ == "__main__":
    main()
