# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import os

def delete_tvshow_records():
    """
    删除 tvshowrecord.xml 文件的脚本
    """
    
    # 定义确认对话框的标题和消息
    heading = "确认操作"
    message = "此操作将删除所有标记过的剧集片头片尾记录点，是否继续？\n选择“是”立即执行，选择“否”则退出。"
    
    # 弹出是/否确认窗口
    if not xbmcgui.Dialog().yesno(heading, message):
        # 用户选择“否”，直接退出脚本
        return

    # 用户选择“是”，执行删除操作
    try:
        # 获取 tvshowrecord.xml 的完整路径
        # 使用 xbmcvfs.translatePath 替代已弃用的 xbmc.translatePath
        userdata_path = xbmcvfs.translatePath('special://userdata/')
        tvshows_dir = os.path.join(userdata_path, 'tvshows')
        target_file = os.path.join(tvshows_dir, 'tvshowrecord.xml')
        
        # 检查文件是否存在
        if xbmcvfs.exists(target_file):
            # 删除文件
            # xbmcvfs.delete 可以删除文件或空目录
            if xbmcvfs.delete(target_file):
                success_heading = "完成"
                success_message = "已将所有片头片尾记录全部清除！"
                xbmcgui.Dialog().ok(success_heading, success_message)
            else:
                raise Exception("无法删除文件，可能权限不足或文件被占用")
        else:
            # 如果文件不存在，也提示用户
            success_heading = "完成"
            success_message = "未找到记录文件，无需清除。"
            xbmcgui.Dialog().ok(success_heading, success_message)
            
    except Exception as e:
        # 如果发生错误（如权限不足），弹出错误提示
        error_heading = "错误"
        error_message = "删除文件时发生错误: {}".format(str(e))
        xbmcgui.Dialog().ok(error_heading, error_message)
        xbmc.log(msg="[deletjump.py] Error deleting file: {}".format(str(e)), level=xbmc.LOGERROR)

# 执行主函数
if __name__ == '__main__':
    delete_tvshow_records()