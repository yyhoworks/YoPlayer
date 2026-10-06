"""Explain the original CoreELEC OEM-splash capability without device writes.

The historical command replaces /flash/oemsplash.png, not the skin logo.
Its flash implementation is intentionally not restored in a Windows-only audit.
"""
import xbmc
import xbmcgui


def main():
    if xbmc.getCondVisibility('System.Platform.Windows'):
        message = ('此入口用于 CoreELEC 的系统开机画面（/flash/oemsplash.png），'
                   '不适用于 Windows Kodi。\n如需修改界面标志，请使用“自定义皮肤 LOGO”。')
    else:
        message = ('此入口用于 CoreELEC 的 /flash/oemsplash.png。\n'
                   '当前版本尚未恢复并验证设备写入流程，未修改开机画面。'
                   '需要在目标 CoreELEC 上确认备份与回退方案后另行验证。')
    xbmcgui.Dialog().ok('自定义开机画面 · CoreELEC', message)


if __name__ == '__main__':
    main()
