"""Library view and complete-directory sorting commands; never write history."""
import json
import sys
from urllib.parse import parse_qs, urlsplit
import xbmc
import xbmcgui
from infuse import import_actions


def source():
    path = xbmc.getInfoLabel('Container.FolderPath')
    if 'route=native-browse' in path and path.startswith('plugin://plugin.video.yoplayer.home/'):
        query = parse_qs(urlsplit(path).query).get('q', [''])[0]
        selection = json.loads(query)
        return path, selection
    label = xbmc.getInfoLabel('Container.SortMethod').strip().casefold()
    methods = {'标题':'title', '名称':'title', 'title':'title', 'name':'title',
               '年份':'year', 'year':'year', '评分':'rating', 'rating':'rating',
               '添加日期':'dateadded', '添加时间':'dateadded', 'date added':'dateadded',
               '集数':'episode', 'episode':'episode'}
    content = xbmc.getInfoLabel('Container.Content')
    title = {'movies':'电影', 'tvshows':'剧集', 'episodes':'单集', 'seasons':'季', 'sets':'合集'}.get(content)
    return path, {'origin': path, 'method': methods.get(label, ''),
                  'order': 'ascending' if xbmc.getCondVisibility('Container.SortDirection(Ascending)') else 'descending',
                  'title': title or xbmc.getInfoLabel('Container.FolderName')}


def sort(direction=False):
    import_actions()
    from provider import plugin_url
    from browse_directory import SORTS
    before, selection = source()
    if not xbmc.getCondVisibility('Window.IsActive(Videos) + !System.HasVisibleModalDialog'):
        return
    if direction and not selection['method']:
        xbmc.executebuiltin('SendClick(10025,4)')
        return
    if direction and selection['method']:
        selection['order'] = 'descending' if selection['order'] == 'ascending' else 'ascending'
    else:
        labels = [name for name, _ in SORTS]
        preselect = next((i for i, (_, key) in enumerate(SORTS) if key == selection['method']), 0)
        picked = xbmcgui.Dialog().select('排序依据', labels, preselect=preselect)
        if not 0 <= picked < len(SORTS):
            return
        method = SORTS[picked][1]
        selection['order'] = 'descending' if method == 'rating' and selection['method'] != method else selection['order']
        selection['method'] = method
    if xbmc.getInfoLabel('Container.FolderPath') != before:
        return
    url = plugin_url('native-browse', q=json.dumps(selection, ensure_ascii=False))
    from actions import builtin_argument
    # Release this script before Kodi starts the provider for the replacement
    # directory. Waiting synchronously can leave the GUI and plugin waiting on
    # one another after the modal selector closes.
    xbmc.executebuiltin('Container.Update(' + builtin_argument(url) + ',replace)', wait=False)


def views():
    before = xbmc.getInfoLabel('Container.FolderPath')
    episode = xbmc.getCondVisibility('Container.Content(episodes)')
    # The two established skin panels are fixed and always have a valid fallback.
    titles = ['海报墙', '分集网格' if episode else '横图网格']
    current_grid = xbmc.getCondVisibility('Control.IsVisible(526)')
    picked = xbmcgui.Dialog().select('可用视图', titles, preselect=1 if current_grid else 0)
    if not 0 <= picked < len(titles) or xbmc.getInfoLabel('Container.FolderPath') != before:
        return
    wanted = 526 if picked == 1 else 525
    xbmc.executebuiltin('Container.SetViewMode(%s)' % wanted)


def fallback():
    monitor = xbmc.Monitor()
    settled = 0
    original = ''
    for _ in range(700):
        if monitor.waitForAbort(.05): return
        if not xbmc.getCondVisibility('Window.IsActive(Videos)'): return
        if xbmc.getCondVisibility('Player.HasMedia'):return
        path = xbmc.getInfoLabel('Container.FolderPath')
        if not path:continue
        if original and path != original:return
        original = path
        if xbmc.getCondVisibility('Container.IsUpdating | System.HasVisibleModalDialog'):
            settled = 0
            continue
        if 'route=native-browse' in path and xbmc.getInfoLabel('Container.Property(YoPlayer.Browse.Empty)') not in ('true','false'):
            settled = 0
            continue
        content = xbmc.getInfoLabel('Container.Content')
        if not content:continue
        if content and content not in ('movies', 'tvshows', 'seasons', 'episodes', 'sets'):
            return  # shared plugin/file/music layouts retain their own memories
        # Let Kodi restore the saved native view after replacing the directory.
        # During startup there can be a path but no visible media panel yet.
        settled += 1
        if settled < 4:continue
        if xbmc.getCondVisibility('Container.Content(episodes)') and 'route=native-browse' not in xbmc.getInfoLabel('Container.FolderPath'):
            import_actions()
            from library_state import normalize
            from provider import plugin_url
            from actions import builtin_argument
            path, selection = source()
            if path and not xbmc.getCondVisibility('Container.IsUpdating'):
                selection.update(method='episode', order='ascending', content='episodes')
                url = plugin_url('native-browse', q=json.dumps(normalize(selection), ensure_ascii=False))
                xbmc.executebuiltin('Container.Update(' + builtin_argument(url) + ',replace)', wait=False)
                return
        if xbmc.getCondVisibility('Control.IsVisible(525)') or xbmc.getCondVisibility('Control.IsVisible(526)'):
            return
        if xbmc.getInfoLabel('Container.FolderPath'):
            xbmc.executebuiltin('Container.SetViewMode(525)')
            return


def focus_cleared_directory(before, destination, expected_summary):
    """Return to Search after this refresh, without following new navigation."""
    monitor = xbmc.Monitor()
    for _ in range(350):
        if monitor.waitForAbort(.1):return
        if not xbmc.getCondVisibility('Window.IsActive(Videos)') or xbmc.getCondVisibility('Player.HasMedia'):return
        current = xbmc.getInfoLabel('Container.FolderPath')
        if current not in (before, destination):return
        if current != destination or xbmc.getCondVisibility('Container.IsUpdating | System.HasVisibleModalDialog'):continue
        if xbmc.getInfoLabel('Container.Property(YoPlayer.Browse.Summary)') != expected_summary:continue
        if xbmc.getInfoLabel('System.CurrentControlID') not in ('', '0', '525', '526', '533'):return
        # Kodi's directory completion restores the media panel itself. Wait
        # until that completion before returning this command's toolbar focus.
        xbmc.executebuiltin('SetFocus(529)', wait=False)
        return


def clear():
    import_actions()
    from library_state import normalize, summary
    from provider import plugin_url
    from actions import builtin_argument
    if not xbmc.getCondVisibility('Window.IsActive(Videos) + !System.HasVisibleModalDialog'):return
    before, selection = source()
    selection = normalize(selection, xbmc.getInfoLabel('Container.Content') or 'videos')
    selection.update(query='', genre='', year='', watched='all')
    url = plugin_url('native-browse', q=json.dumps(selection, ensure_ascii=False))
    xbmc.executebuiltin('Container.Update(' + builtin_argument(url) + ',replace)', wait=False)
    focus_cleared_directory(before, url, summary(selection))


if __name__ == '__main__' and xbmc.getSkinDir() == 'skin.yoplayer.infuse':
    try:
        if len(sys.argv) == 2:
            if sys.argv[1] in ('sort', 'direction'): sort(sys.argv[1] == 'direction')
            elif sys.argv[1] == 'views': views()
            elif sys.argv[1] == 'fallback': fallback()
            elif sys.argv[1] == 'clear': clear()
    except (ValueError, KeyError, TypeError, RuntimeError):
        xbmcgui.Dialog().notification('操作未完成', '目录已变化，请重新打开浏览选项。')
