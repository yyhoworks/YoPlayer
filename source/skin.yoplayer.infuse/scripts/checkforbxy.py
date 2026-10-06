"""Read dependency state and route to existing native management; never install.

Unlike the historical script this does not download, remove add-ons, choose
buttons in another dialog, or start a library scan.
"""
import sys
import xbmc
import xbmcgui

SCRAPERS = (
    ('电影刮削器', 'metadata.tmdb.cn.optimization'),
    ('剧集刮削器', 'metadata.tvshows.tmdb.cn.optimization'),
)


def dependency_state():
    rows = []
    for title, addon_id in SCRAPERS:
        installed = bool(xbmc.getCondVisibility('System.HasAddon({})'.format(addon_id)))
        enabled = installed and bool(xbmc.getCondVisibility('System.AddonIsEnabled({})'.format(addon_id)))
        rows.append((title, addon_id, '已启用' if enabled else '已安装但未启用' if installed else '未安装'))
    return rows


def main(mode='manage'):
    if mode not in ('manage', 'library'):
        xbmcgui.Dialog().ok('刮削依赖', '无法识别操作模式；未启动扫描或修改设置。')
        return False
    rows = dependency_state()
    if all(row[2] == '已启用' for row in rows):
        # autotmdb presents its existing menu; choosing a scan remains separate.
        xbmc.executebuiltin('RunScript(special://skin/scripts/autotmdb.py,{})'.format(mode))
        return True
    summary = '\n'.join('{}：{}\n{}'.format(title, state, addon_id) for title, addon_id, state in rows)
    dialog = xbmcgui.Dialog()
    choice = dialog.select('刮削器尚未就绪', ['查看依赖状态', '打开“我的插件”', '打开“从库安装”', '取消'])
    if choice == 0:
        dialog.textviewer('刮削依赖状态', summary + '\n\n请在 Kodi 插件管理中检查、启用或安装所需刮削器。'
                          '\n本入口不会自动下载安装。完成后返回原条目，再次打开“扫描/管理海报数据”或“添加来源并扫描刮削”。')
    elif choice == 1:
        xbmc.executebuiltin('ActivateWindow(addonbrowser,addons://user/,return)')
    elif choice == 2:
        xbmc.executebuiltin('ActivateWindow(addonbrowser,addons://repos/,return)')
    return False


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'manage')
