"""Fit Kodi's actual context buttons while retaining their native callbacks."""
import xbmc
import xbmcgui

def geometry(count,poster):
    rows=max(1,min(7,count));body=rows*72-8
    body=max(body,252 if poster else 0)
    width=920 if poster else 760
    return width,body,body+116

def run():
    monitor=xbmc.Monitor();last=None
    for _ in range(24):
        if monitor.waitForAbort(.05):return
        if xbmcgui.getCurrentWindowDialogId()!=10106:continue
        w=xbmcgui.Window(10106)
        buttons=[]
        for ident in list(range(1000,1200))+[3000]:
            if not xbmc.getCondVisibility('Control.IsVisible('+str(ident)+')'):
                continue
            try:c=w.getControl(ident)
            except RuntimeError:continue
            buttons.append(c)
        if not buttons or len(buttons)!=last:
            last=len(buttons);continue
        poster=xbmc.getCondVisibility('!String.IsEmpty(ListItem.Art(poster)) | !String.IsEmpty(ListItem.Art(season.poster)) | !String.IsEmpty(ListItem.Art(tvshow.poster))')
        width,body,height=geometry(len(buttons),poster)
        group=w.getControl(11811);group.setPosition((1920-width)//2,(1080-height)//2)
        panel=w.getControl(11810);panel.setWidth(width);panel.setHeight(height)
        title=w.getControl(11812);title.setWidth(width-56)
        if not title.getLabel().strip():title.setLabel('更多操作')
        left=220 if poster else 28;listwidth=width-left-28
        # Kodi does not expose native grouplist controls to Python. The XML
        # viewport stays seven rows tall; a supported group positions it.
        listing=w.getControl(11814);listing.setPosition(left,88)
        for c in buttons:c.setWidth(listwidth-12)
        # Native scrollbars have no Python wrapper either. Keep their seven-row
        # viewport in XML and position/hide only the supported surrounding group.
        bar=w.getControl(11815);bar.setPosition(width-14,88);bar.setVisible(len(buttons)>7)
        return

if __name__=='__main__' and xbmc.getSkinDir()=='skin.yoplayer.infuse':run()
