import sys
import json
import xbmc
import base64

def get_setting(setting_name):
    query = {
        "jsonrpc": "2.0",
        "method": "Settings.GetSettingValue",
        "params": {"setting": setting_name},
        "id": 1
    }
    response = xbmc.executeJSONRPC(json.dumps(query))
    try:
        result = json.loads(response)
        return result.get('result', {}).get('value')
    except Exception:
        return None

def set_setting(setting_name, value):
    query = {
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {"setting": setting_name, "value": value},
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(query))

def format_offset_value(val):
    try:
        num = int(val)
        if num > 0:
            return "+{}".format(num)
        else:
            return str(num)
    except (ValueError, TypeError):
        return str(val)

def clear_skin_strings():
    xbmc.executebuiltin('Skin.SetString(subtitlename,)')
    xbmc.executebuiltin('Skin.SetString(subsetvar,)')

def wait_for_idle_and_clear():
    while not xbmc.getCondVisibility('System.IdleTime(1)'):
        xbmc.sleep(1000)
    
    clear_skin_strings()

def handle_pos(direction):
    build_date = xbmc.getInfoLabel('Skin.String(BuildDate)')
    
    if 'R10' not in build_date and 'F10' not in build_date:
        if direction == 'up':
            xbmc.executebuiltin('SubtitleShiftUp')
        else:
            xbmc.executebuiltin('SubtitleShiftDown')
        return

    xbmc.executebuiltin('Skin.SetString(subtitlename,Subtitle Vertical Offset)')
    set_setting('subtitles.pgsverticalmode', 5)
    
    current_val = get_setting('subtitles.pgsverticaloffset')
    if current_val is None:
        wait_for_idle_and_clear()
        return
        
    try:
        current_val = int(current_val)
    except ValueError:
        wait_for_idle_and_clear()
        return

    formatted_current = format_offset_value(current_val)
    xbmc.executebuiltin('Skin.SetString(subsetvar,{})'.format(formatted_current))
    
    new_val = current_val + 1 if direction == 'up' else current_val - 1
    set_setting('subtitles.pgsverticaloffset', new_val)
    
    formatted_new = format_offset_value(new_val)
    xbmc.executebuiltin('Skin.SetString(subsetvar,{})'.format(formatted_new))
    
    wait_for_idle_and_clear()

def handle_zoom(direction):
    xbmc.executebuiltin('Skin.SetString(subtitlename,Subtitle Zoom Ratio)')
    
    current_val = get_setting('subtitles.bitmapzoom')
    if current_val is None:
        wait_for_idle_and_clear()
        return
        
    try:
        current_val = int(current_val)
    except ValueError:
        wait_for_idle_and_clear()
        return

    xbmc.executebuiltin('Skin.SetString(subsetvar,{})'.format(current_val))
    
    new_val = current_val + 5 if direction == 'up' else current_val - 5
    set_setting('subtitles.bitmapzoom', new_val)
    
    xbmc.executebuiltin('Skin.SetString(subsetvar,{})'.format(new_val))
    
    wait_for_idle_and_clear()

def main():
    # Decode the skin name from Base64 to hide it from plain text view
    target_skin_b64 = "c2tpbi5jb25mbHVlbmNlLm1pbnNr"
    target_skin = base64.b64decode(target_skin_b64).decode('utf-8')
    
    current_skin = xbmc.getSkinDir()
    if current_skin != target_skin:
        return

    if len(sys.argv) < 2:
        return

    action = sys.argv[1].lower()

    if action == "reset":
        set_setting('subtitles.pgsverticaloffset', 0)
        set_setting('subtitles.bitmapzoom', 100)
        return

    if action == "posup":
        handle_pos('up')
    elif action == "posdown":
        handle_pos('down')
    elif action == "zoomup":
        handle_zoom('up')
    elif action == "zoomdown":
        handle_zoom('down')

if __name__ == "__main__":
    main()