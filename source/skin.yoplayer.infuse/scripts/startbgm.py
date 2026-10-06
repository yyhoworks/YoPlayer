import xbmc


def main():
    xbmc.executebuiltin('Skin.SetString(startmusic,1)')
    custom_path = xbmc.getInfoLabel('Skin.String(custombgm)')
    if xbmc.getCondVisibility('Skin.HasSetting(custombgmon)') and custom_path.strip():
        xbmc.executebuiltin(f'PlayMedia({custom_path})')
    else:
        xbmc.executebuiltin('PlayMedia(special://skin/resources/start.mp3)')

    xbmc.sleep(3000)
    while xbmc.getCondVisibility('Player.HasMedia'):
        xbmc.sleep(100)
    xbmc.executebuiltin('Skin.SetString(startmusic,0)')


if __name__ == '__main__':
    main()
