"""Four toolbar popovers scoped to the current native directory."""
import copy
import json
import sys
import xbmc
import xbmcgui
import xbmcvfs
from infuse import import_actions


def run(page):
    import_actions()
    from infuse_library import source
    from library_state import normalize, SORTS
    from provider import rpc, plugin_url
    from actions import builtin_argument
    from genres import canonical
    if page not in ('more', 'views', 'sort', 'search') or not xbmc.getCondVisibility('Window.IsActive(Videos) + !System.HasVisibleModalDialog'):
        return
    origin_path, raw = source()
    state = normalize(raw, xbmc.getInfoLabel('Container.Content') or 'videos')
    state['content'] = xbmc.getInfoLabel('Container.Content') or state['content']
    button = {'more': 527, 'views': 528, 'sort': 532, 'search': 529}[page]
    grid = xbmc.getCondVisibility('Control.IsVisible(526)')

    class Menu(xbmcgui.WindowXMLDialog):
        def onInit(self):
            self.page = page
            self.stack = []
            self.position = 0
            self.view = None
            self.facets = None
            self.render()

        def render(self):
            self.entries = []
            def row(title, action, selected=False, detail=''):
                self.entries.append((title, action, selected, detail))
            titles = {'more': '更多', 'views': '排列', 'sort': '排序', 'search': '搜索当前片库',
                      'watched': '观看状态', 'genre': '类型', 'year': '年份', 'display': '显示设置'}
            if self.page == 'more':
                row('观看状态', ('page', 'watched'), detail={'all':'全部','watched':'已看','unwatched':'未看'}[state['watched']])
                row('类型', ('page', 'genre'), detail=state['genre'] or '全部')
                row('年份', ('page', 'year'), detail=state['year'] or '全部')
                row('清除筛选', ('clear', 'filters'))
                row('显示设置', ('page', 'display'))
            elif self.page == 'views':
                row('海报墙', ('view', 525), not grid)
                row('分集网格' if state['content'] == 'episodes' else '横图网格', ('view', 526), grid)
            elif self.page == 'sort':
                for title, method in SORTS + ((('集数', 'episode'),) if state['content'] == 'episodes' else ()):
                    row(title, ('method', method), state['method'] == method)
                row('升序', ('order', 'ascending'), state['order'] == 'ascending')
                row('降序', ('order', 'descending'), state['order'] == 'descending')
            elif self.page == 'watched':
                for title, value in (('全部', 'all'), ('未看', 'unwatched'), ('已看', 'watched')):
                    row(title, ('watched', value), state['watched'] == value)
            elif self.page in ('genre', 'year'):
                if self.facets is None:
                    values = rpc('Files.GetDirectory', {'directory': state['origin'], 'media': 'video', 'properties': ['genre','year']}).get('files') or []
                    self.facets = {'genre': sorted({canonical(g) for r in values for g in r.get('genre', [])}),
                                   'year': sorted({str(r['year']) for r in values if r.get('year')}, reverse=True)}
                row('全部', (self.page, ''), not state[self.page])
                for value in self.facets[self.page]:
                    row(value, (self.page, value), state[self.page] == value)
            elif self.page == 'search':
                row('输入片名', ('query', 'edit'), detail=state['query'] or '当前片库')
                row('清除查询', ('query', 'clear'))
                row('清除搜索和筛选', ('clear', 'all'))
            elif self.page == 'display':
                row('显示片名', ('setting', 'YoPlayer.HideBrowseTitles'), not xbmc.getCondVisibility('Skin.HasSetting(YoPlayer.HideBrowseTitles)'))
                if not grid and state['content'] != 'episodes':
                    row('光盘盒外套', ('setting', 'YoPlayer.BrowseCases'), xbmc.getCondVisibility('Skin.HasSetting(YoPlayer.BrowseCases)'))
            self.getControl(1001).setLabel(titles[self.page])
            listing = self.getControl(1003)
            listing.reset()
            for title, _, selected, detail in self.entries:
                item = xbmcgui.ListItem(label=title, label2=detail)
                item.setProperty('chosen', 'true' if selected else 'false')
                listing.addItem(item)
            height = min(8, len(self.entries)) * 72
            listing.setHeight(height)
            self.getControl(1010).setHeight(height + 180)
            self.getControl(1005).setPosition(1304, 236 + height)
            self.getControl(1005).setLabel('返回上一级' if self.stack else '返回关闭 · 更改即时应用')
            listing.selectItem(min(self.position, max(0, len(self.entries)-1)))
            self.setFocusId(1003)

        def valid_origin(self):
            try:
                _, current = source()
                return current['origin'] == state['origin']
            except (ValueError, KeyError, TypeError):
                return False

        def publish(self):
            if not self.valid_origin():
                self.close(); return
            url = plugin_url('native-browse', q=json.dumps(state, ensure_ascii=False))
            # Never wait for a foreground directory while holding this dialog.
            xbmc.executebuiltin('Container.Update(' + builtin_argument(url) + ',replace)', wait=False)

        def back(self):
            if self.stack:
                self.page, self.position = self.stack.pop()
                self.render()
            else:
                self.close()

        def onClick(self, ident):
            if ident == 1002:
                self.back(); return
            if ident != 1003:
                return
            self.position = self.getControl(1003).getSelectedPosition()
            if not 0 <= self.position < len(self.entries):
                return
            action, value = self.entries[self.position][1]
            if action == 'page':
                self.stack.append((self.page, self.position)); self.page = value; self.position = 0
            elif action == 'view':
                self.view = value; self.close(); return
            elif action == 'setting':
                before = xbmc.getCondVisibility('Skin.HasSetting(' + value + ')')
                xbmc.executebuiltin('Skin.SetBool(' + value + ',' + ('false' if before else 'true') + ')', wait=False)
                xbmc.sleep(60)
            else:
                previous = copy.deepcopy(state)
                if action == 'clear':
                    state.update(watched='all', genre='', year='')
                    if value == 'all':state['query'] = ''
                elif action == 'query':
                    if value == 'clear':state['query'] = ''
                    else:
                        keyboard = xbmc.Keyboard(state['query'], '搜索当前片库片名')
                        keyboard.doModal()
                        if keyboard.isConfirmed():state['query'] = keyboard.getText().strip()
                else:
                    if action == 'method' and value == 'rating' and state['method'] != 'rating':state['order'] = 'descending'
                    state[action] = value
                if previous != state:self.publish()
            self.render()

        def onAction(self, action):
            if action.getId() in (9, 10, 92):self.back()

    menu = Menu('YoPlayerLibraryMenu.xml', xbmcvfs.translatePath('special://skin'), 'Default', '1080p')
    menu.doModal()
    view = menu.view
    del menu
    # Only restore focus while still on this same source; never steal it from a
    # new page or an external action. Keep the selected panel when changing view.
    _, current = source()
    if current.get('origin') == state['origin'] and xbmc.getCondVisibility('Window.IsActive(Videos)'):
        if view is not None:xbmc.executebuiltin('Container.SetViewMode(%s)' % view, wait=False)
        xbmc.executebuiltin('SetFocus(%s)' % button, wait=False)


if __name__ == '__main__' and xbmc.getSkinDir() == 'skin.yoplayer.infuse':
    try:
        if len(sys.argv) == 2:run(sys.argv[1])
    except (ValueError, TypeError, KeyError, RuntimeError):
        xbmcgui.Dialog().notification('操作未完成', '目录已变化，请重新打开工具菜单。')
