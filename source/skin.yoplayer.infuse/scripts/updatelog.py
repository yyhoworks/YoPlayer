# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import os

def log(msg):
    """辅助函数：将消息打印到 Kodi 日志"""
    xbmc.log("### UpdateLog Script: %s" % msg, level=xbmc.LOGDEBUG)

def run():
    log("脚本开始运行")
    
    # 1. 定义日志文件路径
    log_path = xbmcvfs.translatePath('special://skin/changelog.log')
    
    # 2. 兼容检查：如果 .log 不存在，检查是否有 .txt
    if not xbmcvfs.exists(log_path):
        alt_path = log_path.replace('.log', '.txt')
        if xbmcvfs.exists(alt_path):
            log_path = alt_path
            log("检测到 .log 不存在，自动切换为: %s" % log_path)
        else:
            log("错误：文件不存在 - %s" % log_path)
            xbmcgui.Dialog().notification("错误", "找不到更新日志文件", xbmcgui.NOTIFICATION_ERROR)
            return

    log("尝试读取文件: %s" % log_path)
    content = ""

    try:
        # 3. 使用 Python 原生 open() 函数
        # 关键点：
        # - 使用 xbmcvfs.translatePath 获取绝对路径后，就可以用 open() 了
        # - encoding='utf-8' 尝试以 utf-8 读取
        # - errors='ignore' 如果遇到无法识别的字符（如 0xb7），直接忽略而不是报错
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        log("文件读取成功 (已忽略非法字符)")
            
    except Exception as e:
        log("读取文件时发生异常: %s" % str(e))
        xbmcgui.Dialog().notification("错误", "读取日志文件失败", xbmcgui.NOTIFICATION_ERROR)
        return

    # 4. 显示文本查看器
    if content:
        log("正在打开文本查看器...")
        xbmcgui.Dialog().textviewer("更新日志", content)

if __name__ == '__main__':
    run()