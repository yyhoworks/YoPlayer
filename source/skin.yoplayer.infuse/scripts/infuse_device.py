"""One capability contract for menus and guarded device dispatch."""
import json
import os
import shutil
import subprocess
import sys

import xbmc
import xbmcgui

PREFIX = 'YoPlayer.Infuse.Capability.'
TITLES = {'fastoff': '快速关闭系统', 'poweroff': '正常关闭系统', 'powerdown': '关闭系统',
          'reboot': '断电重启', 'android': '重启到安卓系统',
          'restartkodi': '软重启 Kodi', 'kernel': '内核切换/升级', 'clean': '清理内存占用', 'quit': '退出 Kodi'}


def capabilities():
    settings = xbmc.getCondVisibility('System.AddonIsEnabled(service.coreelec.settings)')
    linux = xbmc.getCondVisibility('System.Platform.Linux')
    ce = bool(linux and settings)
    if linux and not ce:
        try:
            with open('/etc/os-release') as f:
                ce = any(line.strip().lower().replace('"','') == 'id=coreelec' for line in f)
        except OSError:
            pass
    return {
        'quit': True,
        'powerdown': bool(xbmc.getCondVisibility('System.CanPowerDown')),
        'coreelec': bool(ce and settings),
        'kernel': bool(ce and os.access('/storage/.config', os.W_OK)),
        'android': bool(ce and os.path.isfile('/usr/sbin/rebootfromnand') and os.access('/usr/sbin/rebootfromnand', os.X_OK)),
        'restartkodi': bool(ce and shutil.which('nohup') and shutil.which('sh')),
        'fastoff': bool(ce and xbmc.getCondVisibility('System.CanPowerDown') and os.access('/usr/sbin/poweroff', os.X_OK)),
        'poweroff': bool(ce and xbmc.getCondVisibility('System.CanPowerDown')),
        'reboot': bool(ce and xbmc.getCondVisibility('System.CanReboot') and shutil.which('reboot') and shutil.which('sync')),
        'clean': bool(ce and os.access('/proc/sys/vm/drop_caches', os.W_OK)),
    }


def publish(only_changed=False):
    window = xbmcgui.Window(10000)
    current = capabilities()
    snapshot = json.dumps(current, sort_keys=True, separators=(',', ':'))
    # Share the completed snapshot with explicit menu publications from other
    # invokers. Startup/menu calls still publish every property to repair state.
    if only_changed and window.getProperty(PREFIX + 'Snapshot') == snapshot:
        return
    for name, supported in current.items():
        window.setProperty(PREFIX + name, str(supported).lower())
        window.setProperty(PREFIX + name + '.Reason', '' if supported else '当前设备不支持或缺少所需权限')
    window.setProperty(PREFIX + 'Snapshot', snapshot)


def dispatch(action, guard=None):
    if action not in TITLES:
        return
    dialog = xbmcgui.Dialog()
    if not capabilities().get(action):
        dialog.ok(TITLES[action], '当前设备不支持此操作，或缺少所需工具与权限。')
        return
    if guard is not None and not guard():
        dialog.ok(TITLES[action], '播放或设备状态已改变，操作已取消。')
        return
    message = '是否执行“{}”？'.format(TITLES[action])
    if action == 'poweroff':
        message += ('\n已启用目录同步：同步流程完成后按原 CE 流程关闭。'
                    if xbmc.getCondVisibility('Skin.HasSetting(cd2strm)') else
                    '\n未启用目录同步：按原 CE 关机流程关闭。')
    if not dialog.yesno(TITLES[action], message,
                        nolabel='取消', yeslabel='执行', defaultbutton=xbmcgui.DLG_YESNO_NO_BTN):
        return
    # A modal confirmation may outlive permission/service changes.
    if not capabilities().get(action):
        dialog.ok(TITLES[action], '设备状态已改变，操作已取消。')
        return
    if guard is not None and not guard():
        dialog.ok(TITLES[action], '播放或设备状态已改变，操作已取消。')
        return
    try:
        if action == 'android':
            # Never fall back to Reset when the Android command fails.
            subprocess.run(['/usr/sbin/rebootfromnand'], check=True, timeout=30)
        elif action == 'powerdown':
            xbmc.executebuiltin('Powerdown()')
        elif action == 'fastoff':
            xbmc.executebuiltin('RunScript(special://skin/scripts/fastoff.py)')
        elif action == 'poweroff':
            # Original Minsk has mutually exclusive onclick conditions. The
            # sync script itself invokes rebootoff after its work, so dispatching
            # both scripts here races the sync and may request poweroff twice.
            script = ('cd2strm.py,allsync' if xbmc.getCondVisibility('Skin.HasSetting(cd2strm)')
                      else 'rebootoff.py,turnoff')
            xbmc.executebuiltin('RunScript(special://skin/scripts/{})'.format(script))
        elif action == 'reboot':
            xbmc.executebuiltin('RunScript(special://skin/scripts/rebootoff.py,noask)')
        elif action == 'quit':
            xbmc.executebuiltin('Quit()')
        elif action == 'clean':
            from infuse_memory_cleaner import MemoryCleaner
            MemoryCleaner().perform_cleanup()
        else:
            command = 'cetranscpm.py,select' if action == 'kernel' else 'restartkodi.py'
            xbmc.executebuiltin('RunScript(special://skin/scripts/{})'.format(command))
    except (OSError, subprocess.SubprocessError) as exc:
        xbmc.log('Infuse device action: {}'.format(exc), xbmc.LOGWARNING)
        dialog.ok(TITLES[action], '操作未成功，请检查设备状态后重试。')


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'publish'
    publish() if action == 'publish' else dispatch(action)
