"""TV and mouse reorder sheet: lift, move, drop, then finish once."""
import time
import threading
import xbmc
import xbmcgui
import xbmcvfs
from home_dialog import Sheet, Dialog
from reorder_state import ReorderState


class ReorderDialog(Sheet):
    def configure(self, title, rows, nested=False):
        self.title = title
        self.state = ReorderState(rows)
        self.nested = nested
        self.result = None
        self.initial_focus_pending = False
        self.last_direction = None
        self.last_step = 0

    def onInit(self):
        self.setProperty('reorder.title', self.title)
        self.setProperty('reorder.subtitle', '按确定拿起，上下移动，再按确定放下')
        self.setProperty('reorder.fixed', '全部分类固定在末尾' if self.nested else '仅调整首页显示顺序')
        self.getControl(1004).setLabel('完成' if self.nested else '保存')
        self.render()
        self.initial_focus_pending = True
        target = 1100 if self.state.rows else 1004
        threading.Thread(target=self.initial_focus,
                         args=(target, xbmcgui.getCurrentWindowDialogId()), daemon=True).start()

    def render(self, restore=True):
        state = self.state
        state.ensure_visible()
        moving = state.lifted is not None
        self.setProperty('reorder.total', '{} / {} 项'.format(state.focus + 1, len(state.rows)) if state.rows else '0 项')
        self.setProperty('reorder.empty', '' if state.rows else '暂无可排序项目')
        self.setProperty('reorder.hint', '↑ ↓ 移动   确定 放下   返回 撤销' if moving else '确定 拿起项目   → 前往{}'.format('完成' if self.nested else '保存'))
        self.getControl(1004).setEnabled(not moving)
        for slot in range(state.visible_count):
            index = state.start + slot
            present = index < len(state.rows)
            self.getControl(1100 + slot).setVisible(present)
            self.getControl(1100 + slot).setEnabled(present and (not moving or index == state.focus))
            self.setProperty('reorder.row.{}.number'.format(slot), '{:02d}'.format(index + 1) if present else '')
            self.setProperty('reorder.row.{}.name'.format(slot), state.rows[index]['name'] if present else '')
        y = 264 + (state.focus - state.start) * 74
        for control_id, x, offset in ((1200, 444, 0), (1201, 1312, 10), (1202, 1370, 10), (1203, 1190, 0)):
            control = self.getControl(control_id)
            control.setPosition(x, y + offset)
            control.setVisible(moving)
        self.getControl(1201).setEnabled(state.focus > 0)
        self.getControl(1202).setEnabled(state.focus + 1 < len(state.rows))
        if restore:
            self.focus_row()

    def focus_row(self):
        self.setFocusId(1100 + self.state.focus - self.state.start if self.state.rows else 1004)

    def leave(self):
        if self.state.undo_lift():
            self.render()
        elif not self.state.dirty or Dialog().yesno('放弃未保存的调整？', '已保存的顺序不会改变。',
                                                    nolabel='继续调整', yeslabel='放弃调整'):
            self.close()
        else:
            self.focus_row()

    def onClick(self, control_id):
        self.initial_focus_pending = False
        self.last_direction = None
        if control_id in (1002, 1007):
            self.leave()
        elif control_id == 1004:
            result = self.state.finish()
            if result is not None:
                self.result = result
                self.close()
        elif 1100 <= control_id < 1108:
            index = self.state.start + control_id - 1100
            if self.state.lifted is None:
                self.state.select(index)
                self.state.toggle()
            elif index == self.state.focus:
                self.state.toggle()
            self.render()
        elif control_id in (1201, 1202) and self.state.lifted is not None:
            self.state.step(-1 if control_id == 1201 else 1)
            self.render()

    def onAction(self, action):
        self.initial_focus_pending = False
        action_id = action.getId()
        if action_id in (9, 10, 92):
            self.leave()
            return
        focused = self.getFocusId()
        if action_id in (3, 4):
            if 1100 <= focused < 1108:
                if self.state.lifted is None:
                    self.state.select(self.state.start + focused - 1100)
                now = time.monotonic()
                # Kodi repeats held direction keys; cap movement at about 7/s.
                if self.last_direction == action_id and now - self.last_step < .14:
                    return
                self.last_direction, self.last_step = action_id, now
                self.state.step(-1 if action_id == 3 else 1)
                self.render()
            else:
                self.focus_row()
        elif action_id == 2:
            if self.state.lifted is None:
                if 1100 <= focused < 1108:
                    self.state.select(self.state.start + focused - 1100)
                self.setFocusId(1004)
        elif action_id == 1:
            if focused == 1004:
                self.focus_row()
            elif self.state.lifted is None:
                self.setFocusId(1007)
        elif action_id == 7:
            self.last_direction = None


def show(title, rows, nested=False):
    if xbmc.getSkinDir() != 'skin.yoplayer.infuse':
        # The provider can still be used with another skin's native picker.
        draft = ReorderState(rows)
        dialog = xbmcgui.Dialog()
        while True:
            selected = dialog.select(title, ['{:02d}   {}'.format(i + 1, r['name']) for i, r in enumerate(draft.rows)] + ['完成' if nested else '保存', '取消'], preselect=draft.focus)
            if selected < 0 or selected == len(draft.rows) + 1:
                return None
            if selected == len(draft.rows):
                return draft.finish()
            draft.select(selected)
            direction = dialog.select(draft.rows[selected]['name'], ['上移', '下移', '返回'])
            if direction in (0, 1):
                draft.toggle()
                draft.step(-1 if direction == 0 else 1)
                draft.toggle()
    sheet = ReorderDialog('YoPlayerReorder.xml', xbmcvfs.translatePath('special://skin'), 'Default', '1080p')
    sheet.configure(title, rows, nested)
    sheet.doModal()
    result = sheet.result
    del sheet
    return result
