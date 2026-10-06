# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import subprocess

def is_coreelec():
    """
    判断当前系统是否为 CoreELEC
    通过 Kodi 内置的系统版本信息标签进行判断
    """
    try:
        os_info = xbmc.getInfoLabel('System.OSVersionInfo')
        return 'coreelec' in os_info.lower()
    except Exception:
        return False

def upload_log():
    # 1. 判断当前系统是否为 CoreELEC
    if not is_coreelec():
        dialog = xbmcgui.Dialog()
        dialog.ok('系统提示', '当前系统不是CoreELEC系统，不支持该指令')
        return  # 终止并退出脚本

    # 2. 确认是 CoreELEC 系统后，执行原有的日志上传逻辑
    # 指定要执行的系统命令
    command = 'cat ~/.kodi/temp/kodi.log | paste'
    
    try:
        # 执行命令并捕获标准输出和标准错误
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        # 判断命令是否执行成功
        if process.returncode == 0:
            # 获取返回的网址字符并去除两端空白
            result_url = stdout.decode('utf-8').strip()
        else:
            result_url = '上传失败: ' + stderr.decode('utf-8').strip()
    except Exception as e:
        result_url = '执行异常: ' + str(e)

    # 按照要求构建弹窗内容，使用 \n 实现另起一行
    message = '已将你的系统日志上传到如下网址：\n{}'.format(result_url)
    
    # 调用 Kodi 原生对话框弹出确认窗口
    dialog = xbmcgui.Dialog()
    dialog.ok('日志上传提示', message)

if __name__ == '__main__':
    upload_log()
    # 脚本执行完毕后自动退出关闭
