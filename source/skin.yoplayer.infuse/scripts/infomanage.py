import xbmc
import xbmcgui
import xbmcvfs
import sqlite3
import os

def debug_log(message):
    """调试日志函数"""
    xbmc.log(f"[RatingManager] {message}", level=xbmc.LOGDEBUG)

def get_user_rating(db_path, dbtype, dbid):
    """获取用户的当前评分"""
    debug_log(f"开始获取用户评分 - DBType: {dbtype}, DBID: {dbid}")
    
    table_map = {
        'movie': ('movie', 'idMovie'),
        'episode': ('episode', 'idepisode'),
        'tvshow': ('tvshow', 'idshow')
    }
    
    if dbtype not in table_map:
        debug_log(f"不支持的数据库类型: {dbtype}")
        return None
    
    table_name, id_field = table_map[dbtype]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = f"SELECT userrating FROM {table_name} WHERE {id_field} = ?"
        debug_log(f"执行查询: {query} 参数: ({dbid},)")
        cursor.execute(query, (dbid,))
        result = cursor.fetchone()
        conn.close()
        
        rating = result[0] if result else None
        debug_log(f"获取到用户评分: {rating}")
        return rating
    except Exception as e:
        debug_log(f"获取用户评分时发生错误: {str(e)}")
        return None

def set_user_rating(db_path, dbtype, dbid, new_rating):
    """设置用户的评分"""
    debug_log(f"开始设置用户评分 - DBType: {dbtype}, DBID: {dbid}, 新评分: {new_rating}")
    
    table_map = {
        'movie': ('movie', 'idMovie'),
        'episode': ('episode', 'idepisode'),
        'tvshow': ('tvshow', 'idshow')
    }
    
    if dbtype not in table_map:
        debug_log(f"不支持的数据库类型: {dbtype}")
        return False
    
    table_name, id_field = table_map[dbtype]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = f"UPDATE {table_name} SET userrating = ? WHERE {id_field} = ?"
        debug_log(f"执行更新: {query} 参数: ({new_rating}, {dbid})")
        cursor.execute(query, (new_rating, dbid))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        debug_log(f"用户评分更新完成，影响行数: {rows_affected}")
        return rows_affected > 0
    except Exception as e:
        debug_log(f"设置用户评分时发生错误: {str(e)}")
        return False

def get_rating_from_db(db_path, media_id, media_type, rating_types):
    """从数据库获取评分"""
    debug_log(f"开始从数据库获取评分 - Media ID: {media_id}, Media Type: {media_type}, Rating Types: {rating_types}")
    
    if isinstance(rating_types, str):
        rating_types = [rating_types]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        placeholders = ' OR '.join(['rating_type LIKE ?'] * len(rating_types))
        query = f"""
        SELECT rating FROM rating 
        WHERE media_id = ? AND media_type = ? 
        AND ({placeholders})
        """
        params = [media_id, media_type] + ['%' + rt + '%' for rt in rating_types]
        
        debug_log(f"执行查询: {query} 参数: {params}")
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        
        rating = result[0] if result else None
        debug_log(f"获取到评分: {rating}")
        return rating
    except Exception as e:
        debug_log(f"从数据库获取评分时发生错误: {str(e)}")
        return None

def delete_rating(db_path, media_id, media_type, rating_type):
    """删除评分记录"""
    debug_log(f"开始删除评分 - Media ID: {media_id}, Media Type: {media_type}, Rating Type: {rating_type}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 删除对应的评分记录
        delete_query = """
        DELETE FROM rating 
        WHERE media_id = ? AND media_type = ? AND rating_type LIKE ?
        """
        cursor.execute(delete_query, (media_id, media_type, f'%{rating_type}%'))
        rows_affected = cursor.rowcount
        
        conn.commit()
        conn.close()
        debug_log(f"评分记录删除成功，影响行数: {rows_affected}")
        return rows_affected > 0
    except Exception as e:
        debug_log(f"删除评分记录时发生错误: {str(e)}")
        return False

def update_or_insert_rating(db_path, media_id, media_type, rating_type, new_rating):
    """更新或插入评分记录"""
    debug_log(f"开始更新或插入评分 - Media ID: {media_id}, Media Type: {media_type}, Rating Type: {rating_type}, New Rating: {new_rating}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查是否存在对应的评分记录
        check_query = """
        SELECT rating_id FROM rating 
        WHERE media_id = ? AND media_type = ? AND rating_type LIKE ?
        """
        cursor.execute(check_query, (media_id, media_type, f'%{rating_type}%'))
        existing_record = cursor.fetchone()
        
        if existing_record:
            # 更新现有的评分
            update_query = """
            UPDATE rating SET rating = ? 
            WHERE media_id = ? AND media_type = ? AND rating_type LIKE ?
            """
            cursor.execute(update_query, (new_rating, media_id, media_type, f'%{rating_type}%'))
            debug_log(f"更新现有评分记录，Rating ID: {existing_record[0]}")
        else:
            # 获取下一个可用的rating_id
            cursor.execute("SELECT MAX(rating_id) FROM rating")
            max_id = cursor.fetchone()[0]
            next_id = 1 if max_id is None else max_id + 1
            
            # 插入新的评分记录
            insert_query = """
            INSERT INTO rating (rating_id, media_id, media_type, rating_type, rating)
            VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(insert_query, (next_id, media_id, media_type, rating_type, new_rating))
            debug_log(f"插入新评分记录，Rating ID: {next_id}")
        
        conn.commit()
        conn.close()
        debug_log("评分记录更新/插入完成")
        return True
    except Exception as e:
        debug_log(f"更新或插入评分记录时发生错误: {str(e)}")
        return False

def format_tomato_popcorn_rating(value):
    """格式化番茄和爆米花评分"""
    if value is None:
        debug_log("评分值为None，返回'无'")
        return "无"
    
    try:
        rating = float(value)
        debug_log(f"原始评分值: {rating}")
        
        if rating < 10:
            formatted = round(rating * 10)
            debug_log(f"评分小于10，乘以10后四舍五入: {formatted}")
        else:
            formatted = round(rating)
            debug_log(f"评分大于等于10，直接四舍五入: {formatted}")
        
        result = f"{formatted}%"
        debug_log(f"格式化结果: {result}")
        return result
    except ValueError:
        debug_log(f"评分值无法转换为浮点数: {value}")
        return "无"

def get_rating_color(rating_value, is_popcorn_or_tomato=False):
    """根据评分获取对应的颜色"""
    if rating_value is None or rating_value == "无":
        return ""
    
    try:
        rating = float(rating_value)
        
        if is_popcorn_or_tomato:
            # 对于烂番茄和爆米花评分，判断是否>=80或>=60
            if rating >= 80:
                return "[COLOR red]"
            elif rating >= 60:
                return "[COLOR lime]"  # 使用lime作为亮绿色
            else:
                return "[COLOR yellow]"
        else:
            # 对于其他评分，判断是否>=8.0或>=6.0
            if rating >= 8.0:
                return "[COLOR red]"
            elif rating >= 6.0:
                return "[COLOR lime]"  # 使用lime作为亮绿色
            else:
                return "[COLOR yellow]"
    except ValueError:
        return ""

def get_decimal_rating(prompt_title):
    """Edit or explicitly clear a rating; cancelling either input never deletes it."""
    dialog = xbmcgui.Dialog()
    action = dialog.select(prompt_title, ['编辑评分', '清除评分', '取消'])
    if action == 1:
        return 'DELETE' if dialog.yesno('清除评分', '确认清除此项评分？其他评分不受影响。') else None
    if action != 0:
        return None
    
    # 输入整数部分（不显示默认值）
    integer_input = dialog.input(f'{prompt_title} - 整数部分', defaultt="", type=xbmcgui.INPUT_NUMERIC)
    if not integer_input:
        return None
    
    # 输入小数部分（十分位，不显示默认值）
    decimal_input = dialog.input(f'{prompt_title} - 小数部分 (0-9)', defaultt="0", type=xbmcgui.INPUT_NUMERIC)
    if not decimal_input:
        return None
    
    # 合并整数和小数部分
    try:
        integer_num = int(integer_input)
        
        if decimal_input:
            # 将用户输入的小数部分转换为十分位
            # 例如：输入6 -> 0.6, 输入5 -> 0.5
            decimal_digit = int(decimal_input)
            if not 0 <= decimal_digit <= 9:
                dialog.ok('错误', '小数部分请输入 0-9')
                return None
            decimal_num = decimal_digit / 10.0
        else:
            decimal_num = 0.0
        
        # 计算最终评分
        final_rating = integer_num + decimal_num
        return final_rating
    except ValueError:
        xbmcgui.Dialog().ok("错误", "请输入有效的数字")
        return None

def get_percentage_rating(prompt_title):
    """Native numeric keypad, with an explicit and separately confirmed clear."""
    dialog = xbmcgui.Dialog()
    action = dialog.select(prompt_title, ['编辑评分', '清除评分', '取消'])
    if action == 1:
        return 'DELETE' if dialog.yesno('清除评分', '确认清除此项评分？其他评分不受影响。') else None
    if action != 0:
        return None
    return dialog.input(prompt_title + ' (0-100)', defaultt='', type=xbmcgui.INPUT_NUMERIC) or None

def manage_rating_avatar():
    dialog = xbmcgui.Dialog()
    action = dialog.select('我的评分头像', ['选择图片', '清除头像', '取消'])
    if action == 0:
        image_path = dialog.browseSingle(1, '选择评分头像', 'pictures')
        if image_path:
            xbmc.executebuiltin(f'Skin.SetString(myratingimg,{image_path})')
    elif action == 1 and dialog.yesno('清除头像', '确认清除自定义评分头像？'):
        xbmc.executebuiltin('Skin.SetString(myratingimg,"")')

def main():
    debug_log("评分管理脚本启动")
    
    # 获取命令行参数
    import sys
    args = sys.argv
    debug_log(f"接收到的参数: {args}")
    
    if len(args) < 2 or args[1] != "rating":
        debug_log("参数不足或不是rating命令，退出")
        return
    
    # 获取当前项目信息
    dbtype = xbmc.getInfoLabel('ListItem.DBTYPE')
    dbid_str = xbmc.getInfoLabel('ListItem.DBID')
    
    debug_log(f"获取到的DBTYPE: {dbtype}")
    debug_log(f"获取到的DBID: {dbid_str}")
    
    if not dbtype or not dbid_str:
        xbmcgui.Dialog().ok("错误", "无法获取当前项目的数据库信息")
        debug_log("无法获取数据库信息，退出")
        return
    
    try:
        dbid = int(dbid_str)
        debug_log(f"转换后的DBID: {dbid}")
    except ValueError:
        xbmcgui.Dialog().ok("错误", "无效的数据库ID")
        debug_log("无效的数据库ID，退出")
        return
    
    # 数据库路径
    database_path = xbmcvfs.translatePath('special://userdata/Database/MyVideos131.db')
    debug_log(f"数据库路径: {database_path}")
    
    while True:
        # 获取各种评分
        debug_log("开始获取各种评分...")
        
        tmdb_rating = get_rating_from_db(database_path, dbid, dbtype, ['tmdb', 'default', 'themoviedb'])
        imdb_rating = get_rating_from_db(database_path, dbid, dbtype, 'imdb')
        tomato_rating = get_rating_from_db(database_path, dbid, dbtype, 'tomato')
        popcorn_rating = get_rating_from_db(database_path, dbid, dbtype, 'popcorn')
        
        debug_log(f"获取到的评分 - TMDB: {tmdb_rating}, IMDB: {imdb_rating}, Tomato: {tomato_rating}, Popcorn: {popcorn_rating}")
        
        # 格式化番茄和爆米花评分
        formatted_tomato = format_tomato_popcorn_rating(tomato_rating)
        formatted_popcorn = format_tomato_popcorn_rating(popcorn_rating)
        
        debug_log(f"格式化后的番茄评分: {formatted_tomato}, 爆米花评分: {formatted_popcorn}")
        
        # 获取用户当前评分
        current_user_rating = get_user_rating(database_path, dbtype, dbid)
        debug_log(f"当前用户评分: {current_user_rating}")
        
        # 创建选择对话框，添加颜色标识
        # 获取各评分对应的颜色
        user_rating_color = get_rating_color(current_user_rating)
        tmdb_rating_color = get_rating_color(tmdb_rating)
        imdb_rating_color = get_rating_color(imdb_rating)
        tomato_rating_color = get_rating_color(tomato_rating, is_popcorn_or_tomato=True)
        popcorn_rating_color = get_rating_color(popcorn_rating, is_popcorn_or_tomato=True)
        
        # 构建带颜色的选项列表
        # 只有当评分存在且不为"无"时才添加颜色标签
        user_rating_display = f"{current_user_rating}" if current_user_rating is not None else "无"
        if current_user_rating is not None and current_user_rating != "无":
            user_rating_display = f"{user_rating_color}{current_user_rating}[/COLOR]"
        
        tmdb_rating_display = f"{tmdb_rating}" if tmdb_rating is not None else "无"
        if tmdb_rating is not None and tmdb_rating != "无":
            tmdb_rating_display = f"{tmdb_rating_color}{tmdb_rating}[/COLOR]"
        
        imdb_rating_display = f"{imdb_rating}" if imdb_rating is not None else "无"
        if imdb_rating is not None and imdb_rating != "无":
            imdb_rating_display = f"{imdb_rating_color}{imdb_rating}[/COLOR]"
        
        tomato_rating_display = formatted_tomato
        if formatted_tomato != "无":
            tomato_rating_display = f"{tomato_rating_color}{formatted_tomato}[/COLOR]"
        
        popcorn_rating_display = formatted_popcorn
        if formatted_popcorn != "无":
            popcorn_rating_display = f"{popcorn_rating_color}{formatted_popcorn}[/COLOR]"
        
        options = [
            "自定义我的评分头像",
            f"我的评分-{user_rating_display}",
            f"TMDB评分-{tmdb_rating_display}",
            f"IMDB评分-{imdb_rating_display}",
            f"烂番茄评分-{tomato_rating_display}",
            f"爆米花评分-{popcorn_rating_display}"
        ]
        
        debug_log(f"显示选项: {options}")
        
        dialog = xbmcgui.Dialog()
        selected = dialog.select("评分管理", options)
        
        if selected == -1:  # 用户取消
            debug_log("用户取消操作，退出循环")
            break
        
        elif selected == 0:  # 自定义我的评分头像
            debug_log("用户选择自定义评分头像")
            manage_rating_avatar()
        
        elif selected == 1:  # 设置我的评分
            debug_log("用户选择设置我的评分")
            # 使用自定义小数输入方法（不显示默认值）
            new_rating = get_decimal_rating("请输入我的评分")
            if new_rating == "DELETE":
                # 删除用户评分
                if set_user_rating(database_path, dbtype, dbid, None):
                    xbmcgui.Dialog().notification("成功", "我的评分已删除", time=1000)
                    debug_log("用户评分删除成功")
                else:
                    xbmcgui.Dialog().ok("错误", "删除评分失败")
                    debug_log("用户评分删除失败")
            elif new_rating is not None:
                try:
                    debug_log(f"用户输入的新评分: {new_rating}")
                    
                    if 0 <= new_rating <= 10:
                        if set_user_rating(database_path, dbtype, dbid, new_rating):
                            xbmcgui.Dialog().notification("成功", "评分已更新", time=1000)
                            debug_log("用户评分更新成功")
                        else:
                            xbmcgui.Dialog().ok("错误", "更新评分失败")
                            debug_log("用户评分更新失败")
                    else:
                        xbmcgui.Dialog().ok("错误", "评分应在0-10之间")
                        debug_log("评分不在有效范围内")
                except ValueError:
                    xbmcgui.Dialog().ok("错误", "请输入有效的数字")
                    debug_log("输入的评分不是有效数字")
        
        elif selected == 2:  # TMDB评分
            debug_log("用户选择设置TMDB评分")
            # 使用自定义小数输入方法（不显示默认值）
            new_rating = get_decimal_rating("请输入TMDB评分")
            if new_rating == "DELETE":
                # 删除TMDB评分
                success = delete_rating(database_path, dbid, dbtype, 'tmdb')
                if success:
                    xbmcgui.Dialog().notification("成功", "TMDB评分已删除", time=1000)
                    debug_log("TMDB评分删除成功")
                else:
                    xbmcgui.Dialog().ok("错误", "删除TMDB评分失败")
                    debug_log("TMDB评分删除失败")
            elif new_rating is not None:
                try:
                    debug_log(f"用户输入的新TMDB评分: {new_rating}")
                    
                    if 0 <= new_rating <= 10:
                        # 保存评分到tmdb类型
                        success = update_or_insert_rating(database_path, dbid, dbtype, 'tmdb', new_rating)
                        if success:
                            xbmcgui.Dialog().notification("成功", "TMDB评分已更新", time=1000)
                            debug_log("TMDB评分更新成功")
                        else:
                            xbmcgui.Dialog().ok("错误", "更新TMDB评分失败")
                            debug_log("TMDB评分更新失败")
                    else:
                        xbmcgui.Dialog().ok("错误", "评分应在0-10之间")
                        debug_log("TMDB评分不在有效范围内")
                except ValueError:
                    xbmcgui.Dialog().ok("错误", "请输入有效的数字")
                    debug_log("输入的TMDB评分不是有效数字")
        
        elif selected == 3:  # IMDB评分
            debug_log("用户选择设置IMDB评分")
            # 使用自定义小数输入方法（不显示默认值）
            new_rating = get_decimal_rating("请输入IMDB评分")
            if new_rating == "DELETE":
                # 删除IMDB评分
                success = delete_rating(database_path, dbid, dbtype, 'imdb')
                if success:
                    xbmcgui.Dialog().notification("成功", "IMDB评分已删除", time=1000)
                    debug_log("IMDB评分删除成功")
                else:
                    xbmcgui.Dialog().ok("错误", "删除IMDB评分失败")
                    debug_log("IMDB评分删除失败")
            elif new_rating is not None:
                try:
                    debug_log(f"用户输入的新IMDB评分: {new_rating}")
                    
                    if 0 <= new_rating <= 10:
                        success = update_or_insert_rating(database_path, dbid, dbtype, 'imdb', new_rating)
                        if success:
                            xbmcgui.Dialog().notification("成功", "IMDB评分已更新", time=1000)
                            debug_log("IMDB评分更新成功")
                        else:
                            xbmcgui.Dialog().ok("错误", "更新IMDB评分失败")
                            debug_log("IMDB评分更新失败")
                    else:
                        xbmcgui.Dialog().ok("错误", "评分应在0-10之间")
                        debug_log("IMDB评分不在有效范围内")
                except ValueError:
                    xbmcgui.Dialog().ok("错误", "请输入有效的数字")
                    debug_log("输入的IMDB评分不是有效数字")
        
        elif selected == 4:  # 烂番茄评分
            debug_log("用户选择设置烂番茄评分")
            # 直接显示空白输入框，不显示默认值
            rating_input = get_percentage_rating('烂番茄评分百分比')
            if rating_input is None:
                continue
            if rating_input == 'DELETE':
                # 用户未输入内容，删除评分
                success = delete_rating(database_path, dbid, dbtype, 'tomato')
                if success:
                    xbmcgui.Dialog().notification("成功", "烂番茄评分已删除", time=1000)
                    debug_log("烂番茄评分删除成功")
                else:
                    xbmcgui.Dialog().ok("错误", "删除烂番茄评分失败")
                    debug_log("烂番茄评分删除失败")
            else:
                try:
                    input_rating = float(rating_input)
                    debug_log(f"用户输入的新烂番茄评分: {input_rating}")
                    
                    if 0 <= input_rating <= 100:
                        # 处理评分存储
                        if input_rating <= 10:
                            stored_rating = input_rating / 10.0
                        else:
                            stored_rating = input_rating
                        
                        debug_log(f"处理后的存储评分: {stored_rating}")
                        success = update_or_insert_rating(database_path, dbid, dbtype, 'tomato', stored_rating)
                        if success:
                            xbmcgui.Dialog().notification("成功", "烂番茄评分已更新", time=1000)
                            debug_log("烂番茄评分更新成功")
                        else:
                            xbmcgui.Dialog().ok("错误", "更新烂番茄评分失败")
                            debug_log("烂番茄评分更新失败")
                    else:
                        xbmcgui.Dialog().ok("错误", "评分应在0-100之间")
                        debug_log("烂番茄评分不在有效范围内")
                except ValueError:
                    xbmcgui.Dialog().ok("错误", "请输入有效的数字")
                    debug_log("输入的烂番茄评分不是有效数字")
        
        elif selected == 5:  # 爆米花评分
            debug_log("用户选择设置爆米花评分")
            # 直接显示空白输入框，不显示默认值
            rating_input = get_percentage_rating('爆米花评分百分比')
            if rating_input is None:
                continue
            if rating_input == 'DELETE':
                # 用户未输入内容，删除评分
                success = delete_rating(database_path, dbid, dbtype, 'popcorn')
                if success:
                    xbmcgui.Dialog().notification("成功", "爆米花评分已删除", time=1000)
                    debug_log("爆米花评分删除成功")
                else:
                    xbmcgui.Dialog().ok("错误", "删除爆米花评分失败")
                    debug_log("爆米花评分删除失败")
            else:
                try:
                    input_rating = float(rating_input)
                    debug_log(f"用户输入的新爆米花评分: {input_rating}")
                    
                    if 0 <= input_rating <= 100:
                        # 处理评分存储
                        if input_rating <= 10:
                            stored_rating = input_rating / 10.0
                        else:
                            stored_rating = input_rating
                        
                        debug_log(f"处理后的存储评分: {stored_rating}")
                        success = update_or_insert_rating(database_path, dbid, dbtype, 'popcorn', stored_rating)
                        if success:
                            xbmcgui.Dialog().notification("成功", "爆米花评分已更新", time=1000)
                            debug_log("爆米花评分更新成功")
                        else:
                            xbmcgui.Dialog().ok("错误", "更新爆米花评分失败")
                            debug_log("爆米花评分更新失败")
                    else:
                        xbmcgui.Dialog().ok("错误", "评分应在0-100之间")
                        debug_log("爆米花评分不在有效范围内")
                except ValueError:
                    xbmcgui.Dialog().ok("错误", "请输入有效的数字")
                    debug_log("输入的爆米花评分不是有效数字")

if __name__ == '__main__':
    main()
