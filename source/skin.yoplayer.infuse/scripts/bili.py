import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import json
import os
import time

def log_message(message, level=xbmc.LOGINFO):
    """记录日志信息"""
    xbmc.log(f"[BiliScript] {message}", level=level)

def check_addon_exists(addon_id):
    """检查插件是否存在"""
    return xbmc.getCondVisibility(f'System.HasAddon({addon_id})')

def check_addon_enabled(addon_id):
    """检查插件是否启用"""
    return xbmc.getCondVisibility(f'System.AddonIsEnabled({addon_id})')

def enable_addon(addon_id):
    """启用插件"""
    xbmc.executebuiltin(f'EnableAddon({addon_id})')

def update_local_addons():
    """更新本地插件列表"""
    xbmc.executebuiltin('UpdateLocalAddons')

def run_plugin(plugin_path):
    """运行插件"""
    xbmc.executebuiltin(f'RunPlugin({plugin_path})')

def run_script(script_path):
    """运行脚本"""
    xbmc.executebuiltin(f'RunScript({script_path})')

def dialog_close(dialog_id):
    """关闭对话框"""
    xbmc.executebuiltin(f'Dialog.Close({dialog_id})')

def wait_for_condition(condition, timeout=10000):
    """等待条件满足"""
    start_time = time.time()
    while (time.time() - start_time) * 1000 < timeout:
        if xbmc.getCondVisibility(condition):
            return True
        xbmc.sleep(100)
    return False

def get_cookie_from_file(file_path):
    """从文件中提取cookie值"""
    try:
        if not xbmcvfs.exists(file_path):
            return None
            
        file_stat = xbmcvfs.Stat(file_path)
        file_size = file_stat.st_size()
        
        # 尝试使用xbmcvfs.File读取
        try:
            with xbmcvfs.File(file_path, 'r') as f:
                content = f.read()
        except:
            content = None
        
        # 如果xbmcvfs.File读取失败或返回空内容，尝试使用Python内置函数
        if not content and file_size > 0:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except:
                return None
        
        if not content:
            return None
                
        if isinstance(content, bytes):
            content_str = content.decode('utf-8')
        else:
            content_str = content
        
        data = json.loads(content_str)
        return data.get('cookie')
    except json.JSONDecodeError:
        return None
    except Exception as e:
        log_message(f"读取Cookie文件失败: {str(e)}", level=xbmc.LOGERROR)
        return None

def is_valid_cookie(cookie_value):
    """检查cookie是否有效"""
    if not cookie_value:
        return False
    
    required_fields = ['DedeUserID', 'SESSDATA', 'bili_jct']
    cookie_str = str(cookie_value)
    
    for field in required_fields:
        if field not in cookie_str:
            return False
    
    return True

def translate_path(path):
    """兼容不同KODI版本的路径转换函数"""
    if hasattr(xbmc, 'translatePath'):
        return xbmc.translatePath(path)
    else:
        return xbmcvfs.translatePath(path)

def is_demo_mode():
    """检查是否为demo模式运行"""
    try:
        # 获取命令行参数
        import sys
        args = sys.argv
        return 'demo' in args
    except:
        # 如果无法获取参数，则默认不是demo模式
        return False

def main():
    addon_id = 'plugin.video.bili'
    account_file_path = translate_path('special://userdata/addon_data/plugin.video.bili/.storage/account.json')
    
    # 判断是否为demo模式
    demo_mode = is_demo_mode()
    
    try:
        # 第1阶段逻辑
        if check_addon_exists(addon_id):
            # 情况1：插件存在
            if check_addon_enabled(addon_id):
                # 插件已启用，执行第2阶段逻辑
                execute_stage_2(account_file_path, demo_mode)
            else:
                # 插件未启用，先启用插件
                enable_addon(addon_id)
                
                # 监测yesnodialog窗口是否可见
                if wait_for_condition('Window.IsVisible(yesnodialog)'):
                    time.sleep(0.5)
                    xbmc.executebuiltin('SetFocus(11)')
                    xbmc.executebuiltin('Action(select)')
                    
                # 等待插件启用成功后再执行第2阶段逻辑
                if wait_for_condition(f'System.AddonIsEnabled({addon_id})', 15000):
                    time.sleep(1.5)  # 延迟1.5秒
                    execute_stage_2(account_file_path, demo_mode)
                else:
                    if demo_mode:
                        run_script('special://skin/scripts/demotrailer.py')
                    else:
                        run_script('special://skin/scripts/bilitrailer.py')
        else:
            # 情况2：插件不存在
            # 2026.10.3.107：不再自动从网络下载安装插件，改为提示用户手动安装。
            xbmcgui.Dialog().ok(
                "B站插件未安装",
                "该功能需要安装 plugin.video.bili 插件。\n请自行获取并安装该插件后再使用预告片按键。"
            )
            log_message("未安装 plugin.video.bili，已停止自动下载安装（安全收口）")
            if demo_mode:
                run_script('special://skin/scripts/demotrailer.py')
            else:
                run_script('special://skin/scripts/bilitrailer.py')
    except Exception as e:
        log_message(f"脚本执行异常: {str(e)}", level=xbmc.LOGERROR)
        if demo_mode:
            run_script('special://skin/scripts/demotrailer.py')
        else:
            run_script('special://skin/scripts/bilitrailer.py')

def execute_stage_2(account_file_path, demo_mode=False):
    """执行第2阶段逻辑"""
    try:
        cookie_value = get_cookie_from_file(account_file_path)
        
        if not is_valid_cookie(cookie_value):
            # cookie为空或无效，需要登录
            dialog_close(1130)
            run_plugin('plugin://plugin.video.bili/qrcode_login/')
            
            # 监测slideshow窗口是否可见
            if wait_for_condition('Window.IsVisible(slideshow)', 10000):
                time.sleep(0.5)
                xbmcgui.Dialog().ok("登录提醒", "您当前未登录B站插件，无法获取资源，请用手机B站客户端扫码登录后，重新点击预告片按键。")
        else:
            # cookie不为空且有效，执行后续脚本
            if demo_mode:
                run_script('special://skin/scripts/demotrailer.py')
            else:
                run_script('special://skin/scripts/bilitrailer.py')
    except Exception as e:
        log_message(f"第2阶段逻辑执行异常: {str(e)}", level=xbmc.LOGERROR)
        if demo_mode:
            run_script('special://skin/scripts/demotrailer.py')
        else:
            run_script('special://skin/scripts/bilitrailer.py')

if __name__ == '__main__':
    main()