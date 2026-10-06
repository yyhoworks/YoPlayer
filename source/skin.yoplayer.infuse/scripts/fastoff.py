import xbmc
import os
import subprocess

nandscript = '/usr/sbin/poweroff'
if os.path.exists(nandscript):
    xbmc.executebuiltin('Notification(正在等待关机)')
    subprocess.call('/usr/sbin/poweroff')
    xbmc.sleep(300)
    subprocess.call(['poweroff', '-f'])
else:
    xbmc.executebuiltin('Notification(poweroff, not available)')
exit() 