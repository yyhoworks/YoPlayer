"""Homepage editors: real library data, cancellable drafts and guarded commits."""
import copy
import xbmc
import xbmcgui
from home_dialog import Dialog
import genres


def entry(title, detail='', icon=''):
    item = xbmcgui.ListItem(label=title, label2=detail, offscreen=True)
    if icon:
        item.setArt({'icon': icon})
    return item


def set_hidden(key, hidden):
    """Synchronize Kodi's builtin queue before constructing the next menu."""
    if xbmc.Monitor().abortRequested():return False
    xbmc.executebuiltin('Skin.SetBool({},{})'.format(key, 'true' if hidden else 'false'),wait=True)
    if xbmc.Monitor().abortRequested():return False
    if bool(xbmc.getCondVisibility('Skin.HasSetting({})'.format(key)))!=hidden:
        Dialog().ok('显示状态未能确认','Kodi 未确认此项更改，请查看当前状态后重试。')
        return False
    return True


def migrate_genre_display():
    """One-way, idempotent effective legacy visibility migration; retain JSON."""
    if xbmc.getCondVisibility('Skin.HasSetting(YoPlayerGenreDisplayMigrated)'):return True
    from provider import preferences
    prefs=preferences()
    hidden=bool(prefs.get('genres',{}).get('hidden',False) or xbmc.getCondVisibility('Skin.HasSetting(InfuseHideGenres)'))
    if not set_hidden('InfuseHideGenres',hidden):return False
    return set_hidden('YoPlayerGenreDisplayMigrated',True)


def menu(title, entries):
    """Each nested page returns to the selected parent entry."""
    position = 0
    while True:
        selected = Dialog().select(title, [entry(x[0], x[1], x[3] if len(x) > 3 else '') for x in entries], preselect=position)
        if not 0 <= selected < len(entries):
            return
        position = selected
        if entries[selected][2]() == 'close':
            return 'close'


def commit(base, draft):
    from provider import preferences_path
    from catalog import save_preferences
    from actions import refresh
    try:
        save_preferences(preferences_path(), draft, expected=base)
    except (ValueError, FileExistsError):
        Dialog().ok('设置已发生变化', '请重新打开此页后再保存；本次草稿没有覆盖其他更改。')
        return False
    refresh()
    return True


def reorder(title, values, nested=False):
    """Return a private draft; persistence remains with the owning page."""
    from reorder_dialog import show
    return show(title, values, nested=nested)


def genre_settings():
    from provider import preferences, get_genres
    base = preferences()
    draft = copy.deepcopy(base)
    config = draft.setdefault('genres', {'schema': 1, 'show_all': True})
    if 'hidden' not in config:
        config['hidden'] = xbmc.getCondVisibility('Skin.HasSetting(InfuseHideGenres)')
    available = get_genres()
    chosen, missing = genres.selected(config, available)
    config['selected'] = chosen
    position = 0
    while True:
        entries = [entry('显示影片类型', '关闭' if config.get('hidden') else '开启'),
                   entry('选择分类', '已选 {} 类{}'.format(len(config['selected']), ' · 存在已变更分类，请重新选择' if missing else '')),
                   entry('调整顺序', '仅调整已选分类；全部分类固定在末尾'),
                   entry('全部分类入口', '开启' if config.get('show_all', True) else '关闭'),
                   entry('一键恢复推荐', '恢复常用十类与推荐顺序，保存后生效'),
                   entry('保存并返回', '本次更改仅影响首页显示'), '取消']
        selected = Dialog().select('影片类型', entries, preselect=position)
        if selected < 0 or selected == 6:
            return
        position = selected
        if selected == 0:
            config['hidden'] = not config.get('hidden', False)
        elif selected == 1:
            available = get_genres()
            previous, missing = genres.selected(config, available)
            ids = {r['id'] for r in previous}
            picked = Dialog().multiselect('选择分类', [r['name'] for r in available], preselect=[i for i,r in enumerate(available) if r['id'] in ids])
            if picked is not None:
                config['selected'] = genres.reselect(previous, available, picked)
                missing = []
        elif selected == 2:
            ordered = reorder('调整分类顺序', config['selected'], nested=True)
            if ordered is not None:
                config['selected'] = ordered
        elif selected == 3:
            config['show_all'] = not config.get('show_all', True)
        elif selected == 4:
            config['selected'] = genres.recommended(get_genres())
            config['show_all'] = True
            missing = []
        elif selected == 5:
            resolved, gone = genres.resolve(config['selected'], get_genres())
            if missing or gone:
                Dialog().ok('分类已变化', '请重新选择分类后保存。')
                continue
            config['selected'] = resolved
            if commit(base, draft):
                # Compatibility editor still owns its explicit movie visibility.
                # The new automatic row retains all actual metadata categories.
                set_hidden('InfuseHideGenres',bool(config.get('hidden',False)))
            return


def home_layout():
    if not migrate_genre_display():return
    entries = [('继续观看','InfuseHideContinue'),('媒体分库','InfuseHideLibraries'),
               ('最近添加的电影','InfuseHideRecentMovies'),('最近添加的剧集','InfuseHideRecentEpisodes'),
               ('每日精选','InfuseHidePicks'),('电影类型','InfuseHideGenres'),('剧集类型','InfuseHideShowGenres'),('未观看','InfuseHideUnwatched')]
    position = 0
    while True:
        labels = [entry(title, ('选择分类、顺序与全部分类入口' if key is None else
                  '已隐藏' if xbmc.getCondVisibility('Skin.HasSetting({})'.format(key)) else '已显示')) for title,key in entries]
        picked = Dialog().select('首页分区显示', labels, preselect=position)
        if not 0 <= picked < len(entries):return
        position = picked
        key = entries[picked][1]
        if key is None:genre_settings()
        else:
            hidden = xbmc.getCondVisibility('Skin.HasSetting({})'.format(key))
            if not set_hidden(key,not hidden):return


def edit_library(key):
    from provider import preferences, get_libraries
    from catalog import library_visible
    base = preferences(); draft = copy.deepcopy(base)
    row = next((r for r in get_libraries(include_hidden=True) if r['id'] == key), None)
    if row is None:
        Dialog().ok('分库已变化','请返回并重新选择。');return
    override = draft.setdefault('items', {}).setdefault(key, {})
    position = 0
    while True:
        hidden = not library_visible(key, row.get('source'), draft)
        items = [entry('显示名称',override.get('name') or row['name']),entry('封面图片','自定义' if override.get('thumb') else '原始封面'),
                 entry('首页显示','关闭' if hidden else '开启'),'查看来源','保存并返回','取消']
        choice = Dialog().select(row['name'],items,preselect=position)
        if choice < 0 or choice == 5:return
        position=choice
        if choice == 0:
            value=Dialog().input('显示名称',defaultt=override.get('name') or row['name']).strip()
            if value:override['name']=value
        elif choice == 1:
            mode=Dialog().select('封面图片',['选择图片','使用原始封面'])
            if mode == 0:
                image=Dialog().browse(2,'选择封面','pictures',mask='.png|.jpg|.jpeg|.webp',useThumbs=True)
                if image:override['thumb']=image
            elif mode == 1:override.pop('thumb',None)
        elif choice == 2:
            if 'selected' not in draft:
                draft['selected'] = [r['id'] for r in get_libraries(include_hidden=True)
                                     if library_visible(r['id'], r.get('source'), draft)]
            override['hidden']=not hidden
            if 'selected' in draft:
                draft['selected']=[x for x in draft['selected'] if x != key]
                if hidden:draft['selected'].append(key)
        elif choice == 3:Dialog().textviewer('分库来源',row['path'])
        elif choice == 4:
            if not any(r['id']==key and r['path']==row['path'] for r in get_libraries(include_hidden=True)):
                Dialog().ok('分库已变化','请重新打开编辑页。');return
            commit(base,draft);return


def library_settings():
    from provider import get_libraries, preferences
    from actions import choose_libraries
    position=0
    focused_key=None
    while True:
        rows=get_libraries(include_hidden=True)
        if focused_key:
            position=next((i+2 for i,r in enumerate(rows) if r['id']==focused_key), position)
        picked=Dialog().select('媒体分库',[entry('选择显示','入口及可识别的续播、记录；进度保留'),entry('调整顺序','保存后生效')]+[entry(r['name'],'名称、封面、显示与来源') for r in rows],preselect=position)
        if picked < 0:return
        position=picked
        focused_key=rows[picked-2]['id'] if 2 <= picked < len(rows)+2 else None
        if picked == 0:choose_libraries()
        elif picked == 1:
            base=preferences();ordered=reorder('分库顺序',rows)
            if ordered is not None:
                current={r['id'] for r in get_libraries(include_hidden=True)}
                if any(r['id'] not in current for r in ordered):
                    Dialog().ok('分库已变化','请重新调整顺序。');continue
                draft=copy.deepcopy(base);draft['order']=[r['id'] for r in ordered];commit(base,draft)
        elif picked-2 < len(rows):edit_library(rows[picked-2]['id'])
