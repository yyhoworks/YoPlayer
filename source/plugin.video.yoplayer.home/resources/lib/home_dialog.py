"""Home sheets; native pickers remain available for filesystem and text entry."""
import xbmc
import xbmcgui
import xbmcvfs
import threading


def sheet_layout(count, text_mode=False, has_save=False, message=''):
    """Bound the scrolling body while keeping title, close and footer on screen."""
    import re
    import unicodedata
    # Conservative initial size; XML autoscroll handles font-specific wrapping
    # and arbitrarily long messages without changing cancellation/navigation.
    plain = re.sub(r'\[/?(?:B|I|COLOR[^\]]*)\]', '', message).replace('[CR]', '\n')
    lines = sum(max(1, (sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1
                            for c in line) + 39) // 40) for line in plain.split('\n'))
    help_height = max(64, min(240, lines * 40))
    body = 96 if text_mode else max(104, min(4, count) * 104)
    footer = (160 if has_save else 104) + help_height - 64
    height = 104 + body + footer
    top = (1080 - height) // 2
    return {'top': top, 'height': height, 'body_top': top + 104,
            'body_height': body, 'help_top': top + 104 + body + 16,
            'help_height': help_height, 'save_top': top + height - 70}


POWER_HELP = {
    '正常关闭系统': '设备电源 · 保存数据后关闭系统。',
    '关闭系统': '设备电源 · 关闭当前操作系统。',
    '断电重启': '设备电源 · 保存数据并重启设备。',
    '重启到安卓系统': '设备电源 · 离开 CoreELEC 并进入安卓。',
    '快速关闭系统': '设备电源 · 快速断电可能中断正在进行的写入。',
    '退出 Kodi': 'Kodi 与维护 · 关闭 Kodi，保留操作系统运行。',
    '软重启 Kodi': 'Kodi 与维护 · 重新启动 Kodi 服务。',
    '重新载入皮肤': 'Kodi 与维护 · 重新加载当前界面。',
    '内核切换/升级': 'Kodi 与维护 · 打开内核管理流程。',
}


class Sheet(xbmcgui.WindowXMLDialog):
    def configure(self, title, entries, selected=None, multiple=False, message='', text_mode=False, value='', preselect=0):
        self.initial_focus_pending = False
        self.title = title
        self.entries = entries
        self.multiple = multiple
        self.selected = set(selected or [])
        self.result = None if multiple else -1
        self.message = message
        self.text_mode = text_mode
        self.value = value
        self.preselect = max(0, preselect)
        if text_mode:
            self.result = ''

    def onInit(self):
        layout = sheet_layout(len(self.entries), self.text_mode, self.multiple or self.text_mode, self.message)
        try:
            panel = self.getControl(1010)
        except RuntimeError:
            panel = None  # A provider-only update can meet an older skin XML.
        if panel is not None:
            panel.setPosition(550, layout['top'])
            panel.setHeight(layout['height'])
            self.getControl(1001).setPosition(590, layout['top'] + 24)
            self.getControl(1002).setPosition(1272, layout['top'] + 30)
            self.getControl(1003).setPosition(590, layout['body_top'])
            self.getControl(1003).setHeight(layout['body_height'])
            self.getControl(1006).setPosition(590, layout['body_top'])
            self.getControl(1005).setPosition(590, layout['help_top'])
            self.getControl(1005).setHeight(layout['help_height'])
            self.getControl(1004).setPosition(1130, layout['save_top'])
        self.getControl(1001).setLabel(self.title)
        self.getControl(1004).setVisible(self.multiple or self.text_mode)
        self.getControl(1006).setVisible(self.text_mode)
        self.getControl(1003).setVisible(not self.text_mode)
        if self.text_mode:
            self.getControl(1006).setText(self.value)
            self.getControl(1006).setType(xbmcgui.INPUT_TYPE_TEXT, self.title)
            self.getControl(1004).setLabel('确定')
            self.getControl(1004).controlUp(self.getControl(1006))
            self.getControl(1004).controlLeft(self.getControl(1006))
            self.getControl(1002).controlDown(self.getControl(1006))
        self.getControl(1005).setText(self.message or ('选择后按“保存”；返回键取消' if self.multiple else '返回键关闭菜单'))
        self.getControl(1003).controlDown(self.getControl(1004 if self.multiple else 1002))
        self.render()
        if self.entries:
            self.getControl(1003).selectItem(min(self.preselect, len(self.entries)-1))
        self.update_help()
        target = 1006 if self.text_mode else 1003 if self.entries else 1002
        self.initial_focus_pending = True
        dialog_id = xbmcgui.getCurrentWindowDialogId()
        threading.Thread(target=self.initial_focus, args=(target, dialog_id), daemon=True).start()

    def initial_focus(self, target, dialog_id):
        # WindowXML restores its XML default after onInit. Focus only once,
        # after initialization, and never after user input or another modal.
        monitor = xbmc.Monitor()
        for _ in range(8):
            if monitor.waitForAbort(.05) or not self.initial_focus_pending:
                return
            if xbmcgui.getCurrentWindowDialogId() != dialog_id:
                return
            try:
                focused = self.getFocusId()
                if focused not in (0, 1002, target):
                    return
                if focused == target:
                    self.initial_focus_pending = False
                    return
                if xbmc.getCondVisibility('Control.IsVisible({})'.format(target)):
                    self.setFocusId(target)
                    self.initial_focus_pending = False
                    return
            except RuntimeError:
                continue

    def update_help(self):
        if self.title != '关机' or not self.entries:
            return
        index = self.getControl(1003).getSelectedPosition()
        if 0 <= index < len(self.entries):
            entry = self.entries[index]
            title = entry if isinstance(entry, str) else entry.getLabel()
            self.getControl(1005).setText(POWER_HELP.get(title, '按确认进入此操作；返回键关闭菜单。'))

    def render(self):
        control = self.getControl(1003)
        position = max(0, control.getSelectedPosition())
        control.reset()
        for index, entry in enumerate(self.entries):
            title = entry if isinstance(entry, str) else entry.getLabel()
            prefix = ('已显示  ·  ' if index in self.selected else '已隐藏  ·  ') if self.multiple else ''
            item = xbmcgui.ListItem(label=prefix + title)
            if not isinstance(entry, str):
                item.setLabel2(entry.getLabel2())
                item.setArt({key: entry.getArt(key) for key in ('icon', 'thumb') if entry.getArt(key)})
            control.addItem(item)
        if self.entries:
            control.selectItem(min(position, len(self.entries) - 1))

    def onClick(self, control_id):
        self.initial_focus_pending = False
        if control_id == 1002:
            self.close()
        elif control_id == 1004 and self.text_mode:
            self.result = self.getControl(1006).getText()
            self.close()
        elif control_id == 1004 and self.multiple:
            self.result = sorted(self.selected)
            self.close()
        elif control_id == 1003:
            index = self.getControl(1003).getSelectedPosition()
            if not 0 <= index < len(self.entries):
                return
            if self.multiple:
                if index in self.selected:
                    self.selected.remove(index)
                else:
                    self.selected.add(index)
                self.render()
            else:
                self.result = index
                self.close()

    def onAction(self, action):
        self.initial_focus_pending = False
        if action.getId() in (9, 10, 92):
            self.close()
        else:
            self.update_help()


def show(title, entries, selected=None, multiple=False, message='', text_mode=False, value='', preselect=0):
    sheet = Sheet('YoPlayerHomeSheet.xml', xbmcvfs.translatePath('special://skin'), 'Default', '1080p')
    sheet.configure(title, entries, selected, multiple, message, text_mode, value, preselect)
    sheet.doModal()
    result = sheet.result
    del sheet
    return result


class Dialog:
    """Only replace selection/confirmation sheets while the YoPlayer skin is active."""
    def __init__(self):
        self.native = xbmcgui.Dialog()

    def __getattr__(self, name):
        return getattr(self.native, name)

    def select(self, heading, items, **kwargs):
        if xbmc.getSkinDir() != 'skin.yoplayer.infuse':
            return self.native.select(heading, items, **kwargs)
        return show(heading, items, preselect=kwargs.get('preselect', 0))

    def input(self, heading, defaultt='', **kwargs):
        if xbmc.getSkinDir() != 'skin.yoplayer.infuse' or kwargs:
            return self.native.input(heading, defaultt=defaultt, **kwargs)
        return show(heading, [], message='输入完成后选择“确定”；返回键取消', text_mode=True, value=defaultt)

    def multiselect(self, heading, items, preselect=None, **kwargs):
        if xbmc.getSkinDir() != 'skin.yoplayer.infuse':
            return self.native.multiselect(heading, items, preselect=preselect or [], **kwargs)
        return show(heading, items, preselect, True)

    def yesno(self, heading, message, nolabel='取消', yeslabel='确定', **kwargs):
        if xbmc.getSkinDir() != 'skin.yoplayer.infuse':
            return self.native.yesno(heading, message, nolabel=nolabel, yeslabel=yeslabel, **kwargs)
        return show(heading, [nolabel or '取消', yeslabel or '确定'], message=message) == 1
