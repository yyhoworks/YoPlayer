"""Home entry points with explicit actions and cancellable sheets."""
import xbmc
from infuse import import_actions

ICONS = {
    'kodi': 'settings_final/tv-minimal', 'power': 'home_sheet/power',
    'more': 'home_sheet/dots', 'back': 'home_sheet/back',
    'reload': 'settings_final/refresh-cw', 'settings': 'settings_final/cog',
    'tools': 'settings_final/wrench',
    'layout': 'settings_final/panels-top-left', 'info': 'settings_final/info',
    'log': 'home_sheet/list',
}
DEVICE_ICONS = {'poweroff': 'power', 'powerdown': 'power', 'reboot': 'reload',
                'android': 'back', 'fastoff': 'power', 'kernel': 'settings'}

def row(title, detail, action, icon):
    return (title, detail, action, 'special://skin/media/infuse/' + ICONS[icon] + '.png')


def run(action):
    actions = import_actions()
    from home_dialog import Dialog
    from home_settings import menu, home_layout
    from infuse_device import capabilities, dispatch, TITLES
    dialog = Dialog()
    def native(command):
        xbmc.executebuiltin(command)
        return 'close'
    def device_page(title, names):
        caps=capabilities()
        entries=[row(TITLES[n],'执行前再次确认设备能力',lambda n=n:dispatch(n),DEVICE_ICONS[n]) for n in names if caps.get(n)]
        if entries:return menu(title,entries)
        else:dialog.ok(title,'当前设备没有可用操作。')
    def kodi_page():
        items=[]
        if capabilities().get('restartkodi'):
            items.append(row('软重启 Kodi','重新启动 Kodi 服务',lambda:dispatch('restartkodi'),'reload'))
        items.append(row('退出 Kodi','保留操作系统运行',lambda:dispatch('quit'),'back'))
        def reload_skin():
            if dialog.yesno('重新载入皮肤','重新加载当前界面？',nolabel='取消',yeslabel='重新加载'):
                return native('ReloadSkin()')
        items.append(row('重新载入皮肤','重新加载当前界面',reload_skin,'reload'))
        return menu('Kodi',items)
    if action == 'power-menu':
        power='poweroff' if capabilities().get('poweroff') else 'powerdown'
        menu('电源',[row('Kodi','重启、退出与重新加载界面',kodi_page,'kodi'),
             row('设备','正常关闭与设备重启',lambda:device_page('设备电源',[power,'reboot']),'power'),
             row('更多','安卓、快速关闭与内核工具',lambda:device_page('更多电源操作',['android','fastoff','kernel']),'more')])
    if action == 'settings':
        from infuse_system_tools import show, open_native
        menu('设置',[row('首页布局','显示或隐藏首页分区',home_layout,'layout'),
             row('系统信息','设备、资源、网络与版本',lambda:open_native('1182'),'info'),
             row('系统工具','显示、网络与故障排查',show,'tools'),
             row('高级设置','打开完整 Kodi 设置',lambda:open_native('Settings'),'settings')])
    elif action == 'search-menu':
        actions.search()
