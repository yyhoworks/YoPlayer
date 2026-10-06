import xbmc
import xbmcvfs
import json
import time
import re

def get_listitem_property(property_name):
    """获取当前列表项属性"""
    return xbmc.getInfoLabel(f'ListItem.{property_name}')

def extract_datetime_info(label):
    """从标签中提取日期时间信息"""
    # 匹配 [月-日 小时:分钟] 格式的正则表达式
    pattern = r'\[(\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})\]'
    match = re.search(pattern, label)
    if match:
        date_part = match.group(1)  # 月-日
        time_part = match.group(2)  # 小时:分钟
        return date_part, time_part
    return None, None

def run_script(script_path):
    """运行指定脚本"""
    xbmc.executebuiltin(f'RunScript({script_path})')

def main():
    try:
        # 获取ListItem.FileNameAndPath的值
        file_path = get_listitem_property('FileNameAndPath')
        if not file_path:
            xbmc.log('Error: Could not get FileNameAndPath property', xbmc.LOGERROR)
            return

        # 获取ListItem.label的值
        label = get_listitem_property('Label')
        
        # 翻译特殊路径
        json_file_path = xbmcvfs.translatePath('special://profile/addon_data/skin.yoplayer.infuse/lastPlayed.json')
        
        # 读取JSON文件
        with xbmcvfs.File(json_file_path, 'r') as file:
            content = file.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            data = json.loads(content)

        # 查找包含FileNameAndPath的条目
        matching_entries = []
        for entry in data:
            if 'file' in entry and entry['file'] == file_path:
                matching_entries.append(entry)

        # 如果找到不止一个条目，根据label进一步筛选
        if len(matching_entries) > 1 and label:
            date_part, time_part = extract_datetime_info(label)
            
            if date_part:
                # 筛选日期匹配的条目
                date_matching_entries = []
                for entry in matching_entries:
                    if 'date' in entry and date_part in entry['date']:
                        date_matching_entries.append(entry)
                
                matching_entries = date_matching_entries
                
                # 如果仍有多个匹配项，根据时间进一步筛选
                if len(matching_entries) > 1 and time_part:
                    time_matching_entries = []
                    for entry in matching_entries:
                        if 'time' in entry and time_part in entry['time']:
                            time_matching_entries.append(entry)
                    
                    matching_entries = time_matching_entries

        # 删除匹配的条目
        if matching_entries:
            for entry in matching_entries:
                if entry in data:
                    data.remove(entry)
                    xbmc.log(f'Deleted entry: {entry}', xbmc.LOGINFO)

            # 写回JSON文件
            with xbmcvfs.File(json_file_path, 'w') as file:
                json_content = json.dumps(data, ensure_ascii=False, indent=2)
                file.write(json_content.encode('utf-8'))
            
            xbmc.log(f'Successfully deleted {len(matching_entries)} entries from lastPlayed.json', xbmc.LOGINFO)
            
            # 延时0.5秒后运行history.py脚本
            time.sleep(0.5)
            run_script('special://skin/scripts/history.py')
        else:
            xbmc.log('No matching entries found to delete', xbmc.LOGINFO)

    except FileNotFoundError:
        xbmc.log('Error: lastPlayed.json file not found', xbmc.LOGERROR)
    except json.JSONDecodeError:
        xbmc.log('Error: Invalid JSON format in lastPlayed.json', xbmc.LOGERROR)
    except Exception as e:
        xbmc.log(f'Error in delethistory script: {str(e)}', xbmc.LOGERROR)

if __name__ == '__main__':
    main()