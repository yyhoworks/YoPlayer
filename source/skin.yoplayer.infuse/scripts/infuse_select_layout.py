"""Fit the native selector to its real item count without replacing callbacks."""
import xbmc
import xbmcgui


def layout(count, detailed=False):
    row = 100 if detailed else 72
    body = max(row, min(600 if detailed else 576, max(1, count) * row))
    height = 232 + body
    return body, height, (1080 - height) // 2 - 150


def run():
    monitor = xbmc.Monitor()
    for _ in range(16):
        if monitor.waitForAbort(.05):
            return
        if xbmcgui.getCurrentWindowDialogId() != 12000:
            continue
        window = xbmcgui.Window(12000)
        try:
            detailed = xbmc.getCondVisibility('Control.IsVisible(6)')
            ident = 6 if detailed else 3
            # Python ControlList.size() counts Python-owned items; Kodi's native
            # selector fills its C++ list directly. Read the actual container.
            raw_count = xbmc.getInfoLabel('Container(%d).NumItems' % ident)
            count = int(raw_count) if raw_count.isdigit() else 0
            if not count:
                continue
            body, height, offset = layout(count, detailed)
            panel = window.getControl(11800)
            panel.setPosition(0, offset)
            panel.setHeight(height)
            window.getControl(11801).setPosition(36, 96 + offset)
            window.getControl(1).setPosition(36, 28 + offset)
            for control_id in (3, 6):
                item = window.getControl(control_id)
                item.setPosition(36, 124 + offset)
                item.setHeight(body)
            window.getControl(4).setPosition(36, 160 + offset)
            bar = window.getControl(11816)
            bar.setPosition(1080, 124 + offset)
            bar.setVisible(count * (100 if detailed else 72) > body)
            window.getControl(11802).setPosition(36, 164 + body + offset)
            window.getControl(11817).setPosition(520, 148 + body + offset)
            return
        except RuntimeError:
            # Special game/version selectors use a different original layout.
            return


if __name__ == '__main__' and xbmc.getSkinDir() == 'skin.yoplayer.infuse':
    run()
