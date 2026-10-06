"""Small native settings actions; cancellation never changes preferences."""
import sys
import xbmc
import xbmcgui


def choose_osd():
    values = ('3', '4', '5', '8', '10')
    current = xbmc.getInfoLabel('Skin.String(OSDAutoCloseTime)') or '4'
    labels = [v+' 秒' for v in values]
    if current not in values:
        labels.append('保留当前值（'+current+' 秒）')
    picked = xbmcgui.Dialog().select('自动隐藏播放控件', labels,
        preselect=values.index(current) if current in values else len(values))
    if 0 <= picked < len(values):
        xbmc.executebuiltin('Skin.SetString(OSDAutoCloseTime,'+values[picked]+')')


def dependency(addon):
    allowed = {'plugin.video.themoviedb.helper', 'script.skinvariables',
               'script.embuary.info', 'script.globalsearch'}
    if addon not in allowed:
        return
    dialog = xbmcgui.Dialog()
    if not xbmc.getCondVisibility('System.HasAddon('+addon+')'):
        if dialog.yesno('可选资料服务', '尚未安装，是否打开安装入口？'):
            xbmc.executebuiltin('InstallAddon('+addon+')')
    elif not xbmc.getCondVisibility('System.AddonIsEnabled('+addon+')'):
        if dialog.yesno('可选资料服务', '插件已安装但未启用，是否启用？'):
            xbmc.executebuiltin('EnableAddon('+addon+')')
    else:
        xbmc.executebuiltin('Addon.OpenSettings('+addon+')')


def initialise():
    # Materialize only an absent source; never overwrite a user's preference.
    if not xbmc.getInfoLabel('Skin.String(YoPlayerRatingSource)'):
        xbmc.executebuiltin('Skin.SetString(YoPlayerRatingSource,emby)')


def main(action, argument=''):
    if action == 'osd-time':
        choose_osd()
    elif action == 'rating-source':
        picked = xbmcgui.Dialog().select('评分来源', ['Emby 媒体库'], preselect=0)
        if picked == 0:
            xbmc.executebuiltin('Skin.SetString(YoPlayerRatingSource,emby)')
    elif action == 'dependency':
        dependency(argument)
    elif action == 'bluetooth':
        from infuse_device import capabilities
        if capabilities().get('coreelec'):
            xbmc.executebuiltin('RunAddon(service.coreelec.settings)')
    elif action == 'zoom':
        values = ('50', '75', '100', '125', '150', '175', '200')
        current = xbmc.getInfoLabel('Skin.String(zoomratio)') or '100'
        picked = xbmcgui.Dialog().select('手动缩放比例', [v+'%' for v in values],
            preselect=values.index(current) if current in values else -1)
        if 0 <= picked < len(values):
            xbmc.executebuiltin('Skin.SetString(zoomnumber,1)')
            xbmc.executebuiltin('Skin.SetString(zoomratio,'+values[picked]+')')
    elif action == 'init':
        initialise()
    elif action in ('plot', 'read-plot') and xbmcgui.getCurrentWindowDialogId() == 12003:
        window = xbmcgui.Window(12003)
        if action == 'plot' and window.getProperty('YoPlayer.PlotExpanded') == 'true':
            window.clearProperty('YoPlayer.PlotExpanded')
        else:
            plot = xbmc.getInfoLabel('ListItem.Plot')
            if not plot:
                return
            identity = window.getProperty('YoPlayer.DetailSeasons.Identity')
            if action == 'plot':
                window.setProperty('YoPlayer.PlotExpanded', 'true')
            xbmcgui.Dialog().textviewer('完整简介', plot)
            if (xbmcgui.getCurrentWindowDialogId() == 12003 and
                    window.getProperty('YoPlayer.DetailSeasons.Identity') == identity):
                # External script callers remain compatible; the extra synopsis
                # buttons were withdrawn, so return to the existing audio action.
                window.setFocusId(9015)


if __name__ == '__main__' and xbmc.getSkinDir() == 'skin.yoplayer.infuse':
    main(sys.argv[1] if len(sys.argv) > 1 else 'init', sys.argv[2] if len(sys.argv) > 2 else '')
