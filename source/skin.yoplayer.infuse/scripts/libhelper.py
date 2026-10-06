"""First library visit: explain Emby connection without scanning media."""
import xbmc
import xbmcgui

def run_first_run_check():
    xbmc.executebuiltin('Skin.SetString(libfirstrun,1)')
    if xbmc.getCondVisibility('Library.HasContent(movies) | Library.HasContent(tvshows)'):
        return
    xbmcgui.Dialog().ok('媒体库暂时为空', '请检查 Emby 连接及媒体库同步状态，再到“媒体分库”选择首页显示内容。')

if __name__=='__main__':run_first_run_check()
