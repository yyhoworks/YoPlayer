"""Use the installed Emby settings API; never copy server marks or credentials."""
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import xml.etree.ElementTree as ET
from pathlib import Path

OPTIONS=(('跳过片头','enableSkipIntro',None),('跳过片头前提示','askSkipIntro','enableSkipIntro'),
         ('跳过片尾','enableSkipCredits',None),('跳过片尾前提示','askSkipCredits','enableSkipCredits'))

def run():
    ident=next((i for i in ('plugin.service.emby-next-gen','plugin.video.emby-next-gen')
                if xbmc.getCondVisibility('System.AddonIsEnabled('+i+')')),None)
    if not ident:
        xbmcgui.Dialog().ok('Emby 片头 / 片尾','请先连接并启用 Emby 插件。');return
    addon=xbmcaddon.Addon(ident)
    path=Path(xbmcvfs.translatePath(addon.getAddonInfo('path')))/'resources/settings.xml'
    try:
        supported={s.get('id') for s in ET.parse(path).getroot().iter('setting')}
    except (OSError,ET.ParseError):
        xbmcgui.Dialog().ok('Emby 片头 / 片尾','无法读取插件的跳过偏好，请在 Emby 插件设置中查看。');return
    if not all(key in supported for _,key,_ in OPTIONS):
        xbmcgui.Dialog().ok('Emby 片头 / 片尾','当前插件不提供全部跳过偏好，请在 Emby 插件设置中查看可用项。');return
    position=0
    while True:
        values={key:addon.getSettingBool(key) for _,key,_ in OPTIONS}
        rows=[name+' · '+('开启' if values[key] else '关闭')+
              ('（先开启跳过）' if dependency and not values[dependency] else '') for name,key,dependency in OPTIONS]
        pick=xbmcgui.Dialog().select('Emby 片头 / 片尾',rows+['返回'],preselect=position)
        if not 0<=pick<len(OPTIONS):return
        position=pick;_,key,dependency=OPTIONS[pick]
        if dependency and not addon.getSettingBool(dependency):continue
        addon.setSettingBool(key,not addon.getSettingBool(key))

if __name__=='__main__' and xbmc.getSkinDir()=='skin.yoplayer.infuse':run()
