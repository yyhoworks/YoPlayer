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

def prepare_preview(preview):
    """Only this preview may request login; never confirm another modal."""
    if not preview.valid():
        return False
    addon_id = 'plugin.video.bili'
    if not check_addon_exists(addon_id) or not check_addon_enabled(addon_id):
        preview.error('请在 Kodi 插件管理中手动安装或启用 B站插件，然后重试。')
        return False
    account = translate_path('special://userdata/addon_data/plugin.video.bili/.storage/account.json')
    cookie = get_cookie_from_file(account)
    if not preview.valid():
        return False
    if not is_valid_cookie(cookie):
        # Login is user-owned. Closing preview cancels all playback continuation.
        dialog_close(1130)
        run_plugin('plugin://plugin.video.bili/qrcode_login/')
        xbmcgui.Dialog().ok('登录提醒', '请扫码登录 B站插件后，重新点击预告片按键。')
        return False
    return preview.valid()


def main():
    if not is_demo_mode():
        from trailerurl import main as preview_main
        preview_main()
        return
    # Retain the separately requested demo entry. No automatic install, enable,
    # generic Yes/No click, or recursive retry if prerequisites are unavailable.
    addon_id = 'plugin.video.bili'
    if not check_addon_exists(addon_id) or not check_addon_enabled(addon_id):
        xbmcgui.Dialog().ok('B站插件不可用', '请在 Kodi 插件管理中手动安装或启用后重试。')
        return
    account = translate_path('special://userdata/addon_data/plugin.video.bili/.storage/account.json')
    if not is_valid_cookie(get_cookie_from_file(account)):
        run_plugin('plugin://plugin.video.bili/qrcode_login/')
        return
    run_script('special://skin/scripts/demotrailer.py')


if __name__ == '__main__':
    main()
