"""Explicit media management actions; preferences belong to this branch only."""
import time
import copy
from urllib.parse import urlencode
import xbmc
import xbmcaddon
import xbmcgui
from home_dialog import Dialog
from catalog import identity, media_directory, save_preferences
from provider import PREFIX, get_libraries, preferences, preferences_path, rpc


def menu_row(title, detail, action, icon):
    return title, detail, action, 'special://skin/media/infuse/' + icon + '.png'


def builtin_argument(value):
    if any(c in value for c in '\r\n\x00'):
        raise ValueError('Invalid Kodi argument')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def activate(path):
    xbmc.executebuiltin('ActivateWindow(Videos,{},return)'.format(builtin_argument(path)))


def refresh():
    home = xbmcgui.Window(10000)
    for route in ('continue', 'history', 'daily', 'recent-movies', 'recent-episodes', 'unwatched',
                  'GenreSummary.movie', 'GenreSummary.tvshow'):
        home.clearProperty(PREFIX + 'Cache.' + route)
    home.setProperty(PREFIX + 'RestoreLibraryId', home.getProperty(PREFIX + 'LibraryId'))
    home.setProperty(PREFIX + 'RestoreLibraryPosition', home.getProperty(PREFIX + 'LibraryPosition'))
    home.setProperty(PREFIX + 'Revision', str(time.time_ns()))
    home.setProperty(PREFIX + 'RefreshPending', str(time.monotonic()))


def save(data, expected):
    from home_settings import commit
    return commit(expected, data)


def search():
    if xbmc.getCondVisibility('System.AddonIsEnabled(script.globalsearch)'):
        xbmc.executebuiltin('RunScript(script.globalsearch)')
        return
    query = Dialog().input('搜索电影或剧集名称').strip()
    if query:
        activate('plugin://plugin.video.yoplayer.home/?' + urlencode({'route': 'search', 'q': query}))


def updates():
    from home_settings import menu
    def home():
        refresh();Dialog().notification('首页已刷新','正在重新读取分库和观看进度',time=2500)
    def emby():
        addon=next((n for n in ('plugin.service.emby-next-gen','plugin.video.emby-next-gen','plugin.video.emby') if xbmc.getCondVisibility('System.AddonIsEnabled({})'.format(n))),None)
        if addon:
            xbmcaddon.Addon(addon).openSettings();return 'close'
        Dialog().ok('Emby 管理','当前没有可用的 Emby 插件。')
    return menu('更新媒体库',[
        menu_row('刷新首页','重新读取显示内容',home,'settings_final/refresh-cw'),
        menu_row('Emby 管理','打开 Emby 插件设置',emby,'home_sheet/folder')])


def add_library():
    dialog = Dialog()
    mode = dialog.select('添加媒体分库', ['选择已有媒体目录', '输入媒体节点或播放列表路径'])
    if mode < 0:
        return
    path = dialog.browse(0, '选择媒体目录', 'video', treatAsFolder=True) if mode == 0 else dialog.input('媒体节点 / 目录 / .xsp 路径')
    if not path:
        return
    if not media_directory(path):
        dialog.ok('无法添加分库', '请选择媒体目录、library:// 或 videodb:// 节点，或者 .xsp 播放列表。')
        return
    name = dialog.input('分库名称').strip()
    if not name:
        return
    base = preferences()
    data = copy.deepcopy(base)
    key = identity(path)
    existing = next((item for item in get_libraries(include_hidden=True) if item['id'] == key), None)
    if existing:
        dialog.ok('分库已存在', existing['name'])
        return
    data.setdefault('custom', []).append({'path': path, 'title': name})
    data.setdefault('items', {}).setdefault(key, {}).update({'name': name, 'hidden': False})
    if 'selected' in data and key not in data['selected']:data['selected'].append(key)
    save(data, base)


def choose_libraries():
    """Checkboxes affect the homepage only; never alter Emby libraries."""
    rows=get_libraries(include_hidden=True)
    base=preferences()
    if not rows:
        Dialog().ok('首页分库','尚未找到 Emby 分库或已有媒体节点。请先连接 Emby 并完成分库同步，也可以手动添加媒体目录。')
        return
    visible={row['id'] for row in get_libraries()}
    entries=[]
    for row in rows:
        item=xbmcgui.ListItem(label=row['name'],label2='Emby 媒体库' if row['source']=='emby' else '已有媒体节点',offscreen=True)
        if row['thumb']:item.setArt({'thumb':row['thumb'],'icon':row['thumb']})
        entries.append(item)
    picked=Dialog().multiselect('首页分库',entries,preselect=[i for i,row in enumerate(rows) if row['id'] in visible],useDetails=True)
    if picked is None:return
    import copy
    current={row['id'] for row in get_libraries(include_hidden=True)}
    if any(rows[i]['id'] not in current for i in picked if 0<=i<len(rows)):
        Dialog().ok('分库已变化','请重新选择。');return
    data=copy.deepcopy(base);selected=[rows[i]['id'] for i in picked if 0<=i<len(rows)]
    data['selected']=selected
    for row in rows:data.setdefault('items',{}).setdefault(row['id'],{})['hidden']=row['id'] not in selected
    from home_settings import commit
    if not commit(base,data):return
    Dialog().notification('媒体分库','首页显示 {} 个分库'.format(len(selected)),time=2500)


def library(key=''):
    from home_settings import edit_library, library_settings
    if key:edit_library(key)
    else:library_settings()


def restore_libraries():
    base = preferences()
    data = copy.deepcopy(base)
    changed = False
    for key, item in data.get('items', {}).items():
        if item.get('hidden'):
            item['hidden'] = False
            if 'selected' in data and key not in data['selected']:
                data['selected'].append(key)
            changed = True
    if changed:
        if not save(data, base):return
    Dialog().notification('媒体分库', '已恢复本分支隐藏的分库' if changed else '没有隐藏的分库', time=2500)


def manage():
    from home_settings import menu, library_settings
    def open_path(path):
        activate(path)
        return 'close'
    def native(action):
        xbmc.executebuiltin(action)
        return 'close'
    def more():
        return menu('更多工具',[
            menu_row('我的收藏','打开原生收藏',lambda:native('ActivateWindow(Favouritesbrowser)'),'home_sheet/star'),
            menu_row('添加分库','媒体目录或现有节点',add_library,'home_sheet/plus'),
            menu_row('恢复隐藏分库','恢复首页入口',restore_libraries,'settings_final/refresh-cw'),
            menu_row('移除分库入口','媒体文件和源库保留',remove_library,'home_sheet/trash')])
    return menu('媒体管理',[
        menu_row('全部电影','浏览电影资料库',lambda:open_path('videodb://movies/titles/'),'home_sheet/movies'),
        menu_row('全部剧集','浏览剧集资料库',lambda:open_path('videodb://tvshows/titles/'),'home_sheet/tv'),
        menu_row('播放记录','保留真实观看记录',lambda:open_path('plugin://plugin.video.yoplayer.home/?route=history'),'home_sheet/history'),
        menu_row('媒体分库','显示、顺序、名称与封面',library_settings,'home_sheet/folder'),
        menu_row('更多工具','收藏与分库入口',more,'home_sheet/dots')])


def remove_library():
    """Remove custom links or hide discovered libraries; never remove media."""
    rows = get_libraries(include_hidden=True)
    picked = Dialog().select('移除媒体分库', [row['name'] for row in rows])
    if not 0 <= picked < len(rows):
        return
    row = rows[picked]
    if not Dialog().yesno('隐藏媒体分库', '隐藏“{}”的入口及可识别的继续观看、播放记录？原始记录、进度和媒体保留，恢复分库后重新显示。'.format(row['name'])):
        return
    base = preferences()
    data = copy.deepcopy(base)
    key = row['id']
    data['custom'] = [entry for entry in data.get('custom', []) if identity(entry['path']) != key]
    data['order'] = [item for item in data.get('order', []) if item != key]
    if 'selected' in data:
        data['selected'] = [item for item in data['selected'] if item != key]
    data.setdefault('items', {}).setdefault(key, {})['hidden'] = True
    save(data, base)


def browse_tools():
    """Native window handlers keep sorting and filtering tied to current content."""
    origin_path = xbmc.getInfoLabel('Container.FolderPath')
    options = [('排序方式', 'SendClick(10025,3)'), ('切换排序方向', 'SendClick(10025,4)'),
               ('显示视图', 'SendClick(10025,2)'), ('库内搜索', 'SendClick(10025,8)')]
    if xbmc.getCondVisibility('Container.CanFilterAdvanced'):
        options.append(('高级筛选', 'Action(Filter,10025)'))
    elif xbmc.getCondVisibility('Container.CanFilter'):
        options.append(('筛选当前内容（已有筛选时清除）', 'Action(Filter,10025)'))
    options += [('播放记录', 'ActivateWindow(Videos,"plugin://plugin.video.yoplayer.home/?route=history",return)'),
                ('媒体来源设置', 'ActivateWindow(MediaSettings)')]
    picked = Dialog().select('浏览工具', [label for label, _ in options])
    if 0 <= picked < len(options):
        command = options[picked][1]
        if command == 'Action(Filter,10025)':
            if (not xbmc.getCondVisibility('Window.IsActive(10025)') or
                    xbmc.getInfoLabel('Container.FolderPath') != origin_path):
                Dialog().ok('列表已变化', '请在当前列表重新打开筛选。')
                return
            if not (xbmc.getCondVisibility('Container.CanFilterAdvanced') or
                    xbmc.getCondVisibility('Container.CanFilter')):
                Dialog().ok('当前列表筛选', '此列表不支持筛选。')
                return
        xbmc.executebuiltin(command)


def chapters():
    playlist = xbmc.getCondVisibility('VideoPlayer.Content(episodes) | VideoPlayer.Content(livetv) | [VideoPlayer.Content(movies) + Integer.IsGreater(VideoPlayer.PlaylistLength,1)]')
    xbmc.executebuiltin('ActivateWindow(1140)' if playlist else 'ActivateWindow(VideoBookmarks)')


def coreelec():
    if xbmc.getCondVisibility('System.AddonIsEnabled(service.coreelec.settings)'):
        xbmc.executebuiltin('RunAddon(service.coreelec.settings)')
    else:
        Dialog().ok('CoreELEC', '当前系统未启用 CoreELEC 设置插件。可通过“网络与服务”和“显示与声音”设置 Kodi。')


def dispatch(action, argument=''):
    from home_settings import genre_settings, library_settings
    operations = {'manage': manage, 'updates': updates, 'search': search, 'refresh': refresh,
                  'genre-settings':genre_settings, 'library-settings':library_settings,
                  'choose-libraries':choose_libraries,
                  'library': lambda: library(argument), 'add-library': add_library, 'browse-tools': browse_tools,
                  'chapters': chapters, 'restore-libraries': restore_libraries, 'coreelec': coreelec}
    if action not in operations:
        return False
    try:
        operations[action]()
    except Exception as exc:
        xbmc.log('YoPlayer Infuse action {}: {}'.format(action, type(exc).__name__), xbmc.LOGWARNING)
        Dialog().ok('操作未完成', '请检查媒体来源和配置后重试。现有分库与媒体文件已保留。')
    return True
